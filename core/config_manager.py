#!/usr/bin/env python3
"""
Configuration Manager
Handles loading, saving, and managing platform settings
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class TradingConfig:
    """Trading configuration settings"""
    # Trading Mode
    trading_mode: str = "PAPER"  # PAPER, LIVE
    
    # Risk Management
    max_daily_loss: float = 5000.0
    trailing_stop_amount: float = 500.0
    max_positions: int = 5
    capital_per_trade: float = 10000.0
    max_position_size: float = 25000.0
    
    # Paper Trading
    paper_trading_capital: float = 100000.0
    
    # Options Configuration
    nifty_symbol: str = "NIFTY"
    options_expiry_days: int = 7
    atm_range: int = 200
    
    # Auto-trading
    auto_trading_enabled: bool = False
    auto_trade_start_time: str = "09:15"
    auto_trade_end_time: str = "15:30"
    
    # Notifications
    email_notifications: bool = False
    telegram_notifications: bool = False
    
    # Advanced Settings
    refresh_interval: int = 30  # seconds
    price_precision: int = 2
    
    # Metadata
    last_updated: str = ""
    updated_by: str = "system"

class ConfigManager:
    """Manages platform configuration"""
    
    def __init__(self, config_file: str = "config/user_settings.json"):
        self.config_file = config_file
        self.ensure_config_dir()
        self._config = None
    
    def ensure_config_dir(self):
        """Ensure config directory exists"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
    
    def load_config(self) -> TradingConfig:
        """Load configuration from file or create default"""
        if self._config is not None:
            return self._config
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                
                # Create config object from saved data
                config = TradingConfig()
                
                # Update fields from saved data
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                
                self._config = config
                return config
            else:
                # Create default config
                return self.create_default_config()
                
        except Exception as e:
            print(f"Error loading config: {e}")
            return self.create_default_config()
    
    def create_default_config(self) -> TradingConfig:
        """Create default configuration"""
        config = TradingConfig()
        
        # Load defaults from environment variables if available
        config.trading_mode = os.getenv('TRADING_MODE', 'PAPER')
        config.max_daily_loss = float(os.getenv('MAX_DAILY_LOSS', 5000))
        config.trailing_stop_amount = float(os.getenv('TRAILING_STOP_AMOUNT', 500))
        config.max_positions = int(os.getenv('MAX_POSITIONS', 5))
        config.capital_per_trade = float(os.getenv('CAPITAL_PER_TRADE', 10000))
        config.paper_trading_capital = float(os.getenv('PAPER_TRADING_CAPITAL', 100000))
        config.nifty_symbol = os.getenv('NIFTY_SYMBOL', 'NIFTY')
        config.options_expiry_days = int(os.getenv('OPTIONS_EXPIRY_DAYS', 7))
        config.atm_range = int(os.getenv('ATM_RANGE', 200))
        config.max_position_size = float(os.getenv('MAX_POSITION_SIZE', 25000))
        
        # Set metadata
        config.last_updated = datetime.now().isoformat()
        config.updated_by = "system"
        
        self._config = config
        self.save_config(config)
        return config
    
    def save_config(self, config: TradingConfig) -> bool:
        """Save configuration to file"""
        try:
            # Update metadata
            config.last_updated = datetime.now().isoformat()
            
            # Convert to dict and save
            config_dict = asdict(config)
            
            with open(self.config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            # Update cached config
            self._config = config
            return True
            
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def update_config(self, updates: Dict[str, Any], updated_by: str = "user") -> bool:
        """Update specific configuration values"""
        config = self.load_config()
        
        # Validate and update fields
        for key, value in updates.items():
            if hasattr(config, key):
                # Type validation
                if isinstance(getattr(config, key), bool):
                    value = bool(value) if isinstance(value, bool) else str(value).lower() == 'true'
                elif isinstance(getattr(config, key), int):
                    value = int(float(value))  # Handle string numbers
                elif isinstance(getattr(config, key), float):
                    value = float(value)
                elif isinstance(getattr(config, key), str):
                    value = str(value)
                
                setattr(config, key, value)
        
        config.updated_by = updated_by
        return self.save_config(config)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        config = self.load_config()
        return asdict(config)
    
    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults"""
        try:
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
            self._config = None
            self.create_default_config()
            return True
        except Exception as e:
            print(f"Error resetting config: {e}")
            return False
    
    def export_config(self) -> str:
        """Export configuration as JSON string"""
        config = self.load_config()
        return json.dumps(asdict(config), indent=2)
    
    def import_config(self, json_data: str, updated_by: str = "import") -> bool:
        """Import configuration from JSON string"""
        try:
            data = json.loads(json_data)
            return self.update_config(data, updated_by)
        except Exception as e:
            print(f"Error importing config: {e}")
            return False

# Global config manager instance
config_manager = ConfigManager()

# Helper functions for easy access
def get_trading_config() -> TradingConfig:
    """Get current trading configuration"""
    return config_manager.load_config()

def update_trading_config(updates: Dict[str, Any], updated_by: str = "user") -> bool:
    """Update trading configuration"""
    return config_manager.update_config(updates, updated_by)

def get_config_value(key: str, default: Any = None) -> Any:
    """Get specific configuration value"""
    config = get_trading_config()
    return getattr(config, key, default)