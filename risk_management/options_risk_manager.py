# risk_management/options_risk_manager.py
"""
Options Risk Management System
Handles position sizing, stop losses, risk limits, and portfolio risk management
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from kiteconnect import KiteConnect

from config.settings import TradingConfig, RiskConfig
from utils.market_utils import MarketDataManager

logger = logging.getLogger(__name__)

@dataclass
class RiskMetrics:
    """Risk metrics for a position or portfolio"""
    position_size: float
    max_loss: float
    current_pnl: float
    risk_reward_ratio: float
    portfolio_risk_percentage: float
    stop_loss_price: float
    target_price: float

@dataclass
class TradeSignal:
    """Enhanced trade signal with risk parameters"""
    symbol: str
    action: str  # BUY/SELL
    quantity: int
    order_type: str
    price: float
    stop_loss: float
    target: float
    risk_amount: float
    confidence: int

class OptionsRiskManager:
    """Comprehensive options risk management system"""
    
    def __init__(self, kite_client: KiteConnect, market_data: MarketDataManager):
        """Initialize risk management system"""
        self.kite = kite_client
        self.market_data = market_data
        
        # Risk tracking
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.active_positions = {}
        self.portfolio_value = 0.0
        
        # Load current portfolio state
        self._initialize_portfolio_state()
        
        logger.info("🛡️ Options Risk Manager initialized")
    
    def _initialize_portfolio_state(self) -> None:
        """Initialize portfolio state from current positions"""
        try:
            # Set portfolio value based on trading mode
            if TradingConfig.TRADING_MODE == 'PAPER':
                # Use artificial capital for paper trading
                self.portfolio_value = TradingConfig.PAPER_TRADING_CAPITAL
                logger.info(f"📝 PAPER TRADING: Using artificial capital: ₹{self.portfolio_value:,.2f}")
                
                # Initialize with no positions for paper trading
                self.daily_pnl = 0.0
                logger.info(f"📊 Paper portfolio initialized: 0 positions, P&L: ₹0.00")
                return
            
            # LIVE trading mode - use actual account data
            logger.info("💰 LIVE TRADING: Fetching actual account data...")
            
            # Get current positions
            positions_response = self.kite.positions()
            
            if isinstance(positions_response, dict):
                net_positions = positions_response.get('net', [])
                
                total_pnl = 0.0
                active_count = 0
                
                for position in net_positions:
                    if isinstance(position, dict) and position.get('quantity', 0) != 0:
                        pnl = float(position.get('pnl', 0))
                        total_pnl += pnl
                        active_count += 1
                        
                        # Store position details
                        symbol = position.get('tradingsymbol', '')
                        self.active_positions[symbol] = {
                            'quantity': position.get('quantity', 0),
                            'average_price': float(position.get('average_price', 0)),
                            'pnl': pnl,
                            'entry_time': datetime.now()  # Approximate
                        }
                
                self.daily_pnl = total_pnl
                logger.info(f"📊 Live portfolio initialized: {active_count} positions, P&L: ₹{total_pnl:,.2f}")
            
            # Get available funds for live trading
            margins_response = self.kite.margins()
            if isinstance(margins_response, dict):
                equity_data = margins_response.get('equity', {})
                if isinstance(equity_data, dict):
                    available_data = equity_data.get('available', {})
                    if isinstance(available_data, dict):
                        self.portfolio_value = float(available_data.get('cash', 0))
                        logger.info(f"💰 Available capital: ₹{self.portfolio_value:,.2f}")
        
        except Exception as e:
            logger.error(f"❌ Failed to initialize portfolio state: {e}")
            # Fallback for paper trading if error occurs
            if TradingConfig.TRADING_MODE == 'PAPER':
                self.portfolio_value = TradingConfig.PAPER_TRADING_CAPITAL
                logger.info(f"🔄 Fallback: Using paper trading capital: ₹{self.portfolio_value:,.2f}")
    
    def can_place_new_trade(self, trade_signal: Dict[str, Any]) -> bool:
        """Check if a new trade can be placed based on risk limits"""
        try:
            # Check daily trade limit
            if self.daily_trades >= TradingConfig.MAX_DAILY_TRADES:
                logger.warning(f"🚫 Daily trade limit reached: {self.daily_trades}/{TradingConfig.MAX_DAILY_TRADES}")
                return False
            
            # Check position limit
            if len(self.active_positions) >= TradingConfig.MAX_POSITIONS:
                logger.warning(f"🚫 Position limit reached: {len(self.active_positions)}/{TradingConfig.MAX_POSITIONS}")
                return False
            
            # Check daily loss limit
            if self.daily_pnl < -TradingConfig.MAX_DAILY_LOSS:
                logger.warning(f"🚫 Daily loss limit breached: ₹{self.daily_pnl:,.2f}")
                return False
            
            # Check consecutive loss limit
            if self.consecutive_losses >= RiskConfig.MAX_CONSECUTIVE_LOSSES:
                logger.warning(f"🚫 Consecutive loss limit reached: {self.consecutive_losses}")
                return False
            
            # Check if signal has sufficient confidence
            confidence = trade_signal.get('confidence', 0)
            if confidence < 6:  # Minimum confidence threshold
                logger.debug(f"🚫 Signal confidence too low: {confidence}/10")
                return False
            
            # Calculate position size and risk
            position_size = self._calculate_position_size(trade_signal)
            if position_size == 0:
                logger.warning("🚫 Position size calculation resulted in 0")
                return False
            
            logger.info(f"✅ Trade approved: {trade_signal.get('symbol', '')} - Size: {position_size}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Risk check failed: {e}")
            return False
    
    def _calculate_position_size(self, trade_signal: Dict[str, Any]) -> int:
        """Calculate appropriate position size based on risk parameters"""
        try:
            if self.portfolio_value <= 0:
                return 0
            
            # Get option premium (check both 'premium' and 'entry_price' fields)
            symbol = trade_signal.get('symbol', '')
            premium = trade_signal.get('premium', 0) or trade_signal.get('entry_price', 0)
            
            if premium <= 0:
                return 0
            
            # Calculate maximum risk per trade (2% of portfolio)
            max_risk_amount = self.portfolio_value * RiskConfig.MAX_POSITION_SIZE
            
            # Calculate position size based on premium and risk
            # For options: Risk = Premium * Quantity * Lot Size
            lot_size = 50  # Nifty options lot size
            
            # Conservative approach: Risk entire premium
            max_quantity = max_risk_amount / (premium * lot_size)
            
            # Apply confidence scaling
            confidence = trade_signal.get('confidence', 5)
            confidence_multiplier = min(confidence / 10.0, 1.0)
            
            scaled_quantity = max_quantity * confidence_multiplier
            
            # Round to lot multiples
            lots = max(1, int(scaled_quantity / lot_size))
            final_quantity = lots * lot_size
            
            # Ensure we don't exceed capital limits
            required_capital = final_quantity * premium
            if required_capital > max_risk_amount:
                final_quantity = int(max_risk_amount / premium)
                final_quantity = (final_quantity // lot_size) * lot_size
            
            logger.debug(f"📏 Position size: {final_quantity} (Capital req: ₹{final_quantity * premium:,.2f})")
            
            return final_quantity
            
        except Exception as e:
            logger.error(f"❌ Position size calculation failed: {e}")
            return 0
    
    def calculate_stop_loss(self, trade_signal: Dict[str, Any], entry_price: float) -> float:
        """Calculate stop loss price"""
        try:
            action = trade_signal.get('action', '').upper()
            confidence = trade_signal.get('confidence', 5)
            
            # Base stop loss percentage (20%)
            base_stop_percentage = RiskConfig.STOP_LOSS_PERCENTAGE
            
            # Adjust based on confidence (higher confidence = tighter stop)
            confidence_factor = 1.0 - (confidence - 5) * 0.02  # Reduce stop by 2% per confidence point above 5
            adjusted_stop_percentage = base_stop_percentage * confidence_factor
            
            if action == 'CALL':
                # For calls, stop loss is below entry price
                stop_loss = entry_price * (1 - adjusted_stop_percentage)
            else:  # PUT
                # For puts, stop loss is below entry price (puts lose value as underlying rises)
                stop_loss = entry_price * (1 - adjusted_stop_percentage)
            
            logger.debug(f"🛑 Stop loss calculated: ₹{stop_loss:.2f} ({adjusted_stop_percentage:.1%} from ₹{entry_price:.2f})")
            
            return stop_loss
            
        except Exception as e:
            logger.error(f"❌ Stop loss calculation failed: {e}")
            return entry_price * 0.8  # Default 20% stop loss
    
    def calculate_profit_target(self, trade_signal: Dict[str, Any], entry_price: float) -> float:
        """Calculate profit target price"""
        try:
            confidence = trade_signal.get('confidence', 5)
            
            # Base target (50% profit)
            base_target_percentage = RiskConfig.PROFIT_TARGET_2
            
            # Adjust based on confidence
            if confidence >= 8:
                target_percentage = RiskConfig.MAX_PROFIT_TARGET  # 100% for high confidence
            elif confidence >= 7:
                target_percentage = RiskConfig.PROFIT_TARGET_2   # 50%
            else:
                target_percentage = RiskConfig.PROFIT_TARGET_1   # 25%
            
            target_price = entry_price * (1 + target_percentage)
            
            logger.debug(f"🎯 Target calculated: ₹{target_price:.2f} ({target_percentage:.1%} from ₹{entry_price:.2f})")
            
            return target_price
            
        except Exception as e:
            logger.error(f"❌ Target calculation failed: {e}")
            return entry_price * 1.5  # Default 50% target
    
    def monitor_position(self, position: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Monitor existing position for risk management actions"""
        try:
            symbol = position.get('tradingsymbol', '')
            quantity = position.get('quantity', 0)
            pnl = float(position.get('pnl', 0))
            ltp = float(position.get('last_price', 0))
            
            if quantity == 0:
                return None  # No position to monitor
            
            # Check for stop loss
            if symbol in self.active_positions:
                entry_data = self.active_positions[symbol]
                entry_price = entry_data.get('average_price', ltp)
                
                # Calculate current loss percentage
                if entry_price > 0:
                    loss_percentage = (entry_price - ltp) / entry_price
                    
                    # Check stop loss trigger
                    if loss_percentage > RiskConfig.STOP_LOSS_PERCENTAGE:
                        logger.warning(f"🚨 Stop loss triggered for {symbol}: {loss_percentage:.1%} loss")
                        return {
                            'action': 'CLOSE_POSITION',
                            'reason': 'STOP_LOSS',
                            'symbol': symbol,
                            'quantity': abs(quantity),
                            'current_price': ltp
                        }
                    
                    # Check for profit target
                    profit_percentage = (ltp - entry_price) / entry_price if quantity > 0 else (entry_price - ltp) / entry_price
                    
                    if profit_percentage > RiskConfig.PROFIT_TARGET_1:
                        logger.info(f"🎯 Profit target reached for {symbol}: {profit_percentage:.1%} profit")
                        return {
                            'action': 'PARTIAL_CLOSE',
                            'reason': 'PROFIT_TARGET',
                            'symbol': symbol,
                            'quantity': abs(quantity) // 2,  # Close 50%
                            'current_price': ltp
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Position monitoring failed: {e}")
            return None
    
    def update_daily_pnl(self, pnl_change: float) -> None:
        """Update daily P&L and check limits"""
        self.daily_pnl += pnl_change
        
        # Check daily loss limit
        if self.daily_pnl < -TradingConfig.MAX_DAILY_LOSS:
            logger.error(f"🚨 Daily loss limit exceeded: ₹{self.daily_pnl:,.2f}")
    
    def record_trade(self, trade_result: Dict[str, Any]) -> None:
        """Record completed trade for risk tracking"""
        try:
            self.daily_trades += 1
            
            symbol = trade_result.get('symbol', '')
            pnl = trade_result.get('pnl', 0)
            
            # Update consecutive losses
            if pnl < 0:
                self.consecutive_losses += 1
                logger.debug(f"📉 Consecutive losses: {self.consecutive_losses}")
            else:
                self.consecutive_losses = 0
            
            # Update position tracking
            if trade_result.get('status') == 'SUCCESS':
                if symbol not in self.active_positions:
                    self.active_positions[symbol] = {
                        'quantity': trade_result.get('quantity', 0),
                        'average_price': trade_result.get('price', 0),
                        'pnl': 0,
                        'entry_time': datetime.now()
                    }
            
        except Exception as e:
            logger.error(f"❌ Failed to record trade: {e}")
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk summary"""
        try:
            portfolio_risk = (abs(self.daily_pnl) / max(self.portfolio_value, 1)) * 100
            
            return {
                'daily_trades': self.daily_trades,
                'max_daily_trades': TradingConfig.MAX_DAILY_TRADES,
                'daily_pnl': self.daily_pnl,
                'max_daily_loss': TradingConfig.MAX_DAILY_LOSS,
                'active_positions': len(self.active_positions),
                'max_positions': TradingConfig.MAX_POSITIONS,
                'consecutive_losses': self.consecutive_losses,
                'max_consecutive_losses': RiskConfig.MAX_CONSECUTIVE_LOSSES,
                'portfolio_risk_percentage': portfolio_risk,
                'trading_allowed': self.can_place_new_trade({'confidence': 6, 'symbol': 'TEST'})
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to generate risk summary: {e}")
            return {}

# Export classes
__all__ = ['OptionsRiskManager', 'RiskMetrics', 'TradeSignal']
