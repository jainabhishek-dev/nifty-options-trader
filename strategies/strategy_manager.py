#!/usr/bin/env python3
"""
Advanced Strategy Management System
Handles strategy registration, execution, and lifecycle management for backtesting, paper trading, and live trading.
"""

import logging
from typing import Dict, List, Optional, Type, Any, Union
from datetime import datetime, timedelta
from enum import Enum
import json
import os

from .base_strategy import BaseStrategy
from core.kite_manager import KiteManager

logger = logging.getLogger(__name__)

class TradingMode(Enum):
    """Trading execution modes"""
    BACKTEST = "BACKTEST"
    PAPER = "PAPER" 
    LIVE = "LIVE"

class StrategyStatus(Enum):
    """Strategy execution status"""
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    COMPLETED = "COMPLETED"

class StrategyConfig:
    """Configuration for a strategy instance"""
    def __init__(self, 
                 strategy_name: str,
                 strategy_class: str,
                 parameters: Dict[str, Any],
                 trading_mode: TradingMode,
                 capital_allocation: float,
                 risk_limits: Optional[Dict[str, Any]] = None):
        self.strategy_name = strategy_name
        self.strategy_class = strategy_class
        self.parameters = parameters
        self.trading_mode = trading_mode
        self.capital_allocation = capital_allocation
        self.risk_limits = risk_limits or {}
        self.created_at = datetime.now()
        self.status = StrategyStatus.INACTIVE

class StrategyManager:
    """
    Advanced Strategy Management System
    Handles all aspects of strategy lifecycle across different trading modes
    """
    
    def __init__(self, kite_manager: KiteManager):
        self.kite_manager = kite_manager
        
        # Strategy registry: class_name -> Strategy Class
        self._strategy_registry: Dict[str, Type[BaseStrategy]] = {}
        
        # Active strategy instances: strategy_name -> strategy_instance
        self._active_strategies: Dict[str, BaseStrategy] = {}
        
        # Strategy configurations: strategy_name -> StrategyConfig
        self._strategy_configs: Dict[str, StrategyConfig] = {}
        
        # Strategy performance tracking
        self._strategy_performance: Dict[str, Dict[str, Any]] = {}
        
        # Initialize with built-in strategies
        self._register_builtin_strategies()
        
        logger.info("🚀 StrategyManager initialized with advanced capabilities")
    
    def _register_builtin_strategies(self):
        """Register all built-in strategy classes"""
        try:
            from .options_strategy import ATMStraddleStrategy, IronCondorStrategy
            
            builtin_strategies = [
                ATMStraddleStrategy,
                IronCondorStrategy
            ]
            
            for strategy_class in builtin_strategies:
                self.register_strategy_class(strategy_class)
                
        except Exception as e:
            logger.error(f"❌ Error registering builtin strategies: {e}")
    
    def register_strategy_class(self, strategy_class: Type[BaseStrategy]) -> bool:
        """
        Register a new strategy class
        
        Args:
            strategy_class: Strategy class that inherits from BaseStrategy
            
        Returns:
            True if registered successfully
        """
        try:
            if not issubclass(strategy_class, BaseStrategy):
                raise ValueError(f"{strategy_class.__name__} must inherit from BaseStrategy")
            
            class_name = strategy_class.__name__
            self._strategy_registry[class_name] = strategy_class
            
            logger.info(f"✅ Registered strategy class: {class_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to register strategy {strategy_class.__name__}: {e}")
            return False
    
    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """Get list of all available strategy classes with metadata"""
        strategies = []
        
        for class_name, strategy_class in self._strategy_registry.items():
            try:
                # Get strategy metadata
                metadata = {
                    'class_name': class_name,
                    'display_name': getattr(strategy_class, 'DISPLAY_NAME', class_name),
                    'description': getattr(strategy_class, 'DESCRIPTION', 'No description available'),
                    'parameters': getattr(strategy_class, 'DEFAULT_PARAMETERS', {}),
                    'risk_level': getattr(strategy_class, 'RISK_LEVEL', 'MEDIUM'),
                    'min_capital': getattr(strategy_class, 'MIN_CAPITAL', 10000),
                    'supports_modes': getattr(strategy_class, 'SUPPORTED_MODES', ['BACKTEST', 'PAPER', 'LIVE'])
                }
                strategies.append(metadata)
                
            except Exception as e:
                logger.warning(f"⚠️ Error getting metadata for {class_name}: {e}")
        
        return strategies
    
    def create_strategy_instance(self,
                               strategy_name: str,
                               strategy_class_name: str,
                               parameters: Dict[str, Any],
                               trading_mode: TradingMode,
                               capital_allocation: float,
                               risk_limits: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create a new strategy instance
        
        Args:
            strategy_name: Unique name for this strategy instance
            strategy_class_name: Name of the registered strategy class
            parameters: Strategy-specific parameters
            trading_mode: Trading mode (BACKTEST, PAPER, LIVE)
            capital_allocation: Capital allocated to this strategy
            risk_limits: Risk management limits
            
        Returns:
            True if created successfully
        """
        try:
            # Validate inputs
            if strategy_name in self._strategy_configs:
                raise ValueError(f"Strategy '{strategy_name}' already exists")
            
            if strategy_class_name not in self._strategy_registry:
                raise ValueError(f"Strategy class '{strategy_class_name}' not registered")
            
            if capital_allocation <= 0:
                raise ValueError("Capital allocation must be positive")
            
            # Create strategy configuration
            config = StrategyConfig(
                strategy_name=strategy_name,
                strategy_class=strategy_class_name,
                parameters=parameters,
                trading_mode=trading_mode,
                capital_allocation=capital_allocation,
                risk_limits=risk_limits
            )
            
            # Instantiate the strategy class
            strategy_class = self._strategy_registry[strategy_class_name]
            
            # Create dependencies for strategy
            from risk_management.options_risk_manager import OptionsRiskManager
            from utils.market_utils import MarketDataManager
            
            market_data = MarketDataManager(self.kite_manager.kite)
            risk_manager = OptionsRiskManager(self.kite_manager.kite, market_data)
            
            # Create strategy instance with proper parameters
            strategy_instance = strategy_class(
                kite_client=self.kite_manager.kite,
                risk_manager=risk_manager,
                market_data=market_data,
                **parameters
            )
            
            # Store configuration and instance
            self._strategy_configs[strategy_name] = config
            self._active_strategies[strategy_name] = strategy_instance
            
            # Initialize performance tracking
            self._strategy_performance[strategy_name] = {
                'created_at': datetime.now().isoformat(),
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_pnl': 0.0,
                'max_drawdown': 0.0,
                'last_updated': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Created strategy instance: {strategy_name} ({strategy_class_name})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create strategy instance '{strategy_name}': {e}")
            return False
    
    def get_strategy_instance(self, strategy_name: str) -> Optional[BaseStrategy]:
        """Get a strategy instance by name"""
        return self._active_strategies.get(strategy_name)
    
    def get_strategy_config(self, strategy_name: str) -> Optional[StrategyConfig]:
        """Get strategy configuration by name"""
        return self._strategy_configs.get(strategy_name)
    
    def list_strategy_instances(self) -> List[Dict[str, Any]]:
        """Get list of all strategy instances with their status"""
        instances = []
        
        for name, config in self._strategy_configs.items():
            instance = self._active_strategies.get(name)
            performance = self._strategy_performance.get(name, {})
            
            instance_info = {
                'name': name,
                'class_name': config.strategy_class,
                'trading_mode': config.trading_mode.value,
                'status': config.status.value,
                'capital_allocation': config.capital_allocation,
                'parameters': config.parameters,
                'created_at': config.created_at.isoformat(),
                'performance': performance,
                'is_active': instance is not None
            }
            instances.append(instance_info)
        
        return instances
    
    def activate_strategy(self, strategy_name: str) -> bool:
        """Activate a strategy for execution"""
        try:
            config = self._strategy_configs.get(strategy_name)
            if not config:
                raise ValueError(f"Strategy '{strategy_name}' not found")
            
            instance = self._active_strategies.get(strategy_name)
            if not instance:
                raise ValueError(f"Strategy instance '{strategy_name}' not found")
            
            # Validate trading mode compatibility
            if config.trading_mode == TradingMode.LIVE and not self.kite_manager.is_authenticated:
                raise ValueError("Cannot activate live strategy - Kite Connect not authenticated")
            
            config.status = StrategyStatus.ACTIVE
            logger.info(f"✅ Activated strategy: {strategy_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to activate strategy '{strategy_name}': {e}")
            return False
    
    def deactivate_strategy(self, strategy_name: str) -> bool:
        """Deactivate a strategy"""
        try:
            config = self._strategy_configs.get(strategy_name)
            if not config:
                raise ValueError(f"Strategy '{strategy_name}' not found")
            
            config.status = StrategyStatus.INACTIVE
            logger.info(f"✅ Deactivated strategy: {strategy_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to deactivate strategy '{strategy_name}': {e}")
            return False
    
    def remove_strategy(self, strategy_name: str) -> bool:
        """Remove a strategy instance completely"""
        try:
            # Remove from all tracking dictionaries
            self._strategy_configs.pop(strategy_name, None)
            self._active_strategies.pop(strategy_name, None) 
            self._strategy_performance.pop(strategy_name, None)
            
            logger.info(f"✅ Removed strategy: {strategy_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to remove strategy '{strategy_name}': {e}")
            return False
    
    def update_strategy_performance(self, strategy_name: str, trade_result: Dict[str, Any]):
        """Update strategy performance metrics"""
        try:
            if strategy_name not in self._strategy_performance:
                return
            
            perf = self._strategy_performance[strategy_name]
            
            # Update trade counts
            perf['total_trades'] += 1
            pnl = trade_result.get('pnl', 0)
            
            if pnl > 0:
                perf['winning_trades'] += 1
            elif pnl < 0:
                perf['losing_trades'] += 1
            
            # Update total PnL
            perf['total_pnl'] += pnl
            
            # Update max drawdown if applicable
            if pnl < 0 and abs(pnl) > perf['max_drawdown']:
                perf['max_drawdown'] = abs(pnl)
            
            perf['last_updated'] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"❌ Error updating performance for {strategy_name}: {e}")
    
    def get_active_strategies_by_mode(self, trading_mode: TradingMode) -> List[str]:
        """Get list of active strategies for a specific trading mode"""
        active_strategies = []
        
        for name, config in self._strategy_configs.items():
            if (config.trading_mode == trading_mode and 
                config.status == StrategyStatus.ACTIVE):
                active_strategies.append(name)
        
        return active_strategies
    
    def validate_strategy_for_mode(self, strategy_name: str, trading_mode: TradingMode) -> bool:
        """Validate if a strategy can be used in the specified trading mode"""
        try:
            config = self._strategy_configs.get(strategy_name)
            if not config:
                return False
            
            instance = self._active_strategies.get(strategy_name)
            if not instance:
                return False
            
            # Check if strategy class supports the trading mode
            strategy_class = self._strategy_registry.get(config.strategy_class)
            if strategy_class:
                supported_modes = getattr(strategy_class, 'SUPPORTED_MODES', ['BACKTEST', 'PAPER', 'LIVE'])
                return trading_mode.value in supported_modes
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error validating strategy {strategy_name} for mode {trading_mode}: {e}")
            return False
    
    def export_strategy_config(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """Export strategy configuration for backup/sharing"""
        try:
            config = self._strategy_configs.get(strategy_name)
            if not config:
                return None
            
            return {
                'strategy_name': config.strategy_name,
                'strategy_class': config.strategy_class,
                'parameters': config.parameters,
                'trading_mode': config.trading_mode.value,
                'capital_allocation': config.capital_allocation,
                'risk_limits': config.risk_limits,
                'created_at': config.created_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error exporting config for {strategy_name}: {e}")
            return None
    
    def import_strategy_config(self, config_data: Dict[str, Any]) -> bool:
        """Import strategy configuration from exported data"""
        try:
            return self.create_strategy_instance(
                strategy_name=config_data['strategy_name'],
                strategy_class_name=config_data['strategy_class'],
                parameters=config_data['parameters'],
                trading_mode=TradingMode(config_data['trading_mode']),
                capital_allocation=config_data['capital_allocation'],
                risk_limits=config_data.get('risk_limits')
            )
            
        except Exception as e:
            logger.error(f"❌ Error importing strategy config: {e}")
            return False

# Global strategy manager instance
_strategy_manager: Optional[StrategyManager] = None

def get_strategy_manager(kite_manager: Optional[KiteManager] = None) -> StrategyManager:
    """Get or create the global strategy manager instance"""
    global _strategy_manager
    
    if _strategy_manager is None:
        if kite_manager is None:
            raise ValueError("KiteManager required for first-time initialization")
        _strategy_manager = StrategyManager(kite_manager)
    
    return _strategy_manager