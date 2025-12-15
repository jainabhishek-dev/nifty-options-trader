"""
Virtual Order Execution System
==============================

Paper trading execution engine that simulates real order execution:
1. Processes buy/sell orders with realistic delays
2. Simulates market impact and slippage
3. Tracks virtual positions and P&L
4. Provides order book and trade history
5. Enforces risk limits and margin requirements
"""

import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import pytz

from strategies import TradingSignal, SignalType, Position


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"


@dataclass
class VirtualOrder:
    """Virtual order for paper trading"""
    order_id: str
    symbol: str
    signal_type: SignalType
    quantity: int
    order_type: OrderType
    price: float
    status: OrderStatus
    timestamp: datetime
    filled_quantity: int = 0
    filled_price: float = 0.0
    filled_timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        """Convert order to dictionary for JSON serialization"""
        data = asdict(self)
        data['signal_type'] = self.signal_type.value
        data['order_type'] = self.order_type.value
        data['status'] = self.status.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.filled_timestamp:
            data['filled_timestamp'] = self.filled_timestamp.isoformat()
        return data


@dataclass
class VirtualTrade:
    """Record of executed trade"""
    trade_id: str
    order_id: str
    symbol: str
    signal_type: SignalType
    quantity: int
    price: float
    timestamp: datetime
    fees: float = 0.0
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict:
        """Convert trade to dictionary"""
        data = asdict(self)
        data['signal_type'] = self.signal_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


class VirtualOrderExecutor:
    """
    Virtual order execution system for paper trading
    
    Features:
    - Realistic order execution with simulated delays
    - Market impact and slippage modeling
    - Position tracking and P&L calculation
    - Risk management and margin checks
    - Order history and trade logging
    """
    
    def __init__(self, initial_capital: float = 200000.0, db_manager=None, kite_manager=None):
        self.initial_capital = initial_capital
        self.available_capital = initial_capital
        self.used_margin = 0.0
        self.db_manager = db_manager  # Database manager for persistence
        self.kite_manager = kite_manager  # KiteManager for real price fetching
        
        # Data storage - Start empty, will be populated from database
        self.orders: Dict[str, VirtualOrder] = {}
        self.trades: Dict[str, VirtualTrade] = {}
        self.positions: Dict[str, Position] = {}
        
        # Execution settings
        self.slippage_bps = 2  # 2 basis points slippage
        self.execution_delay_ms = 100  # 100ms execution delay
        self.brokerage_per_lot = 20.0  # ₹20 per lot
        
        # Risk limits
        self.max_positions = 10  # Maximum open positions
        self.max_single_position_size = 50000.0  # ₹50,000 per position
        
        # IST timezone
        self.ist = pytz.timezone('Asia/Kolkata')
        
        # 🚀 CRITICAL FIX: Load existing open positions from database on startup
        self._recover_positions_from_database()
        
        # 🚀 CRITICAL FIX: Load existing open positions from database on startup
        self._recover_positions_from_database()
    
    def _recover_positions_from_database(self):
        """Recovery mechanism: Load open positions from database into memory on startup"""
        if not self.db_manager:
            print("WARNING: No database manager - skipping position recovery")
            return
            
        try:
            print("Starting position recovery from database...")
            
            # Get all open positions from database
            open_positions = self.db_manager.supabase.table('positions').select('*').eq('trading_mode', 'paper').eq('is_open', True).execute()
            
            recovered_count = 0
            for pos_data in open_positions.data:
                try:
                    # Reconstruct Position object from database data
                    symbol = pos_data['symbol']
                    entry_time = datetime.fromisoformat(pos_data['entry_time'].replace('Z', '+00:00'))
                    
                    # Determine signal type from symbol (CE = CALL, PE = PUT)
                    if symbol.endswith('CE'):
                        signal_type = SignalType.BUY_CALL
                    elif symbol.endswith('PE'):
                        signal_type = SignalType.BUY_PUT
                    else:
                        print(f"WARNING: Unknown option type for {symbol}, skipping")
                        continue
                    
                    # Create Position object with database linkage
                    position = Position(
                        symbol=symbol,
                        signal_type=signal_type,
                        quantity=pos_data['quantity'],
                        entry_price=pos_data['average_price'],
                        entry_time=entry_time,
                        is_closed=False,  # It's open
                        last_update=datetime.fromisoformat(pos_data['updated_at'].replace('Z', '+00:00')),
                        metadata={
                            'strategy': pos_data.get('strategy_name', 'unknown'),
                            'position_id': pos_data['id'],  # Critical: Link to database position ID
                            'original_quantity': pos_data['quantity'],
                            'entry_order_saved': True  # Position was already created, so entry order exists
                        }
                    )
                    
                    # Add to in-memory positions
                    self.positions[symbol] = position
                    recovered_count += 1
                    
                    print(f"SUCCESS: Recovered position: {symbol} (Qty: {pos_data['quantity']}, Entry: Rs.{pos_data['average_price']:.2f})")
                    
                except Exception as e:
                    print(f"ERROR: Failed to recover position {pos_data.get('symbol', 'unknown')}: {e}")
            
            print(f"Position recovery complete: {recovered_count} positions loaded into memory")
            
            if recovered_count > 0:
                print(f"In-memory positions: {list(self.positions.keys())}")
                print(f"Force exit mechanism now operational for recovered positions")
            
        except Exception as e:
            print(f"CRITICAL: Position recovery failed: {e}")
            print("WARNING: Force exit may not work properly until positions are recreated")
    
    def place_order(self, signal: TradingSignal, current_market_price: float) -> str:
        """
        Place a virtual order based on trading signal
        
        Args:
            signal: Trading signal from strategy
            current_market_price: Current market price of the option
            
        Returns:
            Order ID if successful, empty string if rejected
        """
        try:
            # Validate signal and market price
            if not self._validate_order(signal, current_market_price):
                return ""
            
            # Generate order ID
            order_id = str(uuid.uuid4())
            
            # Calculate execution price with slippage
            execution_price = self._calculate_execution_price(
                current_market_price, signal.signal_type
            )
            
            # Create virtual order
            order = VirtualOrder(
                order_id=order_id,
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                quantity=signal.quantity,
                order_type=OrderType.MARKET,  # For now, all orders are market orders
                price=execution_price,
                status=OrderStatus.PENDING,
                timestamp=datetime.now(self.ist),
                metadata={
                    **(signal.metadata.copy() if signal.metadata else {}),
                    'confidence': signal.confidence  # Ensure confidence is always included
                }
            )
            
            # Store order
            self.orders[order_id] = order
            
            # Execute immediately (simulating market order)
            self._execute_order(order_id, execution_price)
            
            return order_id
            
        except Exception as e:
            print(f"Error placing order: {e}")
            return ""
    
    def _validate_order(self, signal: TradingSignal, market_price: float) -> bool:
        """Validate order before placement"""
        try:
            # Check if market price is valid
            if market_price <= 0:
                print("Invalid market price")
                return False
            
            # Check position limits
            if len(self.positions) >= self.max_positions:
                print("Maximum positions limit reached")
                return False
            
            # Calculate required capital
            required_capital = market_price * signal.quantity
            
            # Check single position size limit
            if required_capital > self.max_single_position_size:
                print(f"Position size too large: ₹{required_capital:,.0f}")
                return False
            
            # Check available capital
            if required_capital > self.available_capital:
                print(f"Insufficient capital. Required: ₹{required_capital:,.0f}, Available: ₹{self.available_capital:,.0f}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating order: {e}")
            return False
    
    def _calculate_execution_price(self, market_price: float, signal_type: SignalType) -> float:
        """Calculate execution price with slippage"""
        try:
            # Apply slippage based on order direction
            slippage_factor = self.slippage_bps / 10000.0
            
            if signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
                # Buying - price goes against us
                execution_price = market_price * (1 + slippage_factor)
            else:
                # Selling - price goes against us  
                execution_price = market_price * (1 - slippage_factor)
            
            return round(execution_price, 2)
            
        except Exception as e:
            print(f"Error calculating execution price: {e}")
            return market_price
    
    def _execute_order(self, order_id: str, execution_price: float) -> bool:
        """Execute a pending order"""
        try:
            if order_id not in self.orders:
                return False
            
            order = self.orders[order_id]
            
            # Calculate total cost including fees
            trade_value = execution_price * order.quantity
            fees = self.brokerage_per_lot
            total_cost = trade_value + fees
            
            # Check capital availability again
            if total_cost > self.available_capital:
                order.status = OrderStatus.REJECTED
                print(f"Order {order_id} rejected - insufficient capital")
                return False
            
            # Execute the order
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            order.filled_price = execution_price
            order.filled_timestamp = datetime.now(self.ist)
            
            # Save order to database - CRITICAL: Ensure all orders are permanently saved
            if self.db_manager:
                print(f"🔄 Attempting to save order: {order.signal_type.value} {order.symbol}")
                try:
                    # Ensure metadata exists
                    if not order.metadata:
                        order.metadata = {}
                    
                    order_data = {
                        'strategy_name': order.metadata.get('strategy', 'unknown'),
                        'trading_mode': 'paper',
                        'symbol': order.symbol,
                        'order_type': 'BUY' if order.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT] else 'SELL',
                        'quantity': order.quantity,
                        'price': execution_price,
                        'order_id': order_id,  # This must be unique for each order
                        'status': 'COMPLETE',
                        'filled_quantity': order.quantity,
                        'filled_price': execution_price,
                        'signal_data': {
                            **order.metadata,
                            'original_signal_type': order.signal_type.value,  # Preserve original signal type
                            'execution_timestamp': order.filled_timestamp.isoformat() if order.filled_timestamp else None,
                            'is_closing_order': order.metadata.get('is_closing_order', False)
                        }
                    }
                    
                    print(f"📊 Order data prepared: {order_data['order_type']} {order_data['symbol']}")
                    
                    saved_order_id = self.db_manager.save_order(order_data)
                    
                    if saved_order_id:
                        print(f"✅ Order SUCCESSFULLY saved to DB: {order_data['order_type']} {order.symbol} (ID: {saved_order_id})")
                    else:
                        print(f"❌ Order save returned None: {order_data['order_type']} {order.symbol}")
                        print(f"   Order data attempted: {order_data}")
                        
                except Exception as e:
                    print(f"❌ CRITICAL ERROR: Exception during order save: {e}")
                    print(f"   Signal type: {order.signal_type.value}")
                    print(f"   Symbol: {order.symbol}")
                    print(f"   Metadata: {order.metadata}")
                    try:
                        print(f"   Order data that failed: {order_data}")
                    except:
                        print(f"   Could not display order_data due to creation failure")
                    # Don't continue execution if order save fails for opening orders
                    if order.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
                        print(f"   🚨 STOPPING EXECUTION - Opening order save failed")
                        return False
            else:
                print(f"⚠️  No database manager available - order not saved: {order.symbol}")
            
            # Create trade record
            trade_id = str(uuid.uuid4())
            trade = VirtualTrade(
                trade_id=trade_id,
                order_id=order_id,
                symbol=order.symbol,
                signal_type=order.signal_type,
                quantity=order.quantity,
                price=execution_price,
                timestamp=order.filled_timestamp,
                fees=fees,
                metadata=order.metadata
            )
            
            self.trades[trade_id] = trade
            
            # Update positions
            self._update_position(order, trade)
            
            # Update capital
            self.available_capital -= total_cost
            self.used_margin += total_cost
            
            print(f"Order executed: {order.symbol} @ ₹{execution_price} (Qty: {order.quantity})")
            return True
            
        except Exception as e:
            print(f"Error executing order {order_id}: {e}")
            return False
    
    def _update_position(self, order: VirtualOrder, trade: VirtualTrade):
        """Update position and save to database"""
        """Update position based on executed trade"""
        try:
            symbol = order.symbol
            
            if symbol in self.positions:
                # Update existing position
                position = self.positions[symbol]
                
                if order.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
                    # Adding to position (or opening new)
                    total_cost = (position.quantity * position.entry_price) + (trade.quantity * trade.price)
                    total_quantity = position.quantity + trade.quantity
                    position.entry_price = total_cost / total_quantity
                    position.quantity = total_quantity
                    position.last_update = trade.timestamp
                else:
                    # Selling/closing position
                    original_quantity = position.quantity  # Store original quantity before modification
                    position.quantity -= trade.quantity
                    position.last_update = trade.timestamp
                    
                    # POSITION MEMORY FIX: Mark as closed but don't delete from memory immediately
                    # This preserves position tracking and prevents orphaned orders
                    if position.quantity <= 0:
                        # Mark position as closed instead of deleting it
                        position.is_closed = True
                        position.close_time = trade.timestamp
                        position.close_price = trade.price
                        
                        # Update database with closed position including exit reason
                        if self.db_manager:
                            try:
                                # Calculate final P&L using original quantity to avoid division by zero
                                pnl = (trade.price - position.entry_price) * original_quantity
                                pnl_percent = (pnl / (position.entry_price * original_quantity))  # Store as decimal, not percentage
                                
                                # Update the existing position instead of creating a new one
                                position_update_data = {
                                    'quantity': 0,  # Position fully closed
                                    'current_price': trade.price,
                                    'unrealized_pnl': 0.0,
                                    'realized_pnl': pnl,
                                    'pnl_percent': pnl_percent,
                                    'is_open': False,
                                    'exit_time': trade.timestamp.isoformat(),
                                    'exit_price': trade.price,
                                    'exit_reason': trade.metadata.get('reason', 'Unknown') if trade.metadata else 'Unknown',
                                    'exit_reason_category': trade.metadata.get('exit_reason_category', 'OTHER') if trade.metadata else 'OTHER'
                                }
                                
                                # Find and update the existing open position
                                existing_positions = self.db_manager.supabase.table('positions').select('id').eq('symbol', symbol).eq('trading_mode', 'paper').eq('is_open', True).execute()
                                
                                if existing_positions.data:
                                    position_id = existing_positions.data[0]['id']
                                    self.db_manager.supabase.table('positions').update(position_update_data).eq('id', position_id).execute()
                                    print(f"✅ Position closed and updated in database: {symbol} (P&L: {pnl_percent*100:+.2f}%)")
                                else:
                                    print(f"⚠️  No open position found to update for {symbol}")
                            except Exception as e:
                                print(f"Warning: Failed to update closed position in database: {e}")
                        
                        # Keep position in memory for reference but mark it as closed
                        # Don't delete: del self.positions[symbol]  
                        print(f"Position {symbol} marked as closed (kept in memory for tracking)")
            else:
                # Create new position (only for buy signals)
                if order.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
                    position = Position(
                        symbol=symbol,
                        signal_type=order.signal_type,
                        quantity=trade.quantity,
                        entry_price=trade.price,
                        entry_time=trade.timestamp,
                        last_update=trade.timestamp,
                        metadata={
                            'strategy': trade.metadata.get('strategy', 'unknown') if trade.metadata else 'unknown',
                            'strike_price': order.metadata.get('underlying_price') if order.metadata else None,
                            'original_quantity': trade.quantity  # Store original quantity for closing
                        }
                    )
                    self.positions[symbol] = position
                    
                    # 🚀 ATOMIC OPERATION: Save new position to database (linked to BUY order)
                    if self.db_manager:
                        try:
                            position_data = {
                                'strategy_name': trade.metadata.get('strategy', 'unknown'),
                                'trading_mode': 'paper',
                                'symbol': symbol,
                                'quantity': trade.quantity,
                                'average_price': trade.price,
                                'current_price': trade.price,
                                'unrealized_pnl': 0.0,
                                'is_open': True,
                                'entry_time': trade.timestamp.isoformat()
                            }
                            
                            position_id = self.db_manager.save_position(position_data)
                            if position_id:
                                # Link the position ID to the in-memory position for future reference
                                position.metadata['position_id'] = position_id
                                position.metadata['entry_order_saved'] = True
                                print(f"✅ Position created and linked: {symbol} (DB ID: {position_id})")
                            else:
                                print(f"❌ CRITICAL: Position save failed for {symbol} - may cause data inconsistency")
                                
                        except Exception as e:
                            print(f"❌ CRITICAL: Failed to save position to database: {e}")
                            print(f"⚠️ Position {symbol} exists in memory but not in database - force exit may fail")
            
        except Exception as e:
            print(f"Error updating position: {e}")
    
    def close_position(self, symbol: str, current_price: float, reason: str = "Manual close", exit_reason_category: str = "MANUAL") -> bool:
        """
        Close an open position at current market price
        
        Args:
            symbol: Symbol to close
            current_price: Current market price
            reason: Reason for closing
            
        Returns:
            True if successful
        """
        try:
            if symbol not in self.positions:
                print(f"No position found for {symbol}")
                return False
            
            position = self.positions[symbol]
            
            # Prevent closing already closed positions
            if position.is_closed:
                print(f"Position {symbol} is already closed")
                return True
            
            # Create close order
            close_signal_type = SignalType.SELL_CALL if position.signal_type == SignalType.BUY_CALL else SignalType.SELL_PUT
            
            # Create a dummy signal for closing - preserve original strategy name
            original_strategy = position.metadata.get('strategy', 'unknown') if position.metadata else 'unknown'
            
            class CloseSignal:
                def __init__(self):
                    self.symbol = symbol
                    self.signal_type = close_signal_type
                    # Use stored original quantity from metadata or current quantity if position is still open
                    self.quantity = position.metadata.get('original_quantity', position.quantity) if position.metadata else position.quantity
                    # Ensure quantity is never 0
                    if self.quantity <= 0:
                        self.quantity = 1  # Fallback to 1 to avoid database constraint violation
                    self.confidence = 1.0
                    # CRITICAL FIX: Use original strategy name, not 'close'
                    self.metadata = {
                        'reason': reason, 
                        'exit_reason_category': exit_reason_category,
                        'strategy': original_strategy,  # Preserve original strategy
                        'is_closing_order': True,  # Mark as closing order
                        'original_entry_price': position.entry_price,
                        'original_entry_time': position.entry_time.isoformat() if hasattr(position.entry_time, 'isoformat') else str(position.entry_time)
                    }
            
            # Place close order - this creates a SEPARATE SELL order
            close_signal = CloseSignal()
            close_order_id = self.place_order(close_signal, current_price)
            
            if close_order_id:
                print(f"✅ Position closed: {symbol} @ ₹{current_price} - {reason}")
                print(f"   📝 SELL order created (ID: {close_order_id}) - BUY order preserved in database")
                return True
            else:
                print(f"❌ Failed to close position: {symbol}")
                return False
                
        except Exception as e:
            print(f"Error closing position {symbol}: {e}")
            return False
    
    def _get_current_price(self, symbol: str, fallback_price: float) -> float:
        """Get real current market price for a symbol"""
        try:
            if self.kite_manager and self.kite_manager.is_authenticated:
                nfo_symbol = f"NFO:{symbol}"
                ltp_data = self.kite_manager.ltp([nfo_symbol])
                if ltp_data and nfo_symbol in ltp_data:
                    return float(ltp_data[nfo_symbol].get('last_price', fallback_price))
            # Fallback to entry price if KiteManager unavailable
            return fallback_price
        except Exception as e:
            print(f"Error fetching current price for {symbol}: {e}")
            return fallback_price

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Get comprehensive portfolio summary"""
        try:
            total_value = self.available_capital
            total_pnl = 0.0
            open_positions = len(self.positions)
            
            # Calculate position values using real current market prices
            position_details = []
            for symbol, position in self.positions.items():
                # Get real current price from KiteManager
                current_price = self._get_current_price(symbol, position.entry_price)
                position_value = current_price * position.quantity
                pnl = (current_price - position.entry_price) * position.quantity
                pnl_pct = (pnl / (position.entry_price * position.quantity)) * 100
                
                total_value += position_value
                total_pnl += pnl
                
                position_details.append({
                    'symbol': symbol,
                    'quantity': position.quantity,
                    'entry_price': position.entry_price,
                    'current_price': current_price,
                    'position_value': position_value,
                    'pnl': pnl,
                    'pnl_percent': pnl_pct,
                    'entry_time': position.entry_time.isoformat(),
                    'strategy': position.metadata.get('strategy', 'unknown') if position.metadata else 'unknown'
                })
            
            # Calculate overall metrics
            total_pnl_pct = (total_pnl / self.initial_capital) * 100
            used_capital = self.initial_capital - self.available_capital
            utilization_pct = (used_capital / self.initial_capital) * 100
            
            return {
                'initial_capital': self.initial_capital,
                'available_capital': self.available_capital,
                'used_capital': used_capital,
                'total_value': total_value,
                'total_pnl': total_pnl,
                'total_pnl_percent': total_pnl_pct,
                'utilization_percent': utilization_pct,
                'open_positions': open_positions,
                'total_trades': len(self.trades),
                'position_details': position_details,
                'timestamp': datetime.now(self.ist).isoformat()
            }
            
        except Exception as e:
            print(f"Error getting portfolio summary: {e}")
            return {
                'initial_capital': self.initial_capital,
                'available_capital': self.available_capital,
                'error': str(e),
                'timestamp': datetime.now(self.ist).isoformat()
            }
    
    def get_order_history(self, limit: int = 50) -> List[Dict]:
        """Get recent order history"""
        try:
            orders = list(self.orders.values())
            orders.sort(key=lambda x: x.timestamp, reverse=True)
            
            return [order.to_dict() for order in orders[:limit]]
            
        except Exception as e:
            print(f"Error getting order history: {e}")
            return []
    
    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get recent trade history"""
        try:
            trades = list(self.trades.values())
            trades.sort(key=lambda x: x.timestamp, reverse=True)
            
            return [trade.to_dict() for trade in trades[:limit]]
            
        except Exception as e:
            print(f"Error getting trade history: {e}")
            return []
    
    def reset_portfolio(self) -> None:
        """Reset portfolio to initial state (for testing)"""
        try:
            self.available_capital = self.initial_capital
            self.used_margin = 0.0
            self.orders.clear()
            self.trades.clear()
            self.positions.clear()
            print("Portfolio reset to initial state")
            
        except Exception as e:
            print(f"Error resetting portfolio: {e}")
    
    def save_data(self, filepath: str) -> bool:
        """Save portfolio data to JSON file"""
        try:
            data = {
                'initial_capital': self.initial_capital,
                'available_capital': self.available_capital,
                'used_margin': self.used_margin,
                'orders': [order.to_dict() for order in self.orders.values()],
                'trades': [trade.to_dict() for trade in self.trades.values()],
                'positions': [pos.to_dict() for pos in self.positions.values()],
                'timestamp': datetime.now(self.ist).isoformat()
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Error saving data: {e}")
            return False
    
    def get_complete_order_history(self, symbol: str = None) -> List[Dict[str, Any]]:
        """
        Get complete order history from database showing full BUY->SELL lifecycle
        
        Args:
            symbol: Optional symbol filter, if None returns all orders
            
        Returns:
            List of orders sorted by creation time
        """
        try:
            if not self.db_manager:
                return []
                
            # Get all paper trading orders
            orders = self.db_manager.get_orders(trading_mode='paper', limit=1000)
            
            if symbol:
                orders = [order for order in orders if order.get('symbol') == symbol]
                
            # Sort by creation time for proper chronological order
            orders.sort(key=lambda x: x.get('created_at', ''))
            
            return orders
            
        except Exception as e:
            print(f"Error getting order history: {e}")
            return []
    
    def get_trade_pairs(self) -> List[Dict[str, Any]]:
        """
        Analyze orders to identify BUY->SELL trade pairs
        
        Returns:
            List of trade pairs with entry and exit orders
        """
        try:
            orders = self.get_complete_order_history()
            trade_pairs = []
            
            # Group orders by symbol and strategy
            symbol_orders = {}
            for order in orders:
                symbol = order.get('symbol')
                strategy = order.get('strategy_name')
                key = f"{symbol}_{strategy}"
                
                if key not in symbol_orders:
                    symbol_orders[key] = []
                symbol_orders[key].append(order)
            
            # Match BUY and SELL orders for each symbol/strategy combination
            for key, order_list in symbol_orders.items():
                buy_orders = [o for o in order_list if o.get('order_type') == 'BUY']
                sell_orders = [o for o in order_list if o.get('order_type') == 'SELL']
                
                # Create trade pairs
                for i, buy_order in enumerate(buy_orders):
                    if i < len(sell_orders):
                        trade_pairs.append({
                            'symbol': key.split('_')[0],
                            'strategy': key.split('_', 1)[1],
                            'entry_order': buy_order,
                            'exit_order': sell_orders[i],
                            'pnl': (sell_orders[i].get('filled_price', 0) - buy_order.get('filled_price', 0)) * buy_order.get('quantity', 0)
                        })
            
            return trade_pairs
            
        except Exception as e:
            print(f"Error analyzing trade pairs: {e}")
            return []
    
    def verify_order_integrity(self) -> Dict[str, Any]:
        """
        Verify that both BUY and SELL orders are properly saved to database
        
        Returns:
            Dictionary with integrity check results
        """
        try:
            if not self.db_manager:
                return {'error': 'No database manager available'}
                
            # Get recent orders from database
            recent_orders = self.db_manager.get_orders(trading_mode='paper', limit=50)
            
            buy_orders = [o for o in recent_orders if o['order_type'] == 'BUY']
            sell_orders = [o for o in recent_orders if o['order_type'] == 'SELL']
            
            # Analyze order patterns
            result = {
                'total_orders': len(recent_orders),
                'buy_orders': len(buy_orders),
                'sell_orders': len(sell_orders),
                'buy_sell_ratio': len(buy_orders) / max(len(sell_orders), 1),
                'strategies': {},
                'integrity_status': 'GOOD' if len(buy_orders) > 0 else 'ISSUE_DETECTED'
            }
            
            # Group by strategy
            for order in recent_orders:
                strategy = order['strategy_name']
                order_type = order['order_type']
                if strategy not in result['strategies']:
                    result['strategies'][strategy] = {'BUY': 0, 'SELL': 0}
                result['strategies'][strategy][order_type] += 1
            
            return result
            
        except Exception as e:
            return {'error': f'Failed to verify order integrity: {e}'}
    
    def load_data(self, filepath: str) -> bool:
        """Load portfolio data from JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self.initial_capital = data.get('initial_capital', 200000.0)
            self.available_capital = data.get('available_capital', 200000.0)
            self.used_margin = data.get('used_margin', 0.0)
            
            # TODO: Reload orders, trades, and positions from data
            # This would require proper deserialization
            
            return True
            
        except Exception as e:
            print(f"Error loading data: {e}")
            return False