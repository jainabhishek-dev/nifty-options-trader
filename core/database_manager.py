"""
Database Manager for Options Trading Platform
Handles all database operations using Supabase
"""

import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import asdict
import numpy as np
from supabase import create_client, Client
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages all database operations for the trading platform"""
    
    def _sanitize_for_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize data to prevent JSON serialization errors with NaN values"""
        def clean_value(value):
            if isinstance(value, (np.floating, float)) and np.isnan(value):
                return None
            elif isinstance(value, np.integer):
                return int(value)
            elif isinstance(value, np.floating):
                return float(value)
            elif isinstance(value, dict):
                return {k: clean_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [clean_value(item) for item in value]
            return value
        
        return {key: clean_value(value) for key, value in data.items()}
    
    def __init__(self):
        """Initialize Supabase client"""
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            logger.error("Supabase credentials not found in environment variables")
            raise ValueError("Missing Supabase credentials. Please set SUPABASE_URL and SUPABASE_ANON_KEY")
        
        try:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info("Connected to Supabase successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            # Test with a simple query to strategies table
            result = self.supabase.table('strategies').select('*').limit(1).execute()
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    # Strategy Management
    def save_strategy_config(self, strategy_name: str, config: Dict[str, Any], is_active: bool = True) -> bool:
        """Save or update strategy configuration"""
        try:
            strategy_data = {
                'name': strategy_name,
                'config': json.dumps(config),
                'is_active': is_active,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Check if strategy exists
            existing = self.supabase.table('strategies').select('*').eq('name', strategy_name).execute()
            
            if existing.data:
                # Update existing
                result = self.supabase.table('strategies').update(strategy_data).eq('name', strategy_name).execute()
            else:
                # Insert new
                strategy_data['created_at'] = datetime.now(timezone.utc).isoformat()
                result = self.supabase.table('strategies').insert(strategy_data).execute()
            
            logger.info(f"Strategy config saved: {strategy_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save strategy config: {e}")
            return False
    
    def get_strategy_config(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Get strategy configuration"""
        try:
            result = self.supabase.table('strategies').select('*').eq('name', strategy_name).eq('is_active', True).execute()
            
            if result.data:
                config_json = result.data[0]['config']
                return json.loads(config_json)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get strategy config: {e}")
            return None
    
    def get_all_active_strategies(self) -> List[Dict[str, Any]]:
        """Get all active strategies"""
        try:
            result = self.supabase.table('strategies').select('*').eq('is_active', True).execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to get active strategies: {e}")
            return []
    
    # Order Management
    def save_order(self, order_data: Dict[str, Any]) -> Optional[str]:
        """Save order to database - ENHANCED: Validation to prevent orphaned orders"""
        try:
            # CRITICAL VALIDATION: Prevent orphaned SELL orders
            if order_data.get('order_type') == 'SELL':
                symbol = order_data.get('symbol')
                quantity = order_data.get('quantity', 0)
                trading_mode = order_data.get('trading_mode', 'paper')
                
                if symbol:
                    # Check for existing open position before allowing SELL
                    open_positions = self.supabase.table('positions').select('quantity').eq('symbol', symbol).eq('trading_mode', trading_mode).eq('is_open', True).execute()
                    
                    if not open_positions.data:
                        logger.error(f"VALIDATION FAILED: Cannot save SELL order for {symbol} - no open position exists")
                        logger.error(f"This would create an orphaned SELL order (impossible in real trading)")
                        return None
                    
                    # Check if sufficient quantity exists
                    available_quantity = sum(pos['quantity'] for pos in open_positions.data)
                    if available_quantity < quantity:
                        logger.error(f"VALIDATION FAILED: Insufficient position quantity for SELL order")
                        logger.error(f"Available: {available_quantity}, Requested: {quantity}")
                        return None
            
            # VALIDATION: Ensure required fields exist
            required_fields = ['symbol', 'order_type', 'quantity', 'price', 'trading_mode']
            missing_fields = [field for field in required_fields if not order_data.get(field)]
            if missing_fields:
                logger.error(f"Cannot save order - missing required fields: {missing_fields}")
                return None
            
            # Add timestamps
            order_data['created_at'] = datetime.now(timezone.utc).isoformat()
            order_data['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Sanitize data to prevent JSON serialization errors
            sanitized_data = self._sanitize_for_json(order_data)
            
            result = self.supabase.table('orders').insert(sanitized_data).execute()
            
            if result.data:
                order_id = result.data[0]['id']
                logger.info(f"Order saved with validation: {order_data['order_type']} {order_data['symbol']} (ID: {order_id})")
                return order_id
            return None
            
        except Exception as e:
            logger.error(f"Failed to save order: {e}")
            return None
    
    def update_order_status(self, order_id: str, status: str, filled_quantity: int = None, 
                           filled_price: float = None) -> bool:
        """Update order status"""
        try:
            update_data = {
                'status': status,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            if filled_quantity is not None:
                update_data['filled_quantity'] = filled_quantity
            if filled_price is not None:
                update_data['filled_price'] = filled_price
            
            result = self.supabase.table('orders').update(update_data).eq('id', order_id).execute()
            
            logger.info(f"Order {order_id} status updated to {status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update order status: {e}")
            return False
    
    def get_orders(self, strategy_name: str = None, status: str = None, 
                   trading_mode: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get orders with optional filters"""
        try:
            query = self.supabase.table('orders').select('*')
            
            if strategy_name:
                query = query.eq('strategy_name', strategy_name)
            if status:
                query = query.eq('status', status)
            if trading_mode:
                query = query.eq('trading_mode', trading_mode)
            
            result = query.order('created_at', desc=True).limit(limit).execute()
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    # Position Management
    def save_position(self, position_data: Dict[str, Any]) -> Optional[str]:
        """Save or update position - ENHANCED: Strict duplicate prevention and validation"""
        try:
            symbol = position_data.get('symbol')
            trading_mode = position_data.get('trading_mode', 'paper')
            
            if not symbol:
                logger.error("Cannot save position without symbol")
                return None
            
            position_data['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            # Check if this is an update to an existing position (has id) or a new position
            if 'id' in position_data and position_data['id']:
                # Update existing position by ID
                result = self.supabase.table('positions').update(position_data).eq('id', position_data['id']).execute()
                logger.info(f"Position updated: {position_data['symbol']} (ID: {position_data['id']})")
                return position_data['id']
            else:
                # FIXED: Simplified duplicate prevention (removed unique_key dependency)
                if position_data.get('is_open', False):
                    # Check for existing open position with same symbol and trading mode
                    existing = self.supabase.table('positions').select('id').eq('symbol', symbol).eq('trading_mode', trading_mode).eq('is_open', True).execute()
                    
                    if existing.data:
                        # ALLOW multiple positions for same symbol (per your requirement)
                        # Each BUY order should create separate position
                        logger.info(f"Multiple positions allowed for {symbol} - creating new position")
                
                # VALIDATION: Ensure core required fields for new positions
                if position_data.get('is_open', False):
                    required_fields = ['entry_time', 'quantity', 'average_price']
                    missing_fields = [field for field in required_fields if not position_data.get(field)]
                    if missing_fields:
                        logger.error(f"Cannot create position - missing required fields: {missing_fields}")
                        return None
                
                # Create new position with validation passed
                position_data['created_at'] = datetime.now(timezone.utc).isoformat()
                result = self.supabase.table('positions').insert(position_data).execute()
                
                if result.data:
                    position_id = result.data[0]['id']
                    logger.info(f"✅ Position created successfully: {position_data['symbol']} (ID: {position_id})")
                    logger.info(f"✅ Position details: Qty={position_data['quantity']}, Price={position_data['average_price']}, Open={position_data['is_open']}")
                    return position_id
                else:
                    logger.error(f"❌ Position creation returned no data for {position_data['symbol']}")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to save position: {e}")
            return None

    def update_position_price(self, position_id: str, current_price: float) -> bool:
        """Update position with current market price and recalculate P&L"""
        try:
            # Get existing position to calculate P&L
            existing = self.supabase.table('positions').select('*').eq('id', position_id).execute()
            
            if not existing.data:
                logger.error(f"Position not found: {position_id}")
                return False
                
            position = existing.data[0]
            entry_price = float(position['average_price'])
            quantity = int(position['quantity'])
            
            # Calculate unrealized P&L
            unrealized_pnl = (current_price - entry_price) * quantity
            pnl_percent = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            
            # Update position with current price and P&L
            update_data = {
                'current_price': current_price,
                'unrealized_pnl': unrealized_pnl,
                'pnl_percent': pnl_percent,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = self.supabase.table('positions').update(update_data).eq('id', position_id).execute()
            return True
            
        except Exception as e:
            logger.error(f"Failed to update position price: {e}")
            return False

    def update_positions_live_data(self, symbol_prices: Dict[str, float]) -> int:
        """Update current prices for all open positions"""
        try:
            # Get all open positions
            open_positions = self.supabase.table('positions').select('*').eq('is_open', True).execute()
            
            if not open_positions.data:
                return 0
                
            updated_count = 0
            for position in open_positions.data:
                symbol = position['symbol']
                if symbol in symbol_prices:
                    if self.update_position_price(position['id'], symbol_prices[symbol]):
                        updated_count += 1
                        
            logger.info(f"Updated {updated_count} positions with live prices")
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to update positions live data: {e}")
            return 0
    
    def get_positions(self, strategy_name: str = None, trading_mode: str = None, 
                     is_open: bool = None) -> List[Dict[str, Any]]:
        """Get positions with optional filters"""
        try:
            query = self.supabase.table('positions').select('*')
            
            if strategy_name:
                query = query.eq('strategy_name', strategy_name)
            if trading_mode:
                query = query.eq('trading_mode', trading_mode)
            if is_open is not None:
                query = query.eq('is_open', is_open)
            
            result = query.order('created_at', desc=True).execute()
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    # Trade Management
    def save_trade(self, trade_data: Dict[str, Any]) -> Optional[str]:
        """Save completed trade"""
        try:
            # Add timestamps
            trade_data['created_at'] = datetime.now(timezone.utc).isoformat()
            
            result = self.supabase.table('trades').insert(trade_data).execute()
            
            if result.data:
                trade_id = result.data[0]['id']
                logger.info(f"Trade saved with ID: {trade_id}")
                return trade_id
            return None
            
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")
            return None
    
    def get_trades(self, strategy_name: str = None, trading_mode: str = None, 
                   date_from: datetime = None, date_to: datetime = None, 
                   limit: int = 100) -> List[Dict[str, Any]]:
        """Get trades with optional filters"""
        try:
            query = self.supabase.table('trades').select('*')
            
            if strategy_name:
                query = query.eq('strategy_name', strategy_name)
            if trading_mode:
                query = query.eq('trading_mode', trading_mode)
            if date_from:
                query = query.gte('entry_time', date_from.isoformat())
            if date_to:
                query = query.lte('exit_time', date_to.isoformat())
            
            result = query.order('entry_time', desc=True).limit(limit).execute()
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to get trades: {e}")
            return []
    
    # Daily P&L Management
    def save_daily_pnl(self, pnl_data: Dict[str, Any]) -> bool:
        """Save or update daily P&L"""
        try:
            # Check if record exists for the date
            existing = self.supabase.table('daily_pnl').select('*').eq('date', pnl_data['date']).eq('strategy_name', pnl_data['strategy_name']).eq('trading_mode', pnl_data['trading_mode']).execute()
            
            pnl_data['updated_at'] = datetime.now(timezone.utc).isoformat()
            
            if existing.data:
                # Update existing
                result = self.supabase.table('daily_pnl').update(pnl_data).eq('id', existing.data[0]['id']).execute()
            else:
                # Insert new
                pnl_data['created_at'] = datetime.now(timezone.utc).isoformat()
                result = self.supabase.table('daily_pnl').insert(pnl_data).execute()
            
            logger.info(f"Daily P&L saved for {pnl_data['date']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save daily P&L: {e}")
            return False
    
    def get_daily_pnl(self, strategy_name: str = None, trading_mode: str = None, 
                     date_from: str = None, date_to: str = None) -> List[Dict[str, Any]]:
        """Get daily P&L records"""
        try:
            query = self.supabase.table('daily_pnl').select('*')
            
            if strategy_name:
                query = query.eq('strategy_name', strategy_name)
            if trading_mode:
                query = query.eq('trading_mode', trading_mode)
            if date_from:
                query = query.gte('date', date_from)
            if date_to:
                query = query.lte('date', date_to)
            
            result = query.order('date', desc=True).execute()
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to get daily P&L: {e}")
            return []
    
    # Strategy Signals
    def save_strategy_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Save strategy signal for analysis"""
        try:
            signal_data['created_at'] = datetime.now(timezone.utc).isoformat()
            
            # Sanitize data to prevent JSON serialization errors
            sanitized_data = self._sanitize_for_json(signal_data)
            
            result = self.supabase.table('strategy_signals').insert(sanitized_data).execute()
            
            logger.debug(f"Strategy signal saved: {signal_data['strategy_name']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save strategy signal: {e}")
            return False
    
    def get_strategy_signals(self, strategy_name: str = None, signal_type: str = None, 
                           date_from: datetime = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get strategy signals for analysis"""
        try:
            query = self.supabase.table('strategy_signals').select('*')
            
            if strategy_name:
                query = query.eq('strategy_name', strategy_name)
            if signal_type:
                query = query.eq('signal_type', signal_type)
            if date_from:
                query = query.gte('created_at', date_from.isoformat())
            
            result = query.order('created_at', desc=True).limit(limit).execute()
            return result.data
            
        except Exception as e:
            logger.error(f"Failed to get strategy signals: {e}")
            return []
    
    # Analytics and Performance
    def get_strategy_performance(self, strategy_name: str, trading_mode: str = 'paper', 
                               days: int = 30) -> Dict[str, Any]:
        """Get comprehensive strategy performance metrics"""
        try:
            # Get trades for the period
            date_from = (datetime.now(timezone.utc) - timedelta(days=days)).date()
            trades = self.get_trades(strategy_name, trading_mode, date_from)
            
            if not trades:
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'average_pnl_per_trade': 0,
                    'best_trade': 0,
                    'worst_trade': 0,
                    'profit_factor': 0
                }
            
            # Calculate metrics
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t['pnl'] > 0])
            losing_trades = len([t for t in trades if t['pnl'] < 0])
            total_pnl = sum(t['pnl'] for t in trades)
            
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
            
            pnls = [t['pnl'] for t in trades]
            best_trade = max(pnls) if pnls else 0
            worst_trade = min(pnls) if pnls else 0
            
            # Profit factor
            gross_profit = sum(pnl for pnl in pnls if pnl > 0)
            gross_loss = abs(sum(pnl for pnl in pnls if pnl < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': round(win_rate, 2),
                'total_pnl': round(total_pnl, 2),
                'average_pnl_per_trade': round(avg_pnl, 2),
                'best_trade': round(best_trade, 2),
                'worst_trade': round(worst_trade, 2),
                'profit_factor': round(profit_factor, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get strategy performance: {e}")
            return {}