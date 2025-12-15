"""
Trading Strategies Module
========================

This module contains all trading strategies for the Nifty Options Trading Platform.
Each strategy implements the BaseStrategy interface and provides:

1. Signal generation logic
2. Risk management rules  
3. Position sizing
4. Exit conditions

Available Strategies:
- BaseStrategy: Abstract base class for all strategies
- ScalpingStrategy: High-frequency 1-minute scalping strategy (long-only)
"""

from .base_strategy import BaseStrategy, TradingSignal, SignalType, Position
from .scalping_strategy import ScalpingStrategy, ScalpingConfig
from .supertrend_strategy import SupertrendStrategy, SupertrendConfig

__all__ = [
    'BaseStrategy',
    'TradingSignal', 
    'SignalType',
    'Position',
    'ScalpingStrategy',
    'ScalpingConfig',
    'SupertrendStrategy',
    'SupertrendConfig'
]