"""
Live Order Execution System
===========================

Executes real orders via Kite Connect API for live trading:
1. Places BUY/SELL orders through KiteManager.place_order
2. Persists orders and positions to Supabase with trading_mode='live'
3. Tracks positions in memory for the trading loop
4. Recovers open positions from DB on startup
5. Enforces same position/order linkage as paper (buy_order_id, sell_order_id FKs)
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import pytz

from strategies import TradingSignal, SignalType, Position


class LiveOrderExecutor:
    """
    Live order execution via Kite Connect.
    Places real orders and persists to DB with trading_mode='live'.
    """

    def __init__(self, db_manager=None, kite_manager=None):
        self.db_manager = db_manager
        self.kite_manager = kite_manager
        self.positions: Dict[str, Position] = {}
        self.ist = pytz.timezone('Asia/Kolkata')
        self.trading_mode = 'live'

        if self.db_manager:
            self._recover_positions_from_database()
            self._recover_orphaned_positions()

    @property
    def available_capital(self) -> float:
        """Available cash from Kite (for TradingManager compatibility)."""
        if self.kite_manager and self.kite_manager.is_authenticated:
            funds = self.kite_manager.get_funds()
            return float(funds.get('available_cash', 0.0))
        return 0.0

    def _base_symbol(self, symbol: str) -> str:
        """Extract base symbol (strip _uuid suffix for Kite API)."""
        return symbol.split('_')[0] if '_' in symbol else symbol

    def _recover_positions_from_database(self):
        """Load open positions from DB (trading_mode='live') into memory."""
        if not self.db_manager:
            return
        try:
            open_positions = self.db_manager.supabase.table('positions').select('*').eq(
                'trading_mode', self.trading_mode
            ).eq('is_open', True).execute()
            for pos_data in open_positions.data:
                try:
                    symbol = pos_data['symbol']
                    if symbol.endswith('CE'):
                        signal_type = SignalType.BUY_CALL
                    elif symbol.endswith('PE'):
                        signal_type = SignalType.BUY_PUT
                    else:
                        continue
                    entry_time = datetime.fromisoformat(pos_data['entry_time'].replace('Z', '+00:00'))
                    unique_key = f"{symbol}_{pos_data['id'][:8]}"
                    position = Position(
                        symbol=symbol,
                        signal_type=signal_type,
                        quantity=pos_data['quantity'],
                        entry_price=pos_data['average_price'],
                        entry_time=entry_time,
                        last_update=datetime.fromisoformat(pos_data['updated_at'].replace('Z', '+00:00')),
                        is_closed=False,
                        metadata={
                            'strategy': pos_data.get('strategy_name', 'unknown'),
                            'position_id': pos_data['id'],
                            'buy_order_id': pos_data.get('buy_order_id'),
                            'unique_key': unique_key,
                            'original_quantity': pos_data['quantity'],
                        }
                    )
                    self.positions[unique_key] = position
                except Exception as e:
                    print(f"Failed to recover position {pos_data.get('symbol', 'unknown')}: {e}")
        except Exception as e:
            print(f"Position recovery failed: {e}")

    def _recover_orphaned_positions(self):
        """Fix positions marked open but with SELL orders (inconsistent state)."""
        if not self.db_manager:
            return
        try:
            open_positions = self.db_manager.supabase.table('positions').select('*').eq(
                'trading_mode', self.trading_mode
            ).eq('is_open', True).execute()
            for pos in open_positions.data:
                sell_orders = self.db_manager.supabase.table('orders').select('*').eq(
                    'symbol', pos['symbol']
                ).eq('strategy_name', pos['strategy_name']).eq('order_type', 'SELL').eq(
                    'trading_mode', self.trading_mode
                ).order('created_at', desc=False).execute()
                if sell_orders.data:
                    sell_order = sell_orders.data[0]
                    entry_price = pos['average_price']
                    exit_price = sell_order['price']
                    quantity = pos['quantity']
                    pnl = (exit_price - entry_price) * quantity
                    update_data = {
                        'quantity': 0,
                        'current_price': exit_price,
                        'unrealized_pnl': 0.0,
                        'realized_pnl': pnl,
                        'is_open': False,
                        'exit_time': sell_order['created_at'],
                        'exit_price': exit_price,
                        'updated_at': datetime.now(self.ist).isoformat(),
                        'sell_order_id': sell_order['id'],
                    }
                    self.db_manager.supabase.table('positions').update(update_data).eq('id', pos['id']).execute()
                    matching_keys = [k for k in self.positions.keys() if k.startswith(pos['symbol'])]
                    for key in matching_keys:
                        if (hasattr(self.positions[key], 'metadata') and
                                self.positions[key].metadata.get('position_id') == pos['id']):
                            self.positions[key].is_closed = True
                            del self.positions[key]
                            break
        except Exception as e:
            print(f"Orphan recovery failed: {e}")

    def place_order(self, signal: TradingSignal, current_market_price: float) -> str:
        """
        Place a live order via Kite and persist to DB.
        Returns order_id (our internal id) if successful, empty string otherwise.
        """
        if not self.kite_manager or not self.kite_manager.is_authenticated:
            print("Kite not authenticated - cannot place live order")
            return ""
        if current_market_price <= 0:
            print("Invalid market price for live order")
            return ""

        base_symbol = self._base_symbol(signal.symbol)
        is_buy = signal.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]
        transaction_type = 'BUY' if is_buy else 'SELL'

        if not is_buy:
            if not self._validate_sell(signal):
                return ""

        # Zerodha strictly blocks naked MARKET orders for NFO Options.
        # We mathematically simulate a Market Order by sending a LIMIT order with a 5% buffer.
        buffer_percent = 0.05
        if is_buy:
            safe_price = current_market_price * (1 + buffer_percent)
        else:
            safe_price = current_market_price * (1 - buffer_percent)
            
        # NSE tick size requires rounding to nearest 0.05
        safe_limit_price = round(safe_price * 20) / 20.0

        result = self.kite_manager.place_order(
            tradingsymbol=base_symbol,
            transaction_type=transaction_type,
            quantity=signal.quantity,
            order_type='LIMIT',
            price=safe_limit_price,
            product='MIS',
            validity='IOC',
        )

        if not result.get('success'):
            print(f"Kite order failed: {result.get('message', 'Unknown error')}")
            return ""

        kite_order_id = str(result.get('order_id', ''))
        if not kite_order_id:
            print("Kite returned no order_id")
            return ""

        # Fetch actual executed price and filled quantity from Kite
        import time
        executed_price = current_market_price
        filled_quantity = signal.quantity
        try:
            time.sleep(0.5)  # Brief wait for exchange to fulfill the market order
            history = self.kite_manager.kite.order_history(order_id=kite_order_id)
            if history:
                # The last entry usually has the final COMPLETE status and true average_price
                for state in reversed(history):
                    status = state.get('status')
                    if status == 'COMPLETE':
                        if state.get('average_price'):
                            executed_price = float(state.get('average_price'))
                        if state.get('filled_quantity') is not None:
                            filled_quantity = int(state.get('filled_quantity'))
                        break
                    elif status in ['CANCELLED', 'REJECTED']:
                        # The IOC limit order failed to fill instantly
                        f_qty = int(state.get('filled_quantity', 0))
                        if f_qty == 0:
                            print(f"Kite order {kite_order_id} was {status} (Zero Fill). Will retry later.")
                            return ""
                        else:
                            filled_quantity = f_qty
                            if state.get('average_price'):
                                executed_price = float(state.get('average_price'))
                            break
        except Exception as e:
            print(f"Non-critical: Failed to verify exact execution stats for {kite_order_id}: {e}")

        if executed_price <= 0:
            executed_price = current_market_price

        if not self.db_manager:
            print("No DB manager - order placed on Kite but not persisted")
            return kite_order_id

        strategy_name = (signal.metadata or {}).get('strategy', 'unknown')
        order_data = {
            'strategy_name': strategy_name,
            'trading_mode': self.trading_mode,
            'symbol': base_symbol,
            'order_type': transaction_type,
            'quantity': signal.quantity,
            'price': executed_price,
            'order_id': kite_order_id,
            'status': 'COMPLETE',
            'filled_quantity': filled_quantity,
            'filled_price': executed_price,
            'signal_data': {
                **(signal.metadata or {}),
                'original_signal_type': signal.signal_type.value,
                'kite_order_id': kite_order_id,
            }
        }
        saved_order_id = self.db_manager.save_order(order_data)
        if not saved_order_id:
            print(f"Failed to save order to DB: {transaction_type} {base_symbol}")
            if is_buy:
                return ""
            return kite_order_id

        if is_buy:
            position_data = {
                'strategy_name': strategy_name,
                'trading_mode': self.trading_mode,
                'symbol': base_symbol,
                'quantity': signal.quantity,
                'average_price': executed_price,
                'current_price': executed_price,
                'unrealized_pnl': 0.0,
                'is_open': True,
                'entry_time': datetime.now(self.ist).isoformat(),
                'buy_order_id': saved_order_id,
            }
            position_id = self.db_manager.save_position(position_data)
            if position_id:
                unique_key = f"{base_symbol}_{uuid.uuid4().hex[:8]}"
                position = Position(
                    symbol=base_symbol,
                    signal_type=signal.signal_type,
                    quantity=signal.quantity,
                    entry_price=executed_price,
                    entry_time=datetime.now(self.ist),
                    last_update=datetime.now(self.ist),
                    highest_price=executed_price,
                    is_closed=False,
                    metadata={
                        'strategy': strategy_name,
                        'position_id': position_id,
                        'buy_order_id': saved_order_id,
                        'unique_key': unique_key,
                        'original_quantity': signal.quantity,
                    }
                )
                self.positions[unique_key] = position
            return kite_order_id
        else:
            self._close_position_in_db_and_memory(signal, base_symbol, executed_price, saved_order_id)
            return kite_order_id

    def _validate_sell(self, signal: TradingSignal) -> bool:
        """Ensure we have an open position before SELL and reconcile with Broker."""
        base_symbol = self._base_symbol(signal.symbol)
        
        # 1. BROKER RECONCILIATION: Check if user physically sold the position out-of-band
        try:
            if self.kite_manager and self.kite_manager.is_authenticated:
                kite_positions = self.kite_manager.kite.positions()
                if kite_positions and 'net' in kite_positions:
                    broker_owned_qty = 0
                    for kp in kite_positions['net']:
                        if kp.get('tradingsymbol') == base_symbol:
                            broker_owned_qty = int(kp.get('quantity', 0))
                            break
                    if broker_owned_qty <= 0:
                        print(f"SELL validation aborted: Broker confirms 0 quantity for {base_symbol}. Marking as manually closed to halt loop.")
                        self._close_position_in_db_and_memory(
                            signal=signal, 
                            base_symbol=base_symbol, 
                            exit_price=0.0, 
                            sell_order_db_id="MANUAL_SYNC"
                        )
                        return False
        except Exception as e:
            print(f"Warning: Failed to reconcile broker positions before sell: {e}")

        # 2. LOCAL MEMORY CHECKS
        memory_ok = any(
            pos.symbol == base_symbol and not getattr(pos, 'is_closed', False) and pos.quantity >= signal.quantity
            for pos in self.positions.values()
        )
        if not memory_ok:
            print(f"SELL validation failed: no matching open position for {base_symbol}")
            return False
        if self.db_manager:
            open_positions = self.db_manager.supabase.table('positions').select('quantity').eq(
                'symbol', base_symbol
            ).eq('trading_mode', self.trading_mode).eq('is_open', True).execute()
            total = sum(p['quantity'] for p in open_positions.data)
            if total < signal.quantity:
                print(f"SELL validation failed: only {total} available, need {signal.quantity}")
                return False
        return True

    def _close_position_in_db_and_memory(
        self, signal: TradingSignal, base_symbol: str, exit_price: float, sell_order_db_id: str
    ):
        """Update DB position as closed and remove from memory."""
        target_key = None
        target_pos = None
        oldest = None
        for key, pos in self.positions.items():
            if (pos.symbol == base_symbol and not getattr(pos, 'is_closed', False) and
                    pos.quantity == signal.quantity):
                if oldest is None or pos.entry_time < oldest:
                    target_key, target_pos, oldest = key, pos, pos.entry_time
        if not target_pos or not target_pos.metadata.get('position_id'):
            return
        original_qty = target_pos.metadata.get('original_quantity', signal.quantity)
        pnl = (exit_price - target_pos.entry_price) * original_qty
        pnl_pct = ((exit_price - target_pos.entry_price) / target_pos.entry_price * 100) if target_pos.entry_price else 0
        update_data = {
            'quantity': 0,
            'current_price': exit_price,
            'unrealized_pnl': 0.0,
            'realized_pnl': pnl,
            'pnl_percent': pnl_pct,
            'is_open': False,
            'exit_time': datetime.now(self.ist).isoformat(),
            'exit_price': exit_price,
            'exit_reason': (signal.metadata or {}).get('reason', 'Strategy Exit'),
            'exit_reason_category': (signal.metadata or {}).get('exit_reason_category', 'OTHER'),
            'sell_order_id': sell_order_db_id,
        }
        self.db_manager.supabase.table('positions').update(update_data).eq(
            'id', target_pos.metadata['position_id']
        ).execute()
        target_pos.is_closed = True
        if target_key:
            del self.positions[target_key]

    def close_position(
        self, symbol: str, current_price: float, reason: str = "Manual close",
        exit_reason_category: str = "MANUAL"
    ) -> bool:
        """Close an open live position via Kite and update DB."""
        base_symbol = self._base_symbol(symbol)
        position_key = None
        position = None
        for key, pos in self.positions.items():
            if key.startswith(base_symbol) and not getattr(pos, 'is_closed', False):
                position_key, position = key, pos
                break
        if not position:
            print(f"No open position for {symbol}")
            return False

        close_type = SignalType.SELL_CALL if position.signal_type == SignalType.BUY_CALL else SignalType.SELL_PUT
        qty = position.metadata.get('original_quantity', position.quantity)
        if qty <= 0:
            qty = position.quantity or 75

        class CloseSignal:
            symbol = base_symbol
            signal_type = close_type
            quantity = qty
            confidence = 1.0
            metadata = {
                'reason': reason,
                'exit_reason_category': exit_reason_category,
                'strategy': position.metadata.get('strategy', 'unknown'),
                'is_closing_order': True,
            }

        order_id = self.place_order(CloseSignal(), current_price)
        return bool(order_id)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Portfolio summary for live: use Kite funds + in-memory positions."""
        funds = self.kite_manager.get_funds() if self.kite_manager else {}
        available = funds.get('available_cash', 0.0)
        used = funds.get('used_margin', 0.0)
        total_value = available + used
        position_details = []
        total_pnl = 0.0
        for key, pos in self.positions.items():
            if getattr(pos, 'is_closed', False):
                continue
            ltp = 0.0
            if self.kite_manager and self.kite_manager.is_authenticated:
                nfo = f"NFO:{pos.symbol}"
                data = self.kite_manager.ltp([nfo])
                if data and nfo in data:
                    ltp = float(data[nfo].get('last_price', 0))
            if ltp <= 0:
                ltp = pos.entry_price
            pnl = (ltp - pos.entry_price) * pos.quantity
            total_pnl += pnl
            position_details.append({
                'symbol': pos.symbol,
                'quantity': pos.quantity,
                'entry_price': pos.entry_price,
                'current_price': ltp,
                'position_value': ltp * pos.quantity,
                'pnl': pnl,
                'pnl_percent': (pnl / (pos.entry_price * pos.quantity) * 100) if pos.entry_price else 0,
                'entry_time': pos.entry_time.isoformat(),
                'strategy': pos.metadata.get('strategy', 'unknown') if pos.metadata else 'unknown',
            })
        return {
            'initial_capital': available + used,
            'available_capital': available,
            'used_capital': used,
            'total_value': total_value + total_pnl,
            'total_pnl': total_pnl,
            'total_pnl_percent': (total_pnl / total_value * 100) if total_value else 0,
            'utilization_percent': (used / total_value * 100) if total_value else 0,
            'open_positions': len(self.positions),
            'total_trades': 0,
            'position_details': position_details,
            'timestamp': datetime.now(self.ist).isoformat(),
        }

    def get_order_history(self, limit: int = 50) -> List[Dict]:
        """Order history from DB for live mode."""
        if not self.db_manager:
            return []
        orders = self.db_manager.get_orders(trading_mode=self.trading_mode, limit=limit)
        return [{
            'order_id': o.get('order_id'),
            'symbol': o.get('symbol'),
            'order_type': o.get('order_type'),
            'quantity': o.get('quantity'),
            'price': o.get('price'),
            'status': o.get('status'),
            'timestamp': o.get('created_at'),
        } for o in orders]

    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Trade history from DB for live mode."""
        if not self.db_manager:
            return []
        trades = self.db_manager.get_trades(trading_mode=self.trading_mode, limit=limit)
        return [{
            'symbol': t.get('symbol'),
            'entry_price': t.get('entry_price'),
            'exit_price': t.get('exit_price'),
            'quantity': t.get('quantity'),
            'pnl': t.get('pnl'),
            'entry_time': t.get('entry_time'),
            'exit_time': t.get('exit_time'),
        } for t in trades]

    def reset_portfolio(self) -> None:
        """No-op for live (cannot reset real account)."""
        pass
