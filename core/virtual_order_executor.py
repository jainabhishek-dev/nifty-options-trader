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
    
    def __init__(self, initial_capital: float = None, db_manager=None, kite_manager=None):
        # Use configuration value if not explicitly provided
        if initial_capital is None:
            from config.settings import TradingConfig
            initial_capital = TradingConfig.PAPER_TRADING_CAPITAL
        
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
        self.slippage_bps = 0  # No slippage for paper trading
        self.execution_delay_ms = 100  # 100ms execution delay
        self.brokerage_per_lot = 0.0  # ₹0 for paper trading (no fees)
        
        # Risk limits
        self.max_positions = 50  # Maximum open positions
        self.max_single_position_size = 50000.0  # ₹50,000 per position
        
        # IST timezone
        self.ist = pytz.timezone('Asia/Kolkata')
        
        # 🚀 CRITICAL FIX: Load existing open positions from database on startup (single call)
        self._recover_positions_from_database()
        
        # 🔄 RECOVERY FIX: Check for and fix orphaned positions (open but have SELL orders)
        self._recover_orphaned_positions()
    
    def _recover_orphaned_positions(self):
        """
        Recovery mechanism: Fix orphaned positions
        
        Orphaned positions are those that:
        1. Are marked as open in database
        2. Have corresponding SELL orders
        3. Were not properly closed due to system restart or errors
        
        This ensures data consistency after system interruptions.
        """
        if not self.db_manager:
            print("WARNING: No database manager - skipping orphaned position recovery")
            return
        
        try:
            print("Checking for orphaned positions (open but have SELL orders)...")
            
            # Get all open positions
            open_positions = self.db_manager.supabase.table('positions').select('*').eq('trading_mode', 'paper').eq('is_open', True).execute()
            
            orphaned_count = 0
            fixed_count = 0
            
            for pos in open_positions.data:
                # Check if there's a SELL order for this position
                sell_orders = self.db_manager.supabase.table('orders').select('*').eq('symbol', pos['symbol']).eq('strategy_name', pos['strategy_name']).eq('order_type', 'SELL').eq('trading_mode', 'paper').order('created_at', desc=False).execute()
                
                if sell_orders.data:
                    # Found SELL order for open position - this is orphaned!
                    orphaned_count += 1
                    sell_order = sell_orders.data[0]  # Take first SELL order
                    
                    print(f"\n🔍 Found orphaned position: {pos['symbol']}")
                    print(f"   Position Entry: Rs.{pos['average_price']} at {pos['entry_time']}")
                    print(f"   SELL order: Rs.{sell_order['price']} at {sell_order['created_at']}")
                    
                    # Calculate P&L
                    entry_price = pos['average_price']
                    exit_price = sell_order['price']
                    quantity = pos['quantity']
                    pnl = (exit_price - entry_price) * quantity
                    pnl_percent = (pnl / (entry_price * quantity)) * 100 if entry_price > 0 else 0
                    
                    # Close the position
                    try:
                        update_data = {
                            'quantity': 0,
                            'current_price': exit_price,
                            'unrealized_pnl': 0.0,
                            'realized_pnl': pnl,
                            'is_open': False,
                            'exit_time': sell_order['created_at'],
                            'exit_price': exit_price,
                            'updated_at': datetime.now(self.ist).isoformat()
                        }
                        
                        # Add sell_order_id if column exists (check by trying)
                        try:
                            update_data['sell_order_id'] = sell_order['id']
                        except:
                            pass  # Column might not exist yet
                        
                        result = self.db_manager.supabase.table('positions').update(update_data).eq('id', pos['id']).execute()
                        
                        if result.data:
                            fixed_count += 1
                            print(f"   ✅ Orphaned position closed: P&L Rs.{pnl:+.2f} ({pnl_percent:+.2f}%)")
                            
                            # Remove from memory if present
                            matching_keys = [k for k in self.positions.keys() if k.startswith(pos['symbol'])]
                            for key in matching_keys:
                                if hasattr(self.positions[key], 'metadata') and self.positions[key].metadata.get('position_id') == pos['id']:
                                    self.positions[key].is_closed = True
                                    print(f"   ✅ Removed from memory: {key}")
                        else:
                            print(f"   ❌ Failed to close orphaned position")
                            
                    except Exception as e:
                        print(f"   ❌ Error closing orphaned position: {e}")
            
            if orphaned_count > 0:
                print(f"\n🔄 Orphaned position recovery complete: {fixed_count}/{orphaned_count} fixed")
            else:
                print("✅ No orphaned positions found - all data consistent")
                
        except Exception as e:
            print(f"ERROR: Orphaned position recovery failed: {e}")
    
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
                    
                    # Generate unique position key from database ID to prevent overwrites
                    unique_position_key = f"{symbol}_{pos_data['id'][:8]}"
                    
                    # Create Position object with database linkage
                    position = Position(
                        symbol=symbol,
                        signal_type=signal_type,
                        quantity=pos_data['quantity'],
                        entry_price=pos_data['average_price'],  # PRESERVE original entry price from DB
                        entry_time=entry_time,
                        is_closed=False,  # It's open
                        last_update=datetime.fromisoformat(pos_data['updated_at'].replace('Z', '+00:00')),
                        metadata={
                            'strategy': pos_data.get('strategy_name', 'unknown'),
                            'position_id': pos_data['id'],  # Critical: Link to database position ID
                            'buy_order_id': pos_data.get('buy_order_id'),  # PRESERVE foreign key relationship
                            'unique_key': unique_position_key,
                            'original_quantity': pos_data['quantity'],
                            'entry_order_saved': True  # Position was already created, so entry order exists
                        }
                    )
                    
                    # Add to in-memory positions with UNIQUE KEY to prevent overwrites
                    self.positions[unique_position_key] = position
                    recovered_count += 1
                    
                    print(f"SUCCESS: Recovered position: {symbol} (Qty: {pos_data['quantity']}, Entry: Rs.{pos_data['average_price']:.2f})")
                    print(f"         Unique key: {unique_position_key}, Buy Order ID: {pos_data.get('buy_order_id', 'None')}")
                    
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
        """Validate order before placement - CRITICAL: Prevent orphaned SELL orders"""
        try:
            # CRITICAL FIX 1: Strict SELL order validation to prevent trading violations
            if signal.signal_type in [SignalType.SELL_CALL, SignalType.SELL_PUT]:
                # Check both memory AND database for open positions (comprehensive check)
                memory_position_found = False
                
                # First check: In-memory positions
                for pos_key, position in self.positions.items():
                    if (position.symbol == signal.symbol and 
                        not getattr(position, 'is_closed', False) and
                        position.quantity >= signal.quantity and
                        self._match_option_types(position.signal_type, signal.signal_type)):
                        memory_position_found = True
                        break
                
                # Second check: Database positions (in case of recovery issues)
                db_position_found = False
                if self.db_manager:
                    try:
                        open_positions = self.db_manager.supabase.table('positions').select('*').eq('symbol', signal.symbol).eq('trading_mode', 'paper').eq('is_open', True).execute()
                        total_db_quantity = 0
                        for pos in open_positions.data:
                            total_db_quantity += pos['quantity']
                        
                        if total_db_quantity >= signal.quantity:
                            db_position_found = True
                            print(f"✅ Database validation: {total_db_quantity} quantity available for SELL {signal.quantity}")
                        else:
                            print(f"❌ Database validation: Only {total_db_quantity} available, need {signal.quantity}")
                    except Exception as e:
                        print(f"Warning: Could not check database positions: {e}")
                
                # STRICT VALIDATION: Both checks must pass
                if not memory_position_found or not db_position_found:
                    print(f"🚨 VALIDATION FAILED: SELL {signal.symbol} (Qty: {signal.quantity}) REJECTED")
                    print(f"   Memory position found: {memory_position_found}")
                    print(f"   Database position found: {db_position_found}")
                    print(f"   Cannot sell what you don't own - order blocked")
                    return False
                
                print(f"✅ SELL validation passed: {signal.symbol} (Qty: {signal.quantity})")
            
            # Check if market price is valid
            if market_price <= 0:
                print("Invalid market price")
                return False
            
            # For BUY orders, check position limits
            if signal.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
                if len(self.positions) >= self.max_positions:
                    print("Maximum positions limit reached")
                    return False
            
            # For BUY orders, validate capital requirements
            if signal.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
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
    
    def _match_option_types(self, position_signal_type: SignalType, order_signal_type: SignalType) -> bool:
        """Check if position and order are for same option type (CALL/PUT)"""
        position_is_call = position_signal_type.name.endswith('CALL')
        position_is_put = position_signal_type.name.endswith('PUT')
        order_is_call = order_signal_type.name.endswith('CALL')
        order_is_put = order_signal_type.name.endswith('PUT')
        
        return (position_is_call and order_is_call) or (position_is_put and order_is_put)
    
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
            saved_order_id = None  # Initialize before try block to track save success
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
                        
                        # CRITICAL FIX: Store the database ID in order metadata for foreign key relationships
                        if not order.metadata:
                            order.metadata = {}
                        order.metadata['database_id'] = saved_order_id
                        
                        # Verify the order was actually saved by checking its existence
                        verify_result = self.db_manager.supabase.table('orders').select('id').eq('id', saved_order_id).execute()
                        if not verify_result.data:
                            print(f"❌ CRITICAL ERROR: Order save claimed success but order not found in database!")
                            print(f"   Order ID {saved_order_id} does not exist in database")
                            if order.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
                                print(f"   🚨 STOPPING EXECUTION - Order verification failed")
                                return False
                    else:
                        print(f"❌ Order save returned None: {order_data['order_type']} {order.symbol}")
                        print(f"   Order data attempted: {order_data}")
                        # CRITICAL: Stop execution immediately if BUY order save fails
                        if order.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
                            print(f"   🚨 STOPPING EXECUTION - Cannot create position without saved order")
                            return False
                        else:
                            # For SELL orders, proceed to close position even if order save failed
                            # This prevents stuck open positions. Order save already retried 3 times.
                            print(f"   ⚠️ WARNING: Proceeding to close position despite order save failure")
                            print(f"   (Order save retried 3 times - likely persistent database issue)")
                            print(f"   Position will be closed to prevent stuck open position")
                        
                except Exception as e:
                    print(f"❌ CRITICAL ERROR: Exception during order save: {e}")
                    print(f"   Signal type: {order.signal_type.value}")
                    print(f"   Symbol: {order.symbol}")
                    print(f"   Metadata: {order.metadata}")
                    try:
                        print(f"   Order data that failed: {order_data}")
                    except:
                        print(f"   Could not display order_data due to creation failure")
                    
                    # FIX: Check if order was actually saved before stopping execution
                    # This prevents false negative: treating post-save errors as save failures
                    if saved_order_id:
                        print(f"   ⚠️ Order was SAVED successfully (ID: {saved_order_id}) despite exception")
                        print(f"   Exception occurred AFTER save - continuing to position creation")
                        # Ensure database_id is in metadata for position creation
                        if not order.metadata:
                            order.metadata = {}
                        order.metadata['database_id'] = saved_order_id
                    else:
                        # Order truly failed to save - stop execution for BUY orders
                        if order.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
                            print(f"   🚨 STOPPING EXECUTION - Opening order save failed")
                            return False
                        else:
                            # For SELL orders, proceed to close position
                            print(f"   ⚠️ WARNING: Proceeding to close position despite exception")
                            print(f"   Position will be closed to prevent stuck open position")
            else:
                print(f"⚠️  No database manager available - order not saved: {order.symbol}")
            
            # Create trade record ONLY after successful order save
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
            
            # Update positions ONLY after successful order save
            print(f"🔄 Proceeding to position management for verified order {order_id}")
            self._update_position(order, trade)
            
            # Update capital - ONLY for BUY orders (SELL releases capital in _close_matching_position)
            if order.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
                self.available_capital -= total_cost
                self.used_margin += total_cost
            
            print(f"Order executed: {order.symbol} @ ₹{execution_price} (Qty: {order.quantity})")
            return True
            
        except Exception as e:
            print(f"Error executing order {order_id}: {e}")
            return False
    
    def _update_position(self, order: VirtualOrder, trade: VirtualTrade):
        """Update position based on executed trade - FIXED: Separate positions per BUY order"""
        try:
            symbol = order.symbol
            
            if order.signal_type in [SignalType.BUY_CALL, SignalType.BUY_PUT]:
                # CRITICAL FIX 2: Each BUY order creates separate position (NO AGGREGATION)
                self._create_new_position(order, trade)
                
            elif order.signal_type in [SignalType.SELL_CALL, SignalType.SELL_PUT]:
                # CRITICAL FIX 3: Close exact matching position (NO PARTIAL CLOSES)
                self._close_matching_position(order, trade)
            
        except Exception as e:
            print(f"Error updating position: {e}")
    
    def _create_new_position(self, order: VirtualOrder, trade: VirtualTrade):
        """Create new position for BUY order - each BUY gets separate position"""
        try:
            # Generate unique position identifier for each BUY order
            import uuid
            unique_position_key = f"{order.symbol}_{uuid.uuid4().hex[:8]}"
            
            # Use order's filled timestamp to maintain exact timing consistency
            entry_time = order.filled_timestamp if order.filled_timestamp else datetime.now(self.ist)
            current_time = datetime.now(self.ist)
            
            # Always create NEW position for each BUY order (no aggregation)
            position = Position(
                symbol=order.symbol,
                signal_type=order.signal_type,
                quantity=trade.quantity,
                entry_price=trade.price,
                entry_time=entry_time,  # Use order's filled timestamp for consistency
                last_update=current_time,
                highest_price=trade.price,  # Initialize trailing stop at entry price
                metadata={
                    'strategy': trade.metadata.get('strategy', 'unknown') if trade.metadata else 'unknown',
                    'original_quantity': trade.quantity,
                    'buy_order_id': order.order_id,
                    'unique_key': unique_position_key,
                    'created_at': entry_time.isoformat()  # Use entry time for consistency
                }
            )
            
            # Store with unique key to prevent conflicts
            self.positions[unique_position_key] = position
            print(f"✅ NEW position created in memory: {unique_position_key} (Qty: {trade.quantity}, Entry: ₹{trade.price:.2f})")
            print(f"🔗 Memory positions now: {len(self.positions)}")
            
            # ATOMIC OPERATION: Save position to database immediately
            if self.db_manager:
                try:
                    # CRITICAL FIX: Use database ID for foreign key relationship
                    database_order_id = order.metadata.get('database_id') if order.metadata else None
                    if not database_order_id:
                        print(f"❌ CRITICAL ERROR: No database ID found for order {order.order_id}")
                        raise Exception(f"Cannot create position without database order ID")
                        
                    position_data = {
                        'strategy_name': trade.metadata.get('strategy', 'unknown') if trade.metadata else 'unknown',  # Clean strategy name!
                        'trading_mode': 'paper',
                        'symbol': order.symbol,
                        'quantity': trade.quantity,
                        'average_price': trade.price,
                        'current_price': trade.price,
                        'unrealized_pnl': 0.0,
                        'is_open': True,
                        'entry_time': entry_time.isoformat(),  # Use order's filled time for consistency
                        'buy_order_id': database_order_id  # FIXED: Use database UUID for foreign key
                    }
                    
                    position_id = self.db_manager.save_position(position_data)
                    if position_id:
                        position.metadata['position_id'] = position_id
                        print(f"✅ Position saved to database: {unique_position_key} (DB ID: {position_id})")
                        print(f"✅ BUY order → Position link established: Order {database_order_id} → Position {position_id}")
                    else:
                        print(f"❌ CRITICAL ERROR: Position save failed for {unique_position_key}")
                        print(f"❌ BUY order {order.order_id} has NO corresponding position!")
                        print(f"❌ This violates core requirement: 1 BUY order = 1 position")
                        # Don't continue if position save fails - this is critical
                        raise Exception(f"Position creation failed for order {order.order_id}")
                        
                except Exception as e:
                    print(f"❌ CRITICAL: Failed to save position to database: {e}")
                    
        except Exception as e:
            print(f"Error creating new position: {e}")
    
    def _close_matching_position(self, order: VirtualOrder, trade: VirtualTrade):
        """Close exact matching position for SELL order"""
        try:
            # Find the specific position to close (First-In-First-Out logic)
            target_position_key = None
            target_position = None
            oldest_entry_time = None
            
            # Find oldest open position with matching symbol and quantity
            for pos_key, pos in self.positions.items():
                if (pos.symbol == order.symbol and 
                    not getattr(pos, 'is_closed', False) and 
                    pos.quantity == trade.quantity and
                    self._match_option_types(pos.signal_type, order.signal_type)):
                    
                    if oldest_entry_time is None or pos.entry_time < oldest_entry_time:
                        target_position_key = pos_key
                        target_position = pos
                        oldest_entry_time = pos.entry_time
            
            if not target_position:
                print(f"❌ CRITICAL: No matching open position found for SELL order {order.symbol} (Qty: {trade.quantity})")
                return
            
            # Close the specific position
            current_time = datetime.now(self.ist)
            target_position.is_closed = True
            target_position.quantity = 0  # CRITICAL: Set quantity to 0 to prevent blocking new signals
            target_position.close_time = current_time  # Real close time
            target_position.close_price = trade.price
            target_position.last_update = current_time
            
            if not target_position.metadata:
                target_position.metadata = {}
            target_position.metadata['sell_order_id'] = order.order_id
            target_position.metadata['closed_at'] = current_time.isoformat()
            
            print(f"✅ Position CLOSED: {target_position_key} (Entry: ₹{target_position.entry_price:.2f}, Exit: ₹{trade.price:.2f})")
            
            # Update database with closed position
            if self.db_manager and target_position.metadata.get('position_id'):
                try:
                    # Get database order ID for foreign key (if available)
                    database_order_id = order.metadata.get('database_id') if order.metadata else None
                    
                    # CRITICAL: Calculate P&L correctly - use ORIGINAL quantity before it was set to 0
                    original_quantity = target_position.metadata.get('original_quantity', trade.quantity)
                    pnl = (trade.price - target_position.entry_price) * original_quantity
                    pnl_percent = ((trade.price - target_position.entry_price) / target_position.entry_price) if target_position.entry_price > 0 else 0
                    
                    position_update_data = {
                        'quantity': 0,  # Position fully closed
                        'current_price': trade.price,
                        'unrealized_pnl': 0.0,
                        'realized_pnl': pnl,
                        'pnl_percent': pnl_percent,
                        'is_open': False,
                        'exit_time': current_time.isoformat(),  # Real exit time
                        'exit_price': trade.price,
                        'exit_reason': trade.metadata.get('exit_reason', 'Strategy Exit') if trade.metadata else 'Strategy Exit',
                        'exit_reason_category': trade.metadata.get('exit_reason_category', 'OTHER') if trade.metadata else 'OTHER'
                    }
                    
                    # Add sell_order_id if we have database ID and column exists
                    if database_order_id:
                        try:
                            position_update_data['sell_order_id'] = database_order_id
                        except:
                            print(f"⚠️  sell_order_id column not available (run migration)")
                    
                    position_id = target_position.metadata['position_id']
                    result = self.db_manager.supabase.table('positions').update(position_update_data).eq('id', position_id).execute()
                    
                    if result.data:
                        print(f"✅ Position closed in database: {order.symbol} (P&L: {pnl_percent*100:+.2f}%)")
                        
                        # 🚀 CRITICAL FIX #1: Release capital when position closes
                        # This restores the capital that was locked when the position was opened
                        try:
                            # Calculate locked capital (original investment + fees paid on entry)
                            locked_capital = target_position.entry_price * original_quantity
                            fees_on_entry = self.brokerage_per_lot  # Fees that were charged on BUY
                            
                            # Calculate realized P&L (already calculated above)
                            realized_pnl = pnl
                            
                            # Release capital: Return locked amount + fees + profit/loss
                            # Must return fees because they were deducted on BUY (line 460)
                            self.available_capital += locked_capital + fees_on_entry + realized_pnl
                            self.used_margin -= (locked_capital + fees_on_entry)
                            
                            print(f"💰 Capital released: Locked=₹{locked_capital:,.0f}, Fees=₹{fees_on_entry:,.0f}, P&L={realized_pnl:+,.0f}, Available=₹{self.available_capital:,.0f}")
                            
                        except Exception as e:
                            print(f"⚠️ Error releasing capital: {e}")
                        
                        # 🗑️ CRITICAL FIX #2: Remove closed position from memory
                        # Closed positions should only exist in database, not in active memory
                        try:
                            if target_position_key in self.positions:
                                del self.positions[target_position_key]
                                print(f"🗑️ Removed closed position from memory: {target_position_key}")
                                print(f"📊 Active positions in memory: {len(self.positions)}")
                        except Exception as e:
                            print(f"⚠️ Error removing closed position from memory: {e}")
                    else:
                        print(f"⚠️ Failed to update position closure in database")
                        
                except Exception as e:
                    print(f"Warning: Failed to update closed position in database: {e}")
                    
        except Exception as e:
            print(f"Error closing position: {e}")
    
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
            # ENHANCED: Handle both unique position keys and base symbols
            position_key = symbol
            if symbol not in self.positions:
                # Try to find by base symbol (extract base from unique key)
                base_symbol = symbol.split('_')[0] if '_' in symbol else symbol
                matching_keys = [key for key in self.positions.keys() if key.startswith(base_symbol)]
                if matching_keys:
                    position_key = matching_keys[0]  # Use first matching position
                    print(f"🔍 Found position {position_key} for symbol {symbol}")
                else:
                    print(f"No position found for {symbol}")
                    return False
            
            position = self.positions[position_key]
            
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