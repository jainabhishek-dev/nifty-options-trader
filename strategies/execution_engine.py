#!/usr/bin/env python3
"""
Strategy Execution Engine
Manages the execution of multiple trading strategies
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import os
from dataclasses import dataclass, asdict

from strategies import (
    strategy_registry, 
    ATMStraddleStrategy, 
    IronCondorStrategy,
    BaseStrategy,
    TradeSignal
)
from core.kite_manager import KiteManager
from risk_management.options_risk_manager import OptionsRiskManager
from utils.market_utils import MarketDataManager
from config.settings import TradingConfig, is_trading_allowed

logger = logging.getLogger(__name__)

@dataclass
class StrategyStatus:
    """Status of a running strategy"""
    name: str
    active: bool
    signals_generated: int
    trades_executed: int
    current_pnl: float
    last_activity: datetime
    error_count: int
    last_error: str

@dataclass
class ExecutionSession:
    """Trading execution session"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    strategies: List[str]
    total_trades: int
    session_pnl: float
    status: str  # ACTIVE, PAUSED, STOPPED, COMPLETED

class StrategyExecutionEngine:
    """
    Central execution engine for trading strategies
    Manages multiple strategies and their lifecycle
    """
    
    def __init__(self, kite_manager: KiteManager):
        """Initialize execution engine"""
        self.kite_manager = kite_manager
        self.market_data = MarketDataManager(kite_manager.kite)
        self.risk_manager = OptionsRiskManager(kite_manager.kite, self.market_data)
        
        # Execution state
        self.active_strategies: Dict[str, BaseStrategy] = {}
        self.strategy_statuses: Dict[str, StrategyStatus] = {}
        self.current_session: Optional[ExecutionSession] = None
        self.is_running = False
        self.execution_thread: Optional[threading.Thread] = None
        
        # Performance tracking
        self.sessions_file = "data/execution_sessions.json"
        self.execution_log_file = "logs/strategy_execution.log"
        
        # Ensure directories exist
        os.makedirs("data", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        # Register available strategies
        self._register_strategies()
        
        logger.info("🚀 Strategy Execution Engine initialized")
    
    def _register_strategies(self):
        """Register all available strategies"""
        try:
            # Register strategy classes
            strategy_registry.register_strategy(ATMStraddleStrategy)
            strategy_registry.register_strategy(IronCondorStrategy)
            
            # Create default configurations if they don't exist
            self._create_default_strategy_configs()
            
            logger.info("✅ Strategies registered successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to register strategies: {e}")
    
    def _create_default_strategy_configs(self):
        """Create default strategy configurations"""
        try:
            # ATM Straddle default config
            if not strategy_registry.get_strategy_config("default_atm_straddle"):
                strategy_registry.create_strategy_config(
                    name="default_atm_straddle",
                    description="Default ATM Straddle Strategy for high volatility periods",
                    strategy_class="ATMStraddleStrategy",
                    parameters={
                        "entry_time_start": "09:20",
                        "entry_time_end": "10:00",
                        "exit_time": "15:15",
                        "max_loss_percent": 50.0,
                        "profit_target_percent": 100.0,
                        "volatility_threshold": 0.5
                    },
                    author="system"
                )
            
            # Iron Condor default config
            if not strategy_registry.get_strategy_config("default_iron_condor"):
                strategy_registry.create_strategy_config(
                    name="default_iron_condor",
                    description="Default Iron Condor Strategy for neutral market conditions",
                    strategy_class="IronCondorStrategy",
                    parameters={
                        "entry_time_start": "09:30",
                        "entry_time_end": "10:30",
                        "exit_time": "15:15",
                        "wing_width": 100,
                        "max_loss_percent": 80.0,
                        "profit_target_percent": 50.0
                    },
                    author="system"
                )
            
            logger.info("✅ Default strategy configurations created")
            
        except Exception as e:
            logger.error(f"❌ Failed to create default configurations: {e}")
    
    def start_execution_session(self, strategy_names: List[str]) -> str:
        """Start a new execution session with selected strategies"""
        try:
            if self.is_running:
                raise ValueError("Execution session is already running")
            
            if not self.kite_manager.is_authenticated:
                raise ValueError("Kite Connect authentication required")
            
            # Validate strategies
            for name in strategy_names:
                if not strategy_registry.get_strategy_config(name):
                    raise ValueError(f"Strategy '{name}' not found")
            
            # Create new session
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.current_session = ExecutionSession(
                session_id=session_id,
                start_time=datetime.now(),
                end_time=None,
                strategies=strategy_names.copy(),
                total_trades=0,
                session_pnl=0.0,
                status="ACTIVE"
            )
            
            # Initialize strategies
            self._initialize_strategies(strategy_names)
            
            # Start execution thread
            self.is_running = True
            self.execution_thread = threading.Thread(
                target=self._execution_loop,
                name="StrategyExecution",
                daemon=True
            )
            self.execution_thread.start()
            
            logger.info(f"🚀 Execution session started: {session_id} with {len(strategy_names)} strategies")
            return session_id
            
        except Exception as e:
            logger.error(f"❌ Failed to start execution session: {e}")
            raise
    
    def _initialize_strategies(self, strategy_names: List[str]):
        """Initialize strategy instances"""
        try:
            self.active_strategies.clear()
            self.strategy_statuses.clear()
            
            for name in strategy_names:
                # Create strategy instance
                strategy = strategy_registry.create_strategy_instance(
                    name, self.kite_manager, self.risk_manager, self.market_data
                )
                
                if strategy:
                    self.active_strategies[name] = strategy
                    self.strategy_statuses[name] = StrategyStatus(
                        name=name,
                        active=True,
                        signals_generated=0,
                        trades_executed=0,
                        current_pnl=0.0,
                        last_activity=datetime.now(),
                        error_count=0,
                        last_error=""
                    )
                    
                    # Mark strategy as active
                    strategy.is_active = True
                    strategy.start_time = datetime.now()
                    
                    logger.info(f"✅ Strategy initialized: {name}")
                else:
                    logger.error(f"❌ Failed to initialize strategy: {name}")
            
        except Exception as e:
            logger.error(f"❌ Strategy initialization failed: {e}")
            raise
    
    def _execution_loop(self):
        """Main execution loop running in background thread"""
        logger.info("🔄 Strategy execution loop started")
        
        try:
            while self.is_running:
                # Check if market is open and trading is allowed
                if not is_trading_allowed():
                    logger.debug("Market closed or trading not allowed")
                    time.sleep(30)  # Check every 30 seconds
                    continue
                
                # Update market data
                self.market_data.refresh_data()
                
                # Process each active strategy
                for strategy_name, strategy in self.active_strategies.items():
                    try:
                        if not strategy.is_active:
                            continue
                        
                        # Generate signals
                        signals = strategy.generate_signals()
                        
                        if signals:
                            self.strategy_statuses[strategy_name].signals_generated += len(signals)
                            logger.info(f"📡 {strategy_name}: Generated {len(signals)} signals")
                            
                            # Execute signals
                            for signal in signals:
                                success = self._execute_signal(strategy, signal, strategy_name)
                                if success:
                                    self.strategy_statuses[strategy_name].trades_executed += 1
                                    if self.current_session:
                                        self.current_session.total_trades += 1
                        
                        # Monitor existing positions
                        exit_signals = strategy.monitor_positions()
                        for exit_signal in exit_signals:
                            self._handle_exit_signal(strategy, exit_signal, strategy_name)
                        
                        # Update strategy status
                        self.strategy_statuses[strategy_name].last_activity = datetime.now()
                        self.strategy_statuses[strategy_name].current_pnl = strategy.strategy_pnl
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing strategy {strategy_name}: {e}")
                        self.strategy_statuses[strategy_name].error_count += 1
                        self.strategy_statuses[strategy_name].last_error = str(e)
                
                # Update session P&L
                if self.current_session:
                    self.current_session.session_pnl = sum(
                        status.current_pnl for status in self.strategy_statuses.values()
                    )
                
                # Sleep before next iteration
                time.sleep(15)  # 15-second execution cycle
                
        except Exception as e:
            logger.error(f"❌ Execution loop failed: {e}")
        finally:
            logger.info("🛑 Strategy execution loop stopped")
    
    def _execute_signal(self, strategy: BaseStrategy, signal: TradeSignal, strategy_name: str) -> bool:
        """Execute a trading signal"""
        try:
            # Risk management check
            if not self.risk_manager.can_place_new_trade({
                'symbol': signal.symbol,
                'confidence': signal.confidence,
                'premium': signal.entry_price
            }):
                logger.warning(f"🚫 Risk manager rejected signal: {signal.symbol}")
                return False
            # Execute trade through strategy
            result = strategy.execute_trade(signal)
            
            if result and result.status == "SUCCESS":
                logger.info(f"✅ Trade executed: {signal.symbol} - {result.message}")
                
                # Update risk manager
                self.risk_manager.record_trade({
                    'status': 'SUCCESS',
                    'symbol': signal.symbol,
                    'quantity': signal.quantity,
                    'price': signal.entry_price,
                    'pnl': 0  # Initial P&L is 0
                })
                
                return True
            else:
                error_msg = result.message if result else "Unknown error"
                logger.error(f"❌ Trade execution failed: {signal.symbol} - {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Signal execution error: {e}")
            return False
    
    def _handle_exit_signal(self, strategy: BaseStrategy, exit_signal: Dict[str, Any], strategy_name: str):
        """Handle position exit signal"""
        try:
            symbol = exit_signal.get('symbol', '')
            reason = exit_signal.get('reason', 'UNKNOWN')
            
            # Close position through strategy
            result = strategy.close_position(symbol, reason)
            
            if result and result.status == "SUCCESS":
                pnl = exit_signal.get('pnl_percent', 0) * result.quantity * result.price / 100
                
                logger.info(f"🚪 Position closed: {symbol} - {reason} (P&L: ₹{pnl:.2f})")
                
                # Update strategy P&L
                strategy.strategy_pnl += pnl
                
                # Update session P&L
                if self.current_session:
                    self.current_session.session_pnl += pnl
            
        except Exception as e:
            logger.error(f"❌ Exit signal handling failed: {e}")
    
    def stop_execution_session(self) -> bool:
        """Stop the current execution session"""
        try:
            if not self.is_running:
                logger.warning("No execution session is running")
                return False
            
            logger.info("🛑 Stopping execution session...")
            
            # Signal stop to execution loop
            self.is_running = False
            
            # Wait for execution thread to finish
            if self.execution_thread and self.execution_thread.is_alive():
                self.execution_thread.join(timeout=10)
            
            # Close all positions
            self._close_all_positions()
            
            # Finalize current session
            if self.current_session:
                self.current_session.end_time = datetime.now()
                self.current_session.status = "STOPPED"
                self._save_session()
            
            # Deactivate strategies
            for strategy in self.active_strategies.values():
                strategy.is_active = False
            
            self.active_strategies.clear()
            self.strategy_statuses.clear()
            
            logger.info("✅ Execution session stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to stop execution session: {e}")
            return False
    
    def _close_all_positions(self):
        """Close all active positions"""
        try:
            total_closed = 0
            
            for strategy_name, strategy in self.active_strategies.items():
                try:
                    results = strategy.close_all_positions()
                    total_closed += len(results)
                    
                    for result in results:
                        if result.status == "SUCCESS":
                            logger.info(f"🚪 Position closed: {result.symbol}")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to close positions for {strategy_name}: {e}")
            
            logger.info(f"🚪 Closed {total_closed} positions")
            
        except Exception as e:
            logger.error(f"❌ Failed to close all positions: {e}")
    
    def pause_strategy(self, strategy_name: str) -> bool:
        """Pause a specific strategy"""
        try:
            if strategy_name in self.active_strategies:
                strategy = self.active_strategies[strategy_name]
                strategy.is_active = False
                
                self.strategy_statuses[strategy_name].active = False
                
                logger.info(f"⏸️ Strategy paused: {strategy_name}")
                return True
            else:
                logger.warning(f"Strategy not found: {strategy_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to pause strategy {strategy_name}: {e}")
            return False
    
    def resume_strategy(self, strategy_name: str) -> bool:
        """Resume a paused strategy"""
        try:
            if strategy_name in self.active_strategies:
                strategy = self.active_strategies[strategy_name]
                strategy.is_active = True
                
                self.strategy_statuses[strategy_name].active = True
                
                logger.info(f"▶️ Strategy resumed: {strategy_name}")
                return True
            else:
                logger.warning(f"Strategy not found: {strategy_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to resume strategy {strategy_name}: {e}")
            return False
    
    def get_execution_status(self) -> Dict[str, Any]:
        """Get current execution status"""
        try:
            status = {
                'is_running': self.is_running,
                'market_open': is_trading_allowed(),
                'authenticated': self.kite_manager.is_authenticated,
                'active_strategies': len(self.active_strategies),
                'strategy_statuses': {
                    name: asdict(status) for name, status in self.strategy_statuses.items()
                }
            }
            
            if self.current_session:
                status['current_session'] = {
                    'session_id': self.current_session.session_id,
                    'start_time': self.current_session.start_time.isoformat(),
                    'total_trades': self.current_session.total_trades,
                    'session_pnl': self.current_session.session_pnl,
                    'status': self.current_session.status,
                    'strategies': self.current_session.strategies
                }
            
            return status
            
        except Exception as e:
            logger.error(f"❌ Failed to get execution status: {e}")
            return {}
    
    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """Get list of available strategies"""
        try:
            strategies = []
            configs = strategy_registry.get_all_strategy_configs()
            
            for name, config in configs.items():
                performance = strategy_registry.get_strategy_performance(name)
                
                strategy_info = {
                    'name': config.name,
                    'description': config.description,
                    'strategy_class': config.strategy_class,
                    'enabled': config.enabled,
                    'parameters': config.parameters,
                    'created_at': config.created_at,
                    'updated_at': config.updated_at,
                    'author': config.author
                }
                
                if performance:
                    strategy_info['performance'] = {
                        'total_signals': performance.total_signals,
                        'successful_trades': performance.successful_trades,
                        'win_rate': performance.win_rate,
                        'total_pnl': performance.total_pnl
                    }
                
                strategies.append(strategy_info)
            
            return strategies
            
        except Exception as e:
            logger.error(f"❌ Failed to get available strategies: {e}")
            return []
    
    def _save_session(self):
        """Save current session to file"""
        try:
            if not self.current_session:
                return
            
            # Load existing sessions
            sessions = []
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'r') as f:
                    sessions = json.load(f)
            
            # Add current session
            session_dict = asdict(self.current_session)
            session_dict['start_time'] = self.current_session.start_time.isoformat()
            if self.current_session.end_time:
                session_dict['end_time'] = self.current_session.end_time.isoformat()
            
            sessions.append(session_dict)
            
            # Save back to file
            with open(self.sessions_file, 'w') as f:
                json.dump(sessions, f, indent=2)
            
            logger.debug("💾 Session saved successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to save session: {e}")

# Export class
__all__ = ['StrategyExecutionEngine', 'StrategyStatus', 'ExecutionSession']