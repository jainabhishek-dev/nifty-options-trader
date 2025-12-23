"""
Trading Strategy Manager
========================

Orchestrates the complete trading workflow:
1. Fetches real-time market data
2. Runs active strategies to generate signals
3. Executes virtual orders through paper trading engine
4. Monitors positions and applies risk management
5. Provides comprehensive trading dashboard data

This is the central component that ties together:
- Market Data Manager (data fetching)
- Trading Strategies (signal generation)  
- Virtual Order Executor (order execution)
- Risk Management (position monitoring)
"""

import time
import threading
import os
import json
import logging
import atexit
from datetime import datetime, timedelta, time as dt_time
from typing import Dict, List, Any, Optional
import pytz
from dotenv import load_dotenv

from core.kite_manager import KiteManager
from core.market_data_manager import MarketDataManager
from core.virtual_order_executor import VirtualOrderExecutor
from core.database_manager import DatabaseManager
from strategies import ScalpingStrategy, ScalpingConfig, SupertrendStrategy, SupertrendConfig, BaseStrategy

# Set up logging
logger = logging.getLogger(__name__)

class TradingManager:
    """
    Central trading manager that orchestrates all trading activities
    """
    
    def __init__(self, kite_manager: KiteManager, initial_capital: float = 200000.0):
        # Load environment variables
        load_dotenv()
        
        self.kite_manager = kite_manager
        
        # Initialize database first (will be None if credentials not available)
        try:
            self.db_manager = DatabaseManager()
            print("Database connected successfully")
        except Exception as e:
            print(f"Database connection failed: {e}")
            print("Continuing without database persistence")
            self.db_manager = None
        
        # Initialize components with database manager
        self.market_data = MarketDataManager(kite_manager)
        self.order_executor = VirtualOrderExecutor(initial_capital, self.db_manager, self.kite_manager)
        
        # Initialize strategies
        self.strategies: Dict[str, BaseStrategy] = {}
        self.active_strategies: List[str] = []
        
        # Trading state
        self.is_running = False
        self.last_signal_time = None
        self.trading_thread = None
        self.trading_mode = 'paper'  # 'paper' or 'live'
        self.shutdown_event = threading.Event()
        
        # Configuration
        self.update_interval = 1   # Update every 1 second for real-time execution
        self.max_daily_trades = 100  # Maximum trades per day (increased for frequent trading)
        self.daily_trade_count = 0
        self.force_exit_time = dt_time(15, 5)  # 3:05 PM - force close all positions
        
        # IST timezone
        self.ist = pytz.timezone('Asia/Kolkata')
        
        # Register cleanup on exit for non-daemon threads
        atexit.register(self._cleanup_on_exit)
        
        # State persistence file paths
        self.state_file = os.path.join('config', 'active_sessions.json')
        self.strategy_state_file = os.path.join('config', 'strategy_states.json')
        
        # Initialize default strategies
        self._initialize_strategies()
        
        # Load persisted strategy states
        self._load_strategy_states()
        
        # Initialize monitoring
        self._setup_monitoring()
    
    def _initialize_strategies(self):
        """Initialize available trading strategies"""
        try:
            # Create scalping strategy with Supertrend config (fast 1-minute signals)
            scalping_config = ScalpingConfig(
                rsi_period=3,      # Fast ATR period for Supertrend
                rsi_oversold=1.0,  # ATR multiplier for Supertrend
                rsi_overbought=70.0,  # Keep for compatibility 
                volume_threshold=1.0,  # More sensitive trigger
                target_profit=15.0,    # 15% profit target
                stop_loss=10.0,        # 10% trailing stop loss
                time_stop_minutes=30,
                lot_size=75
            )
            
            self.strategies['scalping'] = ScalpingStrategy(scalping_config, self.kite_manager, self.order_executor)
            print("Scalping strategy initialized with position tracking")
            
            # Create supertrend strategy with default config
            supertrend_config = SupertrendConfig(
                atr_period=10,
                atr_multiplier=3.0,
                target_profit=40.0,
                stop_loss=50.0,
                time_stop_minutes=120,
                lot_size=75
            )
            
            self.strategies['supertrend'] = SupertrendStrategy(supertrend_config, self.kite_manager)
            print("Supertrend strategy initialized")
            
        except Exception as e:
            print(f"Error initializing strategies: {e}")
    
    def start_trading(self, strategy_names: List[str] = None):
        """
        Start automated trading with specified strategies - CRITICAL FIX 4: Single strategy enforcement
        
        Args:
            strategy_names: List of strategy names to activate, or None for all
        """
        try:
            # CRITICAL FIX 4: Enforce single strategy operation to prevent conflicts
            if strategy_names and len(strategy_names) > 1:
                print(f"🚨 STRATEGY ISOLATION ERROR: Cannot run multiple strategies simultaneously")
                print(f"   Requested: {strategy_names}")
                print(f"   System only supports ONE strategy at a time to prevent data corruption")
                return False
            
            # If already running, check for conflicts
            if self.is_running:
                if strategy_names:
                    # Check if trying to add different strategy while one is running
                    if self.active_strategies and strategy_names[0] not in self.active_strategies:
                        print(f"🚨 STRATEGY CONFLICT: Cannot add '{strategy_names[0]}' while '{self.active_strategies[0]}' is running")
                        print(f"   Please stop current strategy first")
                        return False
                    
                    new_strategies = [name for name in strategy_names if name in self.strategies and name not in self.active_strategies]
                    if new_strategies:
                        self.active_strategies = [new_strategies[0]]  # Keep only one strategy
                        print(f"✅ Single strategy activated: {new_strategies[0]}")
                        return True
                print("Specified strategy is already running or invalid")
                return False
            
            # Validate authentication
            if not self.kite_manager.is_authenticated:
                print("Not authenticated with Kite Connect")
                return False
            
            # Check market hours
            if not self.market_data.is_market_open():
                print("Market is currently closed")
                return False
            
            # CRITICAL: Set SINGLE active strategy only
            if strategy_names is None:
                # Default to first available strategy (scalping)
                available_strategies = list(self.strategies.keys())
                self.active_strategies = [available_strategies[0]] if available_strategies else []
            else:
                # Take only the first valid strategy
                valid_strategies = [name for name in strategy_names if name in self.strategies]
                self.active_strategies = [valid_strategies[0]] if valid_strategies else []
            
            if not self.active_strategies:
                print("No valid strategy to activate")
                return False
            
            print(f"✅ Starting trading with SINGLE strategy: {self.active_strategies[0]}")
            print(f"🔒 Strategy isolation enforced - no conflicts possible")
            
            # Mark session start time and save initial state
            self._session_start_time = datetime.now(self.ist).isoformat()
            
            # Update monitoring
            self.monitoring['session_start_time'] = self._session_start_time
            self.monitoring['strategies_activated'] += len(self.active_strategies)
            self._log_system_event("TRADING_START", 
                                 f"Trading started with {len(self.active_strategies)} strategies", 
                                 {"strategies": self.active_strategies})
            
            # Start trading loop in separate thread (daemon=False for system sleep resilience)
            self.is_running = True
            self.trading_thread = threading.Thread(target=self._trading_loop, daemon=False)
            self.trading_thread.start()
            
            # Save state after starting
            self._save_strategy_states()
            
            return True
            
        except Exception as e:
            print(f"Error starting trading: {e}")
            return False
    
    def is_strategy_running(self, strategy_name: str) -> bool:
        """Check if a specific strategy is currently running"""
        return self.is_running and strategy_name in self.active_strategies
    
    def stop_trading(self, strategy_names: List[str] = None):
        """Stop automated trading for specified strategies or all"""
        try:
            if not self.is_running:
                print("Trading is not running")
                return
            
            if strategy_names:
                # Stop specific strategies
                strategies_to_remove = [name for name in strategy_names if name in self.active_strategies]
                if strategies_to_remove:
                    for strategy in strategies_to_remove:
                        self.active_strategies.remove(strategy)
                    print(f"Stopped strategies: {', '.join(strategies_to_remove)}")
                    
                    # If no strategies left, stop trading completely
                    if not self.active_strategies:
                        self.is_running = False
                        if self.trading_thread and self.trading_thread.is_alive():
                            self.trading_thread.join(timeout=5)
                        print("All strategies stopped - trading halted")
                else:
                    print("Specified strategies are not currently running")
            else:
                # Stop all trading
                print("Stopping all trading...")
                self.is_running = False
                self.active_strategies.clear()
                
                # Signal shutdown and wait for trading thread to finish
                self.shutdown_event.set()
                if self.trading_thread and self.trading_thread.is_alive():
                    self.trading_thread.join(timeout=10)  # Increased timeout for graceful shutdown
                
                # Save final state
                self._save_strategy_states()
                
                # Force termination if thread doesn't stop gracefully
                if self.trading_thread.is_alive():
                    print("WARNING: Trading thread did not stop gracefully")
                
            print("Trading stopped")
            
        except Exception as e:
            print(f"Error stopping trading: {e}")
    
    def _cleanup_on_exit(self):
        """Cleanup method called on application exit"""
        try:
            if self.is_running:
                print("Application exit detected - stopping trading thread...")
                self.stop_trading()
        except Exception as e:
            print(f"Error during exit cleanup: {e}")
    
    def get_active_strategies(self) -> List[str]:
        """Get list of currently active strategies (should be max 1)"""
        return self.active_strategies.copy()
    
    def get_current_strategy(self) -> Optional[str]:
        """Get the current active strategy (single strategy system)"""
        return self.active_strategies[0] if self.active_strategies else None
    
    def _monitor_connection_health(self):
        """Monitor and recover from connection issues"""
        try:
            health = self.kite_manager.test_connection_health()
            
            if not health['healthy']:
                print(f"⚠️  Connection health issues detected: {health['error_count']} errors")
                print(f"Recommendations: {', '.join(health['recommendations'])}")
                
                # Attempt recovery if connection is unhealthy
                recovery = self.kite_manager.recover_connection()
                if recovery['success']:
                    print(f"Connection recovered: {recovery['message']}")
                    self.monitoring['connection_recoveries'] += 1
                    self.monitoring['health_checks_passed'] += 1
                    self._log_system_event("CONNECTION_RECOVERED", recovery['message'])
                else:
                    print(f"Connection recovery failed: {recovery['message']}")
                    self.monitoring['health_checks_failed'] += 1
                    self._log_system_event("CONNECTION_RECOVERY_FAILED", recovery['message'])
                    # Log the issue but continue trading (don't stop the system)
                    
            elif health['error_count'] == 0:
                # Only log healthy status occasionally (every 5th check = ~2.5 minutes)
                if getattr(self, '_health_log_counter', 0) % 5 == 0:
                    print("✅ Connection health: OK")
                self._health_log_counter = getattr(self, '_health_log_counter', 0) + 1
                
        except Exception as e:
            print(f"Error in connection health monitoring: {e}")
            # Don't let health monitoring errors stop trading
    
    def _save_strategy_states(self):
        """Save current strategy states to disk for persistence"""
        try:
            state_data = {
                'timestamp': datetime.now(self.ist).isoformat(),
                'active_strategies': self.active_strategies.copy(),
                'is_trading_active': self.is_running,
                'strategy_configs': {},
                'session_info': {
                    'started_at': getattr(self, '_session_start_time', None),
                    'market_session': self.market_data.is_market_open()
                }
            }
            
            # Save individual strategy states
            for strategy_name, strategy in self.strategies.items():
                if hasattr(strategy, 'get_state'):
                    state_data['strategy_configs'][strategy_name] = strategy.get_state()
                else:
                    # Basic state for strategies without get_state method
                    state_data['strategy_configs'][strategy_name] = {
                        'active': strategy_name in self.active_strategies,
                        'config': getattr(strategy, 'config', {}).__dict__ if hasattr(getattr(strategy, 'config', {}), '__dict__') else {}
                    }
            
            # Ensure config directory exists
            os.makedirs('config', exist_ok=True)
            
            # Write state file
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2, default=str)
            
            print(f"✅ Strategy states saved to {self.state_file}")
            
        except Exception as e:
            print(f"❌ Error saving strategy states: {e}")
    
    def _load_strategy_states(self):
        """Load and restore strategy states from disk"""
        try:
            if not os.path.exists(self.state_file):
                print("📁 No saved strategy states found - starting fresh")
                return
            
            with open(self.state_file, 'r') as f:
                state_data = json.load(f)
            
            # Check if saved state is from today (don't restore old states)
            saved_timestamp = datetime.fromisoformat(state_data.get('timestamp', ''))
            current_date = datetime.now(self.ist).date()
            saved_date = saved_timestamp.date()
            
            if saved_date != current_date:
                print(f"📅 Saved state is from {saved_date}, not restoring (current: {current_date})")
                return
            
            # Restore active strategies if market is still open
            if state_data.get('is_trading_active', False) and self.market_data.is_market_open():
                restored_strategies = state_data.get('active_strategies', [])
                # Only restore strategies that still exist
                valid_strategies = [s for s in restored_strategies if s in self.strategies]
                
                if valid_strategies:
                    self.active_strategies = valid_strategies
                    print(f"🔄 Restored active strategies: {', '.join(valid_strategies)}")
                    
                    # Mark session as restored
                    self._session_restored = True
                else:
                    print("⚠️  No valid strategies to restore")
            else:
                print("📴 Previous session was inactive or market closed - not restoring")
                
        except Exception as e:
            print(f"Error loading strategy states: {e}")
            print("Starting with fresh strategy states")
    
    def _setup_monitoring(self):
        """Initialize monitoring and alerting systems"""
        self.monitoring = {
            'session_start_time': None,
            'total_iterations': 0,
            'error_count': 0,
            'last_error_time': None,
            'health_checks_passed': 0,
            'health_checks_failed': 0,
            'strategies_activated': 0,
            'strategies_deactivated': 0,
            'connection_recoveries': 0,
            'orders_executed': 0
        }
        
        # Create monitoring log file
        log_dir = os.path.join('logs')
        os.makedirs(log_dir, exist_ok=True)
        
        self.monitoring_log = os.path.join(log_dir, 'system_health.log')
        
        # Initialize monitoring log
        self._log_system_event("SYSTEM_INIT", "Trading system initialized")
    
    def _log_system_event(self, event_type, message, details=None):
        """Log system events for monitoring"""
        timestamp = datetime.now(self.ist).isoformat()
        log_entry = {
            'timestamp': timestamp,
            'event_type': event_type,
            'message': message,
            'details': details or {},
            'monitoring_stats': self.monitoring.copy()
        }
        
        try:
            with open(self.monitoring_log, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Error logging system event: {e}")
    
    def _monitor_system_health(self):
        """Comprehensive system health monitoring"""
        self.monitoring['total_iterations'] += 1
        
        # Check for concerning patterns
        alerts = []
        
        # Alert 1: High error rate
        if self.monitoring['error_count'] > 10:
            alerts.append(f"High error count: {self.monitoring['error_count']}")
        
        # Alert 2: Connection recovery failures
        if self.monitoring['connection_recoveries'] > 5:
            alerts.append(f"Multiple connection recoveries: {self.monitoring['connection_recoveries']}")
        
        # Alert 3: No strategy activity
        if (self.monitoring['total_iterations'] > 60 and 
            len(self.active_strategies) == 0):
            alerts.append("No active strategies for extended period")
        
        # Alert 4: Session duration monitoring
        if self.monitoring['session_start_time']:
            session_duration = (datetime.now(self.ist) - 
                              datetime.fromisoformat(self.monitoring['session_start_time'])).total_seconds()
            if session_duration > 8 * 3600:  # 8 hours
                alerts.append(f"Long session duration: {session_duration/3600:.1f} hours")
        
        # Log alerts if any
        if alerts:
            self._log_system_event("HEALTH_ALERT", 
                                 f"{len(alerts)} health alerts detected", 
                                 {"alerts": alerts})
            print(f"HEALTH ALERTS: {', '.join(alerts)}")
        
        # Log periodic health summary (every 5 minutes)
        if self.monitoring['total_iterations'] % 300 == 0:
            health_summary = {
                'uptime_minutes': self.monitoring['total_iterations'],
                'active_strategies': len(self.active_strategies),
                'error_rate': self.monitoring['error_count'] / max(self.monitoring['total_iterations'], 1),
                'health_check_success_rate': (self.monitoring['health_checks_passed'] / 
                                            max(self.monitoring['health_checks_passed'] + self.monitoring['health_checks_failed'], 1))
            }
            
            self._log_system_event("HEALTH_SUMMARY", 
                                 "Periodic health check", 
                                 health_summary)
            
            print(f"System Health Summary: {self.monitoring['total_iterations']} iterations, "
                  f"{len(self.active_strategies)} active strategies, "
                  f"{self.monitoring['error_count']} total errors")
    
    def _auto_save_states(self):
        """Periodically save strategy states during trading"""
        # Save every 60 iterations (approximately every minute)
        if hasattr(self, '_state_save_counter'):
            self._state_save_counter += 1
        else:
            self._state_save_counter = 1
            
        if self._state_save_counter % 60 == 0:
            self._save_strategy_states()
    
    def _trading_loop(self):
        """Main trading loop - runs in separate thread"""
        print("Trading loop started")
        
        while self.is_running and not self.shutdown_event.is_set():
            try:
                # Check for shutdown signal first
                if self.shutdown_event.is_set():
                    print("Shutdown event received - stopping trading loop")
                    break
                    
                # Check if market is still open
                if not self.market_data.is_market_open():
                    print("Market closed - stopping trading")
                    self.is_running = False
                    break
                
                # Connection health monitoring (every 30 iterations = ~30 seconds)
                if hasattr(self, '_connection_check_counter'):
                    self._connection_check_counter += 1
                else:
                    self._connection_check_counter = 1
                
                if self._connection_check_counter % 30 == 0:
                    self._monitor_connection_health()
                
                # Check for force exit time (3:05 PM)
                current_time = datetime.now(self.ist).time()
                if current_time >= self.force_exit_time:
                    print(f"Force exit time ({self.force_exit_time}) reached - closing all positions")
                    self._force_close_all_positions()
                    # Continue monitoring but no new entries
                
                # Update market data
                self._update_market_data()
                
                # Process each active strategy (no new entries after force exit time)
                if current_time < self.force_exit_time:
                    for strategy_name in self.active_strategies:
                        if not self.is_running or self.shutdown_event.is_set():
                            break
                        
                        self._process_strategy(strategy_name)
                
                # Monitor existing positions
                self._monitor_positions()
                
                # Reset daily trade count at start of new day
                self._check_new_trading_day()
                
                # Update daily P&L periodically (every 60 iterations = ~1 minute)
                if int(time.time()) % 60 == 0:
                    self._update_daily_pnl()
                
                # Auto-save strategy states periodically
                self._auto_save_states()
                
                # Monitor system health
                self._monitor_system_health()
                
                # Wait before next iteration (1 second for real-time execution)
                # Use interruptible sleep to allow for clean shutdown
                if self.shutdown_event.wait(self.update_interval):
                    break  # Shutdown event was set during sleep
                
            except Exception as e:
                print(f"Error in trading loop: {e}")
                # Log the full exception for debugging
                import traceback
                traceback.print_exc()
                # Continue running - don't let single errors stop the trading system
                # Use interruptible sleep for error recovery
                if self.shutdown_event.wait(10):
                    break  # Shutdown event was set during error recovery sleep
        
        print("Trading loop stopped")
    
    def _update_market_data(self):
        """Update market data for all strategies"""
        try:
            # Fetch 1-minute data for scalping strategy
            minute_data = self.market_data.get_nifty_ohlcv(interval="minute", days=1)
            
            # Fetch 15-minute data for supertrend strategy
            fifteen_min_data = self.market_data.get_nifty_ohlcv(interval="15minute", days=7)
            
            # Update strategies with appropriate data
            for strategy_name, strategy in self.strategies.items():
                if strategy_name == 'scalping' and not minute_data.empty:
                    strategy.update_market_data(minute_data)
                elif strategy_name == 'supertrend' and not fifteen_min_data.empty:
                    strategy.update_market_data(fifteen_min_data)
                
            # Store timestamp of last data update if any data was fetched
            if not minute_data.empty or not fifteen_min_data.empty:
                self.last_signal_time = datetime.now(self.ist)
            
        except Exception as e:
            print(f"Error updating market data: {e}")
    
    def _process_strategy(self, strategy_name: str):
        """Process a specific strategy for signals"""
        try:
            if strategy_name not in self.strategies:
                return
            
            strategy = self.strategies[strategy_name]
            
            # Get current market price
            current_price = self.market_data.get_current_price()
            if current_price <= 0:
                return
            
            # Generate signals (for BUY signal generation)
            signals = strategy.generate_signals(timestamp=datetime.now(self.ist), current_price=current_price)
            
            # Process each signal
            for signal in signals:
                if not self.is_running:
                    break
                
                # Save signal to database for analysis
                self._save_strategy_signal_to_db(strategy_name, signal, current_price, False)
                
                # Check daily trade limit
                if self.daily_trade_count >= self.max_daily_trades:
                    print(f"Daily trade limit ({self.max_daily_trades}) reached")
                    break
                
                # Get option price for the signal
                option_price = self._get_option_price(signal.symbol)
                if option_price <= 0:
                    continue
                
                # Add strategy name to signal metadata
                if not signal.metadata:
                    signal.metadata = {}
                signal.metadata['strategy'] = strategy_name
                
                # Place order through virtual executor
                order_id = self.order_executor.place_order(signal, option_price)
                
                if order_id:
                    self.daily_trade_count += 1
                    print(f"✅ Signal processed: {signal.symbol} @ ₹{option_price} (Strategy: {strategy_name})")
                    
                    # NOTE: Order is already saved by virtual_order_executor.place_order()
                    # Removed duplicate _save_order_to_db call to prevent conflicts
                    
                    # Get the position that was created
                    if signal.symbol in self.order_executor.positions:
                        position = self.order_executor.positions[signal.symbol]
                        self._save_position_to_db(signal.symbol, position)
                    
                    # Update signal in database as action taken
                    self._save_strategy_signal_to_db(strategy_name, signal, current_price, True)
                
        except Exception as e:
            print(f"Error processing strategy {strategy_name}: {e}")
    
    def _get_option_price(self, symbol: str) -> float:
        """Get real option price from Kite Connect API"""
        try:
            # CRITICAL FIX: Extract base symbol from unique position key
            # e.g., "NIFTY25D2325850CE_03448d82" → "NIFTY25D2325850CE"
            base_symbol = symbol.split('_')[0] if '_' in symbol else symbol
            
            # Get real market price using Kite Connect LTP API with NFO exchange prefix
            nfo_symbol = f"NFO:{base_symbol}"
            ltp_data = self.kite_manager.ltp([nfo_symbol])
            
            if ltp_data and nfo_symbol in ltp_data:
                last_price = ltp_data[nfo_symbol].get('last_price', 0.0)
                print(f"✅ Got LTP for {base_symbol}: ₹{last_price} (from key: {symbol})")
                return float(last_price)
            else:
                logger.warning(f"No LTP data available for {base_symbol} (position key: {symbol})")
                return 0.0
            
        except Exception as e:
            logger.error(f"Error getting real option price for {symbol}: {e}")
            return 0.0
    
    def _monitor_positions(self):
        """Monitor existing positions for exit conditions and update live prices"""
        try:
            # Get all open positions from database
            if not self.db_manager:
                return
                
            open_positions = self.db_manager.get_positions(trading_mode=self.trading_mode)
            open_positions = [p for p in open_positions if p.get('is_open', True)]
            
            if not open_positions:
                return
                
            # Collect current prices for all open positions
            symbol_prices = {}
            positions_to_close = []
            
            for db_position in open_positions:
                symbol = db_position['symbol']
                
                # Get current option price
                current_price = self._get_option_price(symbol)
                if current_price <= 0:
                    continue
                    
                symbol_prices[symbol] = current_price
                
                # Check exit conditions using virtual executor position if it exists
                # Find the executor position by base symbol (memory keys have suffixes)
                executor_position = None
                for key, pos in self.order_executor.positions.items():
                    if key.startswith(symbol):  # Match base symbol part
                        executor_position = pos
                        break
                        
                if executor_position:
                    # Check if any strategy wants to exit this position
                    for strategy_name in self.active_strategies:
                        strategy = self.strategies[strategy_name]
                        
                        # Update executor position current price for exit calculation
                        executor_position.current_price = current_price
                        
                        should_exit, reason = strategy.should_exit_position(
                            executor_position, current_price, datetime.now(self.ist)
                        )
                        
                        if should_exit:
                            positions_to_close.append((symbol, current_price, reason, db_position))
                            break
            
            # Update all positions with current prices in database
            if symbol_prices:
                self.db_manager.update_positions_live_data(symbol_prices)
            
            # Generate SELL signals for positions that need to be closed
            # This replaces the direct position closing approach with signal-driven architecture
            if positions_to_close:
                print(f"🔴 Processing {len(positions_to_close)} position exit conditions via SELL signals")
                
                for strategy_name in self.active_strategies:
                    strategy = self.strategies[strategy_name]
                    
                    # Set current market data for signal generation
                    strategy.order_executor = self.order_executor  # Ensure strategy has access to positions
                    
                    # Generate signals (including SELL signals for positions meeting exit conditions)
                    signals = strategy.generate_signals(timestamp=datetime.now(self.ist), symbol_prices=symbol_prices)
                    
                    # Process any SELL signals generated
                    sell_signals = [s for s in signals if s.signal_type.value in ['SELL_CALL', 'SELL_PUT']]
                    
                    if sell_signals:
                        print(f"🔴 Generated {len(sell_signals)} SELL signals")
                        for signal in sell_signals:
                            print(f"   Processing SELL signal: {signal.symbol}")
                            
                            # Get current market price for this symbol
                            current_price = symbol_prices.get(signal.symbol, 0)
                            if current_price > 0:
                                # Process SELL signal through normal order flow
                                order_id = self.order_executor.place_order(signal, current_price)
                                if order_id:
                                    print(f"✅ SELL order created: {signal.symbol} (ID: {order_id})")
                                else:
                                    print(f"❌ SELL order failed: {signal.symbol}")
                
                # Clear the positions_to_close list since we've processed them via signals
                positions_to_close.clear()
            
            # Legacy direct closing logic (should not execute if signal-driven approach works)
            for symbol, price, reason, db_position in positions_to_close:
                print(f"⚠️ WARNING: Using legacy direct position closing for {symbol}")
                # Get position before closing for database save
                executor_position = self.order_executor.positions.get(symbol)
                
                # Get exit reason category from strategy
                exit_reason_category = "OTHER"
                for strategy_name in self.active_strategies:
                    strategy = self.strategies[strategy_name]
                    if hasattr(strategy, 'get_exit_reason_category'):
                        exit_reason_category = strategy.get_exit_reason_category(reason)
                        break
                
                # Close position in executor if it exists
                if executor_position:
                    success = self.order_executor.close_position(symbol, price, reason, exit_reason_category)
                    if success:
                        print(f"Position closed: {symbol} @ ₹{price} - {reason} ({exit_reason_category})")
                        
                        # Save completed trade to database
                        self._save_trade_to_db(symbol, executor_position, price, reason)
                
                # Update database position as closed
                try:
                    close_data = {
                        'id': db_position['id'],
                        'symbol': symbol,
                        'is_open': False,
                        'exit_time': datetime.now(self.ist).isoformat(),
                        'exit_price': price,
                        'exit_reason': reason,
                        'exit_reason_category': exit_reason_category,
                        'current_price': price,
                        'realized_pnl': (price - float(db_position['average_price'])) * int(db_position['quantity'])
                    }
                    self.db_manager.save_position(close_data)
                    print(f"Database position updated as closed: {symbol}")
                except Exception as e:
                    print(f"Error updating position in database: {e}")
            
        except Exception as e:
            print(f"Error monitoring positions: {e}")
    
    def _check_new_trading_day(self):
        """Reset counters for new trading day"""
        try:
            now = datetime.now(self.ist)
            
            # Reset at market open (9:15 AM)
            market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
            
            if (hasattr(self, '_last_reset_date') and 
                self._last_reset_date != now.date() and 
                now.time() >= market_open.time()):
                
                self.daily_trade_count = 0
                self._last_reset_date = now.date()
                print(f"New trading day - counters reset")
            elif not hasattr(self, '_last_reset_date'):
                self._last_reset_date = now.date()
            
        except Exception as e:
            print(f"Error checking new trading day: {e}")
    
    def get_trading_status(self) -> Dict[str, Any]:
        """Get comprehensive trading status"""
        try:
            # Get market data summary
            print("Getting market summary...")
            market_summary = self.market_data.get_market_summary()
            
            # Get portfolio summary
            print("Getting portfolio summary...")
            portfolio_summary = self.order_executor.get_portfolio_summary()
            
            # Get strategy status
            print("Getting strategy status...")
            strategy_status = {}
            for name, strategy in self.strategies.items():
                print(f"Processing strategy: {name}")
                try:
                    stats = strategy.get_strategy_stats()
                    print(f"Got stats for {name}: {stats}")
                    strategy_status[name] = {
                        'active': name in self.active_strategies and self.is_running,
                        'available': True,
                        'stats': stats
                    }
                except Exception as se:
                    print(f"Error getting stats for strategy {name}: {se}")
                    strategy_status[name] = {
                        'active': False,
                        'available': False,
                        'stats': {'error': str(se)}
                    }
            
            return {
                'trading_active': self.is_running,
                'market_data': market_summary,
                'portfolio': portfolio_summary,
                'strategies': strategy_status,
                'daily_trades': self.daily_trade_count,
                'max_daily_trades': self.max_daily_trades,
                'last_update': self.last_signal_time.isoformat() if self.last_signal_time else None,
                'timestamp': datetime.now(self.ist).isoformat()
            }
            
        except Exception as e:
            print(f"Error getting trading status: {e}")
            return {
                'trading_active': False,
                'error': str(e),
                'timestamp': datetime.now(self.ist).isoformat()
            }
    
    def get_recent_orders(self, limit: int = 20) -> List[Dict]:
        """Get recent order history"""
        return self.order_executor.get_order_history(limit)
    
    def get_recent_trades(self, limit: int = 20) -> List[Dict]:
        """Get recent trade history"""
        return self.order_executor.get_trade_history(limit)
    
    def get_active_positions(self) -> List[Dict]:
        """Get all active positions"""
        try:
            positions = []
            for symbol, position in self.order_executor.positions.items():
                # Get current price for P&L calculation
                current_price = self._get_option_price(symbol)
                
                pnl = 0.0
                pnl_pct = 0.0
                if current_price > 0 and position.entry_price > 0:
                    pnl = (current_price - position.entry_price) * position.quantity
                    pnl_pct = (pnl / (position.entry_price * position.quantity)) * 100
                
                positions.append({
                    'symbol': symbol,
                    'quantity': position.quantity,
                    'entry_price': position.entry_price,
                    'current_price': current_price,
                    'pnl': pnl,
                    'pnl_percent': pnl_pct,
                    'entry_time': position.entry_time.isoformat(),
                    'signal_type': position.signal_type.value,
                    'strategy': position.metadata.get('strategy', 'unknown') if position.metadata else 'unknown'
                })
            
            return positions
            
        except Exception as e:
            print(f"Error getting active positions: {e}")
            return []
    
    def manual_close_position(self, symbol: str) -> bool:
        """Manually close a position"""
        try:
            current_price = self._get_option_price(symbol)
            if current_price <= 0:
                return False
            
            return self.order_executor.close_position(symbol, current_price, "Manual close")
            
        except Exception as e:
            print(f"Error manually closing position {symbol}: {e}")
            return False
    
    def _force_close_all_positions(self):
        """Force close all open positions at 3:05 PM - Enhanced to check both memory and database"""
        try:
            print(f"🚨 FORCE EXIT INITIATED at 15:05 IST")
            
            # Get positions from memory (recovered positions)
            memory_positions = list(self.order_executor.positions.keys())
            print(f"📊 In-memory positions: {len(memory_positions)} ({memory_positions})")
            
            # Also check database for any positions not in memory (safety check)
            db_positions = []
            if self.db_manager:
                try:
                    open_db_positions = self.db_manager.supabase.table('positions').select('symbol').eq('trading_mode', 'paper').eq('is_open', True).execute()
                    db_positions = [pos['symbol'] for pos in open_db_positions.data]
                    print(f"📊 Database open positions: {len(db_positions)} ({db_positions})")
                except Exception as e:
                    print(f"⚠️ Could not check database positions: {e}")
            
            # Combine both sources (memory has priority, database as backup)
            all_positions = list(set(memory_positions + db_positions))
            print(f"🎯 Total positions to close: {len(all_positions)} ({all_positions})")
            
            closed_count = 0
            failed_positions = []
            
            for symbol in all_positions:
                try:
                    print(f"🔄 Attempting force close: {symbol}")
                    current_price = self._get_option_price(symbol)
                    
                    if current_price > 0:
                        if self.order_executor.close_position(symbol, current_price, "Force close at 3:05 PM", "FORCE_EXIT"):
                            closed_count += 1
                            print(f"✅ Force closed: {symbol} at ₹{current_price}")
                        else:
                            failed_positions.append(symbol)
                            print(f"❌ Failed to close: {symbol}")
                    else:
                        failed_positions.append(symbol)
                        print(f"❌ Could not get price for: {symbol}")
                        
                except Exception as e:
                    failed_positions.append(symbol)
                    print(f"❌ Exception closing {symbol}: {e}")
            
            # Summary
            print(f"📈 FORCE EXIT COMPLETE: {closed_count} closed, {len(failed_positions)} failed")
            if failed_positions:
                print(f"⚠️ Failed positions: {failed_positions}")
                print(f"🛠️ Manual intervention may be required for failed positions")
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR in force close: {e}")
            print(f"🚨 Force exit mechanism failed - manual position review required")
    
    def reset_portfolio(self):
        """Reset portfolio for testing"""
        self.order_executor.reset_portfolio()
        self.daily_trade_count = 0
    
    def is_strategy_running(self, strategy_name: str) -> bool:
        """Check if a specific strategy is currently running"""
        return self.is_running and strategy_name in self.active_strategies
    
    def get_running_strategies(self) -> List[str]:
        """Get list of currently running strategies"""
        return self.active_strategies.copy() if self.is_running else []
    
    def update_strategy_config(self, strategy_name: str, config: Dict[str, Any]) -> bool:
        """Update strategy configuration"""
        try:
            # TODO: Implement strategy configuration updates
            print(f"Strategy config update not yet implemented for {strategy_name}")
            return False
            
        except Exception as e:
            print(f"Error updating strategy config: {e}")
            return False
    
    # Database persistence methods
    def _save_order_to_db(self, signal, option_price: float, order_id: str):
        """Save order to database"""
        if not self.db_manager:
            return
        
        try:
            order_data = {
                'strategy_name': signal.metadata.get('strategy', 'unknown'),
                'trading_mode': self.trading_mode,
                'symbol': signal.symbol,
                'order_type': signal.signal_type.value,
                'quantity': signal.quantity,
                'price': option_price,
                'order_id': order_id,
                'status': 'COMPLETE',
                'filled_quantity': signal.quantity,
                'filled_price': option_price,
                'signal_data': {
                    'confidence': signal.confidence,
                    'target_price': signal.target_price,
                    'stop_loss': signal.stop_loss,
                    'metadata': signal.metadata
                }
            }
            
            self.db_manager.save_order(order_data)
            
        except Exception as e:
            print(f"Error saving order to database: {e}")
    
    def _save_position_to_db(self, symbol: str, position):
        """Save position to database"""
        if not self.db_manager:
            return
        
        try:
            # Get current price for unrealized P&L
            current_price = self._get_option_price(symbol)
            unrealized_pnl = 0.0
            
            if current_price > 0:
                unrealized_pnl = (current_price - position.entry_price) * position.quantity
            
            position_data = {
                'strategy_name': position.metadata.get('strategy', 'unknown'),
                'trading_mode': self.trading_mode,
                'symbol': symbol,
                'quantity': position.quantity,
                'average_price': position.entry_price,
                'current_price': current_price,
                'unrealized_pnl': unrealized_pnl,
                'is_open': True,
                'entry_time': position.entry_time.isoformat()
            }
            
            self.db_manager.save_position(position_data)
            
        except Exception as e:
            print(f"Error saving position to database: {e}")
    
    def _save_trade_to_db(self, symbol: str, position, exit_price: float, exit_reason: str):
        """Save completed trade to database"""
        if not self.db_manager:
            return
        
        try:
            exit_time = datetime.now(self.ist)
            hold_duration = (exit_time - position.entry_time).total_seconds() / 60  # minutes
            
            pnl = (exit_price - position.entry_price) * position.quantity
            pnl_percentage = (pnl / (position.entry_price * position.quantity)) * 100
            
            trade_data = {
                'strategy_name': position.metadata.get('strategy', 'unknown'),
                'trading_mode': self.trading_mode,
                'symbol': symbol,
                'entry_price': position.entry_price,
                'exit_price': exit_price,
                'quantity': position.quantity,
                'pnl': pnl,
                'pnl_percentage': pnl_percentage,
                'entry_time': position.entry_time.isoformat(),
                'exit_time': exit_time.isoformat(),
                'hold_duration_minutes': int(hold_duration),
                'exit_reason': exit_reason,
                'entry_signal_data': position.metadata,
                'fees': 20.0,  # Simulated brokerage fees
                'slippage': 0.5  # Simulated slippage
            }
            
            self.db_manager.save_trade(trade_data)
            
        except Exception as e:
            print(f"Error saving trade to database: {e}")
    
    def _save_strategy_signal_to_db(self, strategy_name: str, signal, current_price: float, action_taken: bool = False):
        """Save strategy signal to database for analysis"""
        if not self.db_manager:
            return
        
        try:
            signal_data = {
                'strategy_name': strategy_name,
                'signal_type': signal.signal_type.value,
                'symbol': signal.symbol,
                'price': current_price,
                'signal_strength': signal.confidence,
                'market_data': {
                    'current_price': current_price,
                    'timestamp': datetime.now(self.ist).isoformat()
                },
                'indicators': signal.metadata,
                'action_taken': action_taken
            }
            
            self.db_manager.save_strategy_signal(signal_data)
            
        except Exception as e:
            print(f"Error saving strategy signal to database: {e}")
    
    def _update_daily_pnl(self):
        """Update daily P&L summary"""
        if not self.db_manager:
            return
        
        try:
            today = datetime.now(self.ist).date()
            
            # Get today's trades
            trades_today = self.db_manager.get_trades(
                trading_mode=self.trading_mode,
                date_from=datetime.combine(today, datetime.min.time())
            )
            
            # Calculate metrics
            realized_pnl = sum(trade['pnl'] for trade in trades_today)
            trades_count = len(trades_today)
            winning_trades = len([t for t in trades_today if t['pnl'] > 0])
            losing_trades = len([t for t in trades_today if t['pnl'] < 0])
            fees_paid = sum(trade.get('fees', 0) for trade in trades_today)
            
            # Get unrealized P&L from open positions
            unrealized_pnl = 0.0
            positions = self.db_manager.get_positions(
                trading_mode=self.trading_mode,
                is_open=True
            )
            for pos in positions:
                current_price = self._get_option_price(pos['symbol'])
                if current_price > 0:
                    unrealized_pnl += (current_price - pos['average_price']) * pos['quantity']
            
            # Total portfolio value
            portfolio_value = self.order_executor.available_capital + realized_pnl + unrealized_pnl
            
            pnl_data = {
                'date': today.isoformat(),
                'strategy_name': 'combined',  # Combined for all strategies
                'trading_mode': self.trading_mode,
                'realized_pnl': realized_pnl,
                'unrealized_pnl': unrealized_pnl,
                'total_pnl': realized_pnl + unrealized_pnl,
                'trades_count': trades_count,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'fees_paid': fees_paid,
                'portfolio_value': portfolio_value
            }
            
            self.db_manager.save_daily_pnl(pnl_data)
            
        except Exception as e:
            print(f"Error updating daily P&L: {e}")
    
    def get_performance_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get performance analytics from database"""
        if not self.db_manager:
            return {}
        
        try:
            analytics = {}
            
            # Get overall performance
            overall_performance = self.db_manager.get_strategy_performance(
                'combined', self.trading_mode, days
            )
            analytics['overall'] = overall_performance
            
            # Get strategy-specific performance
            for strategy_name in self.strategies.keys():
                strategy_performance = self.db_manager.get_strategy_performance(
                    strategy_name, self.trading_mode, days
                )
                analytics[strategy_name] = strategy_performance
            
            return analytics
            
        except Exception as e:
            print(f"Error getting performance analytics: {e}")
            return {}