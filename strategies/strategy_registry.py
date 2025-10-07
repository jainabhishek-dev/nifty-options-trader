#!/usr/bin/env python3
"""
Strategy Registry and Factory
Central management system for all trading strategies
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Type, Optional, Any
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod

from .base_strategy import BaseStrategy
from core.kite_manager import KiteManager
from risk_management.options_risk_manager import OptionsRiskManager
from utils.market_utils import MarketDataManager

logger = logging.getLogger(__name__)

@dataclass
class StrategyConfig:
    """Strategy configuration data class"""
    name: str
    description: str
    strategy_class: str
    parameters: Dict[str, Any]
    enabled: bool = True
    created_at: str = ""
    updated_at: str = ""
    author: str = "system"
    version: str = "1.0.0"
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

@dataclass
class StrategyPerformance:
    """Strategy performance tracking"""
    strategy_name: str
    total_signals: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    last_updated: str = ""
    
    def __post_init__(self):
        self.last_updated = datetime.now().isoformat()
        if self.total_signals > 0:
            self.win_rate = (self.successful_trades / self.total_signals) * 100

class StrategyRegistry:
    """
    Central registry for all trading strategies
    Manages strategy creation, configuration, and lifecycle
    """
    
    def __init__(self):
        self.strategies_file = "config/strategies.json"
        self.performance_file = "data/strategy_performance.json"
        self._registered_strategies: Dict[str, Type[BaseStrategy]] = {}
        self._strategy_configs: Dict[str, StrategyConfig] = {}
        self._performance_data: Dict[str, StrategyPerformance] = {}
        
        # Ensure directories exist
        os.makedirs("config", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        
        # Load existing configurations
        self._load_strategy_configs()
        self._load_performance_data()
        
        logger.info("🏭 Strategy Registry initialized")
    
    def register_strategy(self, strategy_class: Type[BaseStrategy]) -> bool:
        """Register a strategy class in the registry"""
        try:
            strategy_name = strategy_class.__name__
            self._registered_strategies[strategy_name] = strategy_class
            logger.info(f"✅ Registered strategy: {strategy_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to register strategy {strategy_class.__name__}: {e}")
            return False
    
    def create_strategy_config(self, 
                             name: str,
                             description: str,
                             strategy_class: str,
                             parameters: Dict[str, Any],
                             author: str = "user") -> bool:
        """Create a new strategy configuration"""
        try:
            if name in self._strategy_configs:
                logger.warning(f"⚠️ Strategy config '{name}' already exists")
                return False
            
            if strategy_class not in self._registered_strategies:
                logger.error(f"❌ Strategy class '{strategy_class}' not registered")
                return False
            
            config = StrategyConfig(
                name=name,
                description=description,
                strategy_class=strategy_class,
                parameters=parameters,
                author=author
            )
            
            self._strategy_configs[name] = config
            self._save_strategy_configs()
            
            # Initialize performance tracking
            self._performance_data[name] = StrategyPerformance(strategy_name=name)
            self._save_performance_data()
            
            logger.info(f"✅ Created strategy config: {name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create strategy config '{name}': {e}")
            return False
    
    def update_strategy_config(self, name: str, updates: Dict[str, Any]) -> bool:
        """Update existing strategy configuration"""
        try:
            if name not in self._strategy_configs:
                logger.error(f"❌ Strategy config '{name}' not found")
                return False
            
            config = self._strategy_configs[name]
            
            # Update allowed fields
            if 'description' in updates:
                config.description = updates['description']
            if 'parameters' in updates:
                config.parameters.update(updates['parameters'])
            if 'enabled' in updates:
                config.enabled = bool(updates['enabled'])
            
            config.updated_at = datetime.now().isoformat()
            
            self._save_strategy_configs()
            logger.info(f"✅ Updated strategy config: {name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update strategy config '{name}': {e}")
            return False
    
    def delete_strategy_config(self, name: str) -> bool:
        """Delete a strategy configuration"""
        try:
            if name not in self._strategy_configs:
                logger.error(f"❌ Strategy config '{name}' not found")
                return False
            
            del self._strategy_configs[name]
            if name in self._performance_data:
                del self._performance_data[name]
            
            self._save_strategy_configs()
            self._save_performance_data()
            
            logger.info(f"✅ Deleted strategy config: {name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete strategy config '{name}': {e}")
            return False
    
    def create_strategy_instance(self, 
                               name: str,
                               kite_manager: KiteManager,
                               risk_manager: OptionsRiskManager,
                               market_data: MarketDataManager) -> Optional[BaseStrategy]:
        """Create a strategy instance from configuration"""
        try:
            if name not in self._strategy_configs:
                logger.error(f"❌ Strategy config '{name}' not found")
                return None
            
            config = self._strategy_configs[name]
            
            if not config.enabled:
                logger.warning(f"⚠️ Strategy '{name}' is disabled")
                return None
            
            if config.strategy_class not in self._registered_strategies:
                logger.error(f"❌ Strategy class '{config.strategy_class}' not registered")
                return None
            
            strategy_class = self._registered_strategies[config.strategy_class]
            
            # Create strategy instance with parameters
            strategy = strategy_class(
                kite_client=kite_manager.kite,
                risk_manager=risk_manager,
                market_data=market_data,
                **config.parameters
            )
            
            # Set strategy name for tracking
            strategy.config_name = name
            
            logger.info(f"✅ Created strategy instance: {name}")
            return strategy
            
        except Exception as e:
            logger.error(f"❌ Failed to create strategy instance '{name}': {e}")
            return None
    
    def get_strategy_config(self, name: str) -> Optional[StrategyConfig]:
        """Get strategy configuration by name"""
        return self._strategy_configs.get(name)
    
    def get_all_strategy_configs(self) -> Dict[str, StrategyConfig]:
        """Get all strategy configurations"""
        return self._strategy_configs.copy()
    
    def get_enabled_strategies(self) -> Dict[str, StrategyConfig]:
        """Get only enabled strategy configurations"""
        return {name: config for name, config in self._strategy_configs.items() 
                if config.enabled}
    
    def get_registered_strategy_classes(self) -> List[str]:
        """Get list of all registered strategy class names"""
        return list(self._registered_strategies.keys())
    
    def update_strategy_performance(self, 
                                  strategy_name: str,
                                  signals: int = 0,
                                  successful: int = 0,
                                  failed: int = 0,
                                  pnl: float = 0.0) -> bool:
        """Update strategy performance metrics"""
        try:
            if strategy_name not in self._performance_data:
                self._performance_data[strategy_name] = StrategyPerformance(
                    strategy_name=strategy_name
                )
            
            perf = self._performance_data[strategy_name]
            perf.total_signals += signals
            perf.successful_trades += successful
            perf.failed_trades += failed
            perf.total_pnl += pnl
            
            # Recalculate metrics
            if perf.total_signals > 0:
                perf.win_rate = (perf.successful_trades / perf.total_signals) * 100
                perf.avg_return = perf.total_pnl / perf.total_signals
            
            perf.last_updated = datetime.now().isoformat()
            
            self._save_performance_data()
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update performance for '{strategy_name}': {e}")
            return False
    
    def get_strategy_performance(self, name: str) -> Optional[StrategyPerformance]:
        """Get performance data for a strategy"""
        return self._performance_data.get(name)
    
    def get_all_performance_data(self) -> Dict[str, StrategyPerformance]:
        """Get performance data for all strategies"""
        return self._performance_data.copy()
    
    def _load_strategy_configs(self):
        """Load strategy configurations from file"""
        try:
            if os.path.exists(self.strategies_file):
                with open(self.strategies_file, 'r') as f:
                    data = json.load(f)
                    
                for name, config_dict in data.items():
                    config = StrategyConfig(**config_dict)
                    self._strategy_configs[name] = config
                
                logger.info(f"✅ Loaded {len(self._strategy_configs)} strategy configs")
            else:
                logger.info("📄 No existing strategy configs found")
                
        except Exception as e:
            logger.error(f"❌ Failed to load strategy configs: {e}")
    
    def _save_strategy_configs(self):
        """Save strategy configurations to file"""
        try:
            data = {}
            for name, config in self._strategy_configs.items():
                data[name] = asdict(config)
            
            with open(self.strategies_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"💾 Saved {len(self._strategy_configs)} strategy configs")
            
        except Exception as e:
            logger.error(f"❌ Failed to save strategy configs: {e}")
    
    def _load_performance_data(self):
        """Load performance data from file"""
        try:
            if os.path.exists(self.performance_file):
                with open(self.performance_file, 'r') as f:
                    data = json.load(f)
                    
                for name, perf_dict in data.items():
                    perf = StrategyPerformance(**perf_dict)
                    self._performance_data[name] = perf
                
                logger.info(f"✅ Loaded performance data for {len(self._performance_data)} strategies")
            else:
                logger.info("📄 No existing performance data found")
                
        except Exception as e:
            logger.error(f"❌ Failed to load performance data: {e}")
    
    def _save_performance_data(self):
        """Save performance data to file"""
        try:
            data = {}
            for name, perf in self._performance_data.items():
                data[name] = asdict(perf)
            
            with open(self.performance_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"💾 Saved performance data for {len(self._performance_data)} strategies")
            
        except Exception as e:
            logger.error(f"❌ Failed to save performance data: {e}")

# Global registry instance
strategy_registry = StrategyRegistry()