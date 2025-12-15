#!/usr/bin/env python3
"""
Base Strategy Class
Abstract base class for all trading strategies
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

class SignalType(Enum):
    """Trading signal types"""
    BUY_CALL = "BUY_CALL"
    BUY_PUT = "BUY_PUT"
    SELL_CALL = "SELL_CALL"
    SELL_PUT = "SELL_PUT"
    HOLD = "HOLD"
    CLOSE = "CLOSE"

@dataclass
class TradingSignal:
    """Trading signal data structure"""
    signal_type: SignalType
    symbol: str
    strike_price: int
    entry_price: float
    target_price: float
    stop_loss_price: float
    quantity: int
    timestamp: datetime
    confidence: float  # 0.0 to 1.0
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class Position:
    """Position data structure"""
    symbol: str
    signal_type: SignalType
    quantity: int
    entry_price: float
    entry_time: datetime
    last_update: datetime
    metadata: Optional[Dict[str, Any]] = None
    is_closed: bool = False
    close_time: Optional[datetime] = None
    close_price: Optional[float] = None
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert position to dictionary for JSON serialization"""
        return {
            'symbol': self.symbol,
            'signal_type': self.signal_type.value,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat(),
            'last_update': self.last_update.isoformat(),
            'metadata': self.metadata or {}
        }

class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies
    Long-only implementation - BUY calls/puts only
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.is_active = False
        self.positions: Dict[str, Position] = {}
        self.signals_history: List[TradingSignal] = []
        
        # Long-only configuration
        self.lot_size = 75  # Nifty option lot size
        self.lots_per_trade = config.get('lots_per_trade', 1)
        self.target_profit = config.get('target_profit', 35)  # 35%
        self.stop_loss = config.get('stop_loss', 40)  # 40%
        
    @abstractmethod
    def generate_signals(self, market_data: Dict[str, Any]) -> List[TradingSignal]:
        """
        Generate trading signals based on market data
        
        Args:
            market_data: Real-time market data from Kite Connect
            
        Returns:
            List of trading signals (BUY_CALL, BUY_PUT, or HOLD)
        """
        pass
    
    @abstractmethod
    def get_strategy_parameters(self) -> Dict[str, Any]:
        """
        Return current strategy parameters for UI display
        
        Returns:
            Dictionary of parameter names and values
        """
        pass
    
    def update_positions(self, current_prices: Dict[str, float]):
        """
        Update all positions with current market prices
        
        Args:
            current_prices: Dictionary of symbol -> current_price
        """
        for position in self.positions.values():
            if position.symbol in current_prices:
                position.current_price = current_prices[position.symbol]
                position.unrealized_pnl = (
                    (position.current_price - position.entry_price) * position.quantity
                )
    
    def should_close_position(self, position: Position) -> bool:
        """
        Check if position should be closed based on target/SL
        
        Args:
            position: Position to check
            
        Returns:
            True if position should be closed
        """
        if not position.is_open:
            return False
            
        pnl_percent = (position.unrealized_pnl / (position.entry_price * position.quantity)) * 100
        
        # Close on target profit
        if pnl_percent >= self.target_profit:
            return True
            
        # Close on stop loss
        if pnl_percent <= -self.stop_loss:
            return True
            
        return False
    
    def get_total_pnl(self) -> float:
        """
        Calculate total P&L across all positions
        
        Returns:
            Total P&L amount
        """
        return sum(pos.unrealized_pnl for pos in self.positions.values() if pos.is_open)
    
    def get_position_count(self) -> int:
        """
        Get count of active positions
        
        Returns:
            Number of open positions
        """
        return len([pos for pos in self.positions.values() if pos.is_open])
    
    def start_strategy(self):
        """Start the strategy"""
        self.is_active = True
        
    def stop_strategy(self):
        """Stop the strategy"""
        self.is_active = False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current strategy status
        
        Returns:
            Strategy status information
        """
        return {
            'name': self.name,
            'active': self.is_active,
            'total_pnl': self.get_total_pnl(),
            'position_count': self.get_position_count(),
            'total_positions': len(self.positions),
            'parameters': self.get_strategy_parameters()
        }