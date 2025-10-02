# database/models.py
"""
Database Models for Nifty Options Trading Platform
Defines data structures for trades, analysis, and performance tracking
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import json

@dataclass
class TradeRecord:
    """Trade execution record"""
    id: Optional[int] = None
    timestamp: datetime = datetime.now()
    symbol: str = ""
    action: str = ""  # BUY/SELL
    quantity: int = 0
    price: float = 0.0
    order_id: str = ""
    status: str = ""  # SUCCESS/FAILED/PENDING
    pnl: float = 0.0
    fees: float = 0.0
    strategy: str = ""
    confidence: int = 0
    entry_reason: str = ""
    exit_reason: str = ""
    stop_loss: float = 0.0
    target: float = 0.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeRecord':
        """Create TradeRecord from dictionary"""
        # Handle datetime conversion
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        elif 'timestamp' not in data:
            data['timestamp'] = datetime.now()
        
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        # Convert datetime to ISO string
        if isinstance(data['timestamp'], datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        return data

@dataclass 
class AnalysisRecord:
    """AI analysis record"""
    id: Optional[int] = None
    timestamp: datetime = datetime.now()
    sentiment: str = ""  # Bullish/Bearish/Neutral
    impact: str = ""     # High/Medium/Low
    action: str = ""     # CALL/PUT/HOLD
    strike_type: str = ""  # ITM/ATM/OTM
    confidence: int = 0
    reason: str = ""
    nifty_level: float = 0.0
    used_for_trade: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        if isinstance(data['timestamp'], datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        return data

@dataclass
class PositionRecord:
    """Position tracking record"""
    id: Optional[int] = None
    timestamp: datetime = datetime.now()
    symbol: str = ""
    quantity: int = 0
    average_price: float = 0.0
    current_price: float = 0.0
    pnl: float = 0.0
    unrealized_pnl: float = 0.0
    status: str = "OPEN"  # OPEN/CLOSED
    entry_time: datetime = datetime.now()
    exit_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        if isinstance(data['timestamp'], datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        if isinstance(data['entry_time'], datetime):
            data['entry_time'] = data['entry_time'].isoformat()
        if data['exit_time'] and isinstance(data['exit_time'], datetime):
            data['exit_time'] = data['exit_time'].isoformat()
        return data

@dataclass
class PerformanceRecord:
    """Daily performance summary"""
    id: Optional[int] = None
    date: datetime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total_trades: int = 0
    successful_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    risk_adjusted_return: float = 0.0
    
    def calculate_metrics(self, trades: List[TradeRecord]) -> None:
        """Calculate performance metrics from trade list"""
        if not trades:
            return
        
        self.total_trades = len(trades)
        
        # Separate winning and losing trades
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        self.successful_trades = len(winning_trades)
        self.total_pnl = sum(t.pnl for t in trades)
        
        # Win rate
        self.win_rate = (self.successful_trades / self.total_trades) * 100 if self.total_trades > 0 else 0
        
        # Average profit/loss
        self.avg_profit = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        self.avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        # Largest win/loss
        self.largest_win = max(t.pnl for t in winning_trades) if winning_trades else 0
        self.largest_loss = min(t.pnl for t in losing_trades) if losing_trades else 0
        
        # Calculate drawdown (simplified)
        running_pnl = 0
        peak = 0
        max_dd = 0
        
        for trade in sorted(trades, key=lambda x: x.timestamp):
            running_pnl += trade.pnl
            if running_pnl > peak:
                peak = running_pnl
            drawdown = (peak - running_pnl) / max(peak, 1)
            if drawdown > max_dd:
                max_dd = drawdown
        
        self.max_drawdown = max_dd * 100  # Convert to percentage
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        if isinstance(data['date'], datetime):
            data['date'] = data['date'].isoformat()
        return data

@dataclass
class SystemEvent:
    """System events and alerts"""
    id: Optional[int] = None
    timestamp: datetime = datetime.now()
    event_type: str = ""  # INFO/WARNING/ERROR/TRADE/RISK
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        if isinstance(data['timestamp'], datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        if isinstance(data['details'], dict):
            data['details'] = json.dumps(data['details'])
        return data

# Export all models
__all__ = [
    'TradeRecord',
    'AnalysisRecord', 
    'PositionRecord',
    'PerformanceRecord',
    'SystemEvent'
]
