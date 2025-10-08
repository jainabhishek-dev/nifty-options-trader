#!/usr/bin/env python3
"""
Real-Time Paper Trading Engine
Executes strategies with virtual money using live market data from Kite Connect.
Runs continuously in the background, fully automated.
"""

import logging
import threading
import time
import json
import os
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd

from core.kite_manager import KiteManager
from strategies.strategy_manager import get_strategy_manager, TradingMode, StrategyStatus
from database.supabase_client import DatabaseManager
from config.settings import TradingConfig

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class PositionStatus(Enum):
    """Position status"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PARTIAL = "PARTIAL"

@dataclass
class PaperOrder:
    """Paper trading order"""
    order_id: str
    strategy_name: str
    symbol: str
    transaction_type: str  # BUY/SELL
    quantity: int
    price: float
    order_type: str  # MARKET/LIMIT
    timestamp: datetime
    status: OrderStatus
    execution_price: Optional[float] = None
    execution_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'order_id': self.order_id,
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'transaction_type': self.transaction_type,
            'quantity': self.quantity,
            'price': self.price,
            'order_type': self.order_type,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value,
            'execution_price': self.execution_price,
            'execution_time': self.execution_time.isoformat() if self.execution_time else None
        }

@dataclass
class PaperPosition:
    """Paper trading position"""
    position_id: str
    strategy_name: str
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    entry_time: datetime
    status: PositionStatus
    pnl: float = 0.0
    unrealized_pnl: float = 0.0
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    
    def update_pnl(self, current_price: float):
        """Update PnL based on current market price"""
        self.current_price = current_price
        if self.status == PositionStatus.OPEN:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        elif self.status == PositionStatus.CLOSED and self.exit_price:
            self.pnl = (self.exit_price - self.entry_price) * self.quantity
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'position_id': self.position_id,
            'strategy_name': self.strategy_name,
            'symbol': self.symbol,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'entry_time': self.entry_time.isoformat(),
            'status': self.status.value,
            'pnl': self.pnl,
            'unrealized_pnl': self.unrealized_pnl,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None
        }

class PaperTradingEngine:
    """
    Real-time paper trading engine with live market data
    Executes strategies automatically using virtual money
    """
    
    def __init__(self, kite_manager: KiteManager):
        self.kite_manager = kite_manager
        self.strategy_manager = get_strategy_manager(kite_manager)
        self.db_manager = DatabaseManager()
        
        # Paper trading state
        self.is_running = False
        self.virtual_capital = float(os.environ.get('PAPER_TRADING_CAPITAL', 200000))  # ₹2 Lakhs default
        self.available_capital = self.virtual_capital
        
        # Trading data
        self.orders: Dict[str, PaperOrder] = {}
        self.positions: Dict[str, PaperPosition] = {}
        self.order_counter = 1
        self.position_counter = 1
        
        # Threading
        self.main_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Market hours (IST)
        self.market_open_time = dt_time(9, 15)  # 9:15 AM
        self.market_close_time = dt_time(15, 30)  # 3:30 PM
        
        # Performance tracking
        self.total_pnl = 0.0
        self.daily_pnl = 0.0
        self.winning_trades = 0
        self.losing_trades = 0
        
        logger.info("🎯 Paper Trading Engine initialized with ₹{:,.2f} virtual capital".format(self.virtual_capital))
    
    def start_paper_trading(self) -> bool:
        """Start the paper trading engine in background"""
        try:
            if self.is_running:
                logger.warning("⚠️ Paper trading already running")
                return False
            
            if not self.kite_manager.is_authenticated:
                raise Exception("Kite Connect not authenticated")
            
            # Reset stop event
            self.stop_event.clear()
            
            # Start main trading thread
            self.main_thread = threading.Thread(target=self._main_trading_loop, daemon=False)
            self.main_thread.start()
            
            self.is_running = True
            logger.info("🚀 Paper trading engine started - running in background")
            
            # Save status to database
            self._save_trading_status("ACTIVE")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start paper trading: {e}")
            return False
    
    def stop_paper_trading(self) -> bool:
        """Stop the paper trading engine"""
        try:
            if not self.is_running:
                logger.warning("⚠️ Paper trading not running")
                return False
            
            # Signal stop
            self.stop_event.set()
            
            # Wait for thread to finish (with timeout)
            if self.main_thread and self.main_thread.is_alive():
                self.main_thread.join(timeout=10)
            
            self.is_running = False
            logger.info("⏹️ Paper trading engine stopped")
            
            # Save status to database
            self._save_trading_status("INACTIVE")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to stop paper trading: {e}")
            return False
    
    def _main_trading_loop(self):
        """Main trading loop - runs continuously during market hours"""
        logger.info("📈 Paper trading main loop started")
        
        try:
            while not self.stop_event.is_set():
                try:
                    # Check if market is open
                    if not self._is_market_open():
                        logger.debug("🌙 Market closed - waiting...")
                        time.sleep(60)  # Check every minute
                        continue
                    
                    # Execute one trading cycle
                    self._execute_trading_cycle()
                    
                    # Update positions with current market prices
                    self._update_position_prices()
                    
                    # Save current state
                    self._save_trading_state()
                    
                    # Wait before next cycle (30 seconds for real-time)
                    if not self.stop_event.wait(30):
                        continue
                    else:
                        break
                        
                except Exception as e:
                    logger.error(f"❌ Error in trading loop: {e}")
                    time.sleep(30)  # Wait before retrying
                    
        except KeyboardInterrupt:
            logger.info("🛑 Trading loop interrupted by user")
        except Exception as e:
            logger.error(f"❌ Fatal error in trading loop: {e}")
        finally:
            logger.info("📉 Paper trading main loop ended")
    
    def _execute_trading_cycle(self):
        """Execute one complete trading cycle for all active strategies"""
        try:
            # Get active paper trading strategies
            active_strategies = self.strategy_manager.get_active_strategies_by_mode(TradingMode.PAPER)
            
            if not active_strategies:
                return
            
            logger.debug(f"🔄 Executing trading cycle for {len(active_strategies)} active strategies")
            
            for strategy_name in active_strategies:
                try:
                    strategy_instance = self.strategy_manager.get_strategy_instance(strategy_name)
                    if not strategy_instance:
                        continue
                    
                    # Generate trading signals from strategy
                    signals = strategy_instance.generate_signals()
                    
                    if signals:
                        logger.info(f"📊 Strategy '{strategy_name}' generated {len(signals)} signals")
                        
                        # Execute signals as paper trades
                        for signal in signals:
                            self._execute_paper_signal(strategy_name, signal)
                    
                    # Check exit conditions for existing positions
                    self._check_exit_conditions(strategy_name, strategy_instance)
                    
                except Exception as e:
                    logger.error(f"❌ Error executing strategy '{strategy_name}': {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error in trading cycle: {e}")
    
    def _execute_paper_signal(self, strategy_name: str, signal) -> bool:
        """Execute a trading signal as a paper trade"""
        try:
            # Check if we have sufficient capital
            required_capital = signal.entry_price * signal.quantity
            if required_capital > self.available_capital:
                logger.warning(f"⚠️ Insufficient capital for {strategy_name}: Required ₹{required_capital:,.2f}, Available ₹{self.available_capital:,.2f}")
                return False
            
            # Get current market price for execution
            current_price = self._get_current_market_price(signal.symbol)
            if current_price is None:
                logger.error(f"❌ Could not get current price for {signal.symbol}")
                return False
            
            # Create paper order
            order_id = f"PAPER_{self.order_counter:06d}"
            self.order_counter += 1
            
            paper_order = PaperOrder(
                order_id=order_id,
                strategy_name=strategy_name,
                symbol=signal.symbol,
                transaction_type="BUY",  # Entry is always BUY for strategies
                quantity=signal.quantity,
                price=signal.entry_price,
                order_type="MARKET",
                timestamp=datetime.now(),
                status=OrderStatus.EXECUTED,
                execution_price=current_price,
                execution_time=datetime.now()
            )
            
            # Create paper position
            position_id = f"POS_{self.position_counter:06d}"
            self.position_counter += 1
            
            paper_position = PaperPosition(
                position_id=position_id,
                strategy_name=strategy_name,
                symbol=signal.symbol,
                quantity=signal.quantity,
                entry_price=current_price,
                current_price=current_price,
                entry_time=datetime.now(),
                status=PositionStatus.OPEN
            )
            
            # Update capital
            self.available_capital -= (current_price * signal.quantity)
            
            # Store order and position
            self.orders[order_id] = paper_order
            self.positions[position_id] = paper_position
            
            logger.info(f"✅ Paper trade executed: {strategy_name} - {signal.symbol} x {signal.quantity} @ ₹{current_price:.2f}")
            
            # Save to database
            self._save_paper_trade(paper_order, paper_position)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error executing paper signal: {e}")
            return False
    
    def _check_exit_conditions(self, strategy_name: str, strategy_instance):
        """Check exit conditions for existing positions"""
        try:
            strategy_positions = [pos for pos in self.positions.values() 
                                if pos.strategy_name == strategy_name and pos.status == PositionStatus.OPEN]
            
            for position in strategy_positions:
                # Get current market price
                current_price = self._get_current_market_price(position.symbol)
                if current_price is None:
                    continue
                
                # Update position PnL
                position.update_pnl(current_price)
                
                # Check if strategy wants to exit
                should_exit = strategy_instance.should_exit_position(position.to_dict())
                
                if should_exit:
                    self._execute_paper_exit(position, current_price)
                    
        except Exception as e:
            logger.error(f"❌ Error checking exit conditions for {strategy_name}: {e}")
    
    def _execute_paper_exit(self, position: PaperPosition, exit_price: float) -> bool:
        """Execute position exit as paper trade"""
        try:
            # Create exit order
            order_id = f"PAPER_{self.order_counter:06d}"
            self.order_counter += 1
            
            exit_order = PaperOrder(
                order_id=order_id,
                strategy_name=position.strategy_name,
                symbol=position.symbol,
                transaction_type="SELL",
                quantity=position.quantity,
                price=exit_price,
                order_type="MARKET",
                timestamp=datetime.now(),
                status=OrderStatus.EXECUTED,
                execution_price=exit_price,
                execution_time=datetime.now()
            )
            
            # Close position
            position.status = PositionStatus.CLOSED
            position.exit_price = exit_price
            position.exit_time = datetime.now()
            position.update_pnl(exit_price)
            
            # Update capital and PnL
            self.available_capital += (exit_price * position.quantity)
            trade_pnl = position.pnl
            self.total_pnl += trade_pnl
            self.daily_pnl += trade_pnl
            
            # Track performance
            if trade_pnl > 0:
                self.winning_trades += 1
            else:
                self.losing_trades += 1
            
            # Store exit order
            self.orders[order_id] = exit_order
            
            logger.info(f"✅ Paper exit executed: {position.strategy_name} - {position.symbol} x {position.quantity} @ ₹{exit_price:.2f} | P&L: ₹{trade_pnl:.2f}")
            
            # Update strategy performance
            self.strategy_manager.update_strategy_performance(position.strategy_name, {
                'pnl': trade_pnl,
                'quantity': position.quantity,
                'exit_price': exit_price
            })
            
            # Save to database
            self._save_paper_exit(exit_order, position)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error executing paper exit: {e}")
            return False
    
    def _get_current_market_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol"""
        try:
            # Use KiteManager to get real-time price
            ltp_data = self.kite_manager.ltp([f"NFO:{symbol}"])
            
            price_info = ltp_data.get(f"NFO:{symbol}")
            if price_info and isinstance(price_info, dict):
                return float(price_info.get('last_price', 0))
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting market price for {symbol}: {e}")
            return None
    
    def _update_position_prices(self):
        """Update current prices for all open positions"""
        try:
            open_positions = [pos for pos in self.positions.values() if pos.status == PositionStatus.OPEN]
            
            if not open_positions:
                return
            
            # Get symbols for batch price update
            symbols = list(set([f"NFO:{pos.symbol}" for pos in open_positions]))
            
            # Batch get prices
            ltp_data = self.kite_manager.ltp(symbols)
            
            # Update each position
            for position in open_positions:
                symbol_key = f"NFO:{position.symbol}"
                price_info = ltp_data.get(symbol_key, {})
                
                if isinstance(price_info, dict) and 'last_price' in price_info:
                    current_price = float(price_info['last_price'])
                    position.update_pnl(current_price)
                    
        except Exception as e:
            logger.error(f"❌ Error updating position prices: {e}")
    
    def _is_market_open(self) -> bool:
        """Check if market is currently open"""
        try:
            now = datetime.now()
            current_time = now.time()
            
            # Check if it's a weekday (Monday = 0, Sunday = 6)
            if now.weekday() >= 5:  # Saturday or Sunday
                return False
            
            # Check if current time is within market hours
            return self.market_open_time <= current_time <= self.market_close_time
            
        except Exception as e:
            logger.error(f"❌ Error checking market hours: {e}")
            return False
    
    def get_trading_status(self) -> Dict[str, Any]:
        """Get current paper trading status"""
        return {
            'is_running': self.is_running,
            'virtual_capital': self.virtual_capital,
            'available_capital': self.available_capital,
            'used_capital': self.virtual_capital - self.available_capital,
            'total_pnl': self.total_pnl,
            'daily_pnl': self.daily_pnl,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_trades': self.winning_trades + self.losing_trades,
            'win_rate': (self.winning_trades / max(1, self.winning_trades + self.losing_trades)) * 100,
            'active_positions': len([pos for pos in self.positions.values() if pos.status == PositionStatus.OPEN]),
            'market_open': self._is_market_open(),
            'last_updated': datetime.now().isoformat()
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all positions"""
        return [pos.to_dict() for pos in self.positions.values()]
    
    def get_orders(self) -> List[Dict[str, Any]]:
        """Get all orders"""
        return [order.to_dict() for order in self.orders.values()]
    
    def _save_trading_status(self, status: str):
        """Save trading status to database"""
        try:
            from database.models import SystemEvent
            event = SystemEvent(
                event_type="PAPER_TRADING",
                message=f"Paper trading status changed to {status}",
                details={
                    'status': status,
                    'virtual_capital': self.virtual_capital,
                    'available_capital': self.available_capital,
                    'total_pnl': self.total_pnl
                },
                trading_mode="PAPER"
            )
            self.db_manager.save_event(event)
        except Exception as e:
            logger.error(f"❌ Error saving trading status: {e}")
    
    def _save_paper_trade(self, order: PaperOrder, position: PaperPosition):
        """Save paper trade to database"""
        try:
            from database.models import TradeRecord, PositionRecord
            
            # Save trade record
            trade = TradeRecord(
                symbol=order.symbol,
                action=order.transaction_type,
                quantity=order.quantity,
                price=order.execution_price or order.price,
                status="EXECUTED",
                strategy=order.strategy_name,
                trading_mode="PAPER"
            )
            self.db_manager.save_trade(trade)
            
            # Save position record
            pos_record = PositionRecord(
                symbol=position.symbol,
                quantity=position.quantity,
                average_price=position.entry_price,
                current_price=position.current_price,
                trading_mode="PAPER"
            )
            self.db_manager.save_position(pos_record)
                
        except Exception as e:
            logger.error(f"❌ Error saving paper trade: {e}")
    
    def _save_paper_exit(self, exit_order: PaperOrder, position: PaperPosition):
        """Save paper exit to database"""
        try:
            from database.models import TradeRecord
            
            # Save exit trade
            trade = TradeRecord(
                symbol=exit_order.symbol,
                action=exit_order.transaction_type,
                quantity=exit_order.quantity,
                price=exit_order.execution_price or exit_order.price,
                status="EXECUTED",
                pnl=position.pnl,
                strategy=exit_order.strategy_name,
                trading_mode="PAPER"
            )
            self.db_manager.save_trade(trade)
                
        except Exception as e:
            logger.error(f"❌ Error saving paper exit: {e}")
    
    def _save_trading_state(self):
        """Save current trading state periodically"""
        try:
            # Save state to file for persistence
            state_file = "data/paper_trading_state.json"
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            
            state = {
                'virtual_capital': self.virtual_capital,
                'available_capital': self.available_capital,
                'total_pnl': self.total_pnl,
                'daily_pnl': self.daily_pnl,
                'winning_trades': self.winning_trades,
                'losing_trades': self.losing_trades,
                'order_counter': self.order_counter,
                'position_counter': self.position_counter,
                'last_saved': datetime.now().isoformat()
            }
            
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Error saving trading state: {e}")

# Global paper trading engine instance
_paper_trading_engine: Optional[PaperTradingEngine] = None

def get_paper_trading_engine(kite_manager: Optional[KiteManager] = None) -> PaperTradingEngine:
    """Get or create the global paper trading engine instance"""
    global _paper_trading_engine
    
    if _paper_trading_engine is None:
        if kite_manager is None:
            raise ValueError("KiteManager required for first-time initialization")
        _paper_trading_engine = PaperTradingEngine(kite_manager)
    
    return _paper_trading_engine