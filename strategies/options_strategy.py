#!/usr/bin/env python3
"""
Options Trading Strategies
Implementations of common options trading strategies for Nifty
"""

import logging
from datetime import datetime, time
from typing import List, Dict, Any, Optional, Tuple
import math

from .base_strategy import BaseStrategy, TradeSignal
from kiteconnect import KiteConnect
from risk_management.options_risk_manager import OptionsRiskManager
from utils.market_utils import MarketDataManager
from config.settings import OptionsConfig

logger = logging.getLogger(__name__)

class ATMStraddleStrategy(BaseStrategy):
    """
    At-The-Money Straddle Strategy
    Buys both Call and Put options at ATM strike
    Profits from high volatility in either direction
    """
    
    def __init__(self, 
                 kite_client: KiteConnect,
                 risk_manager: OptionsRiskManager,
                 market_data: MarketDataManager,
                 entry_time_start: str = "09:20",
                 entry_time_end: str = "10:00",
                 exit_time: str = "15:15",
                 max_loss_percent: float = 50.0,
                 profit_target_percent: float = 100.0,
                 volatility_threshold: float = 0.5,
                 **kwargs):
        """Initialize ATM Straddle Strategy"""
        super().__init__(kite_client, risk_manager, market_data, **kwargs)
        
        # Strategy parameters
        self.entry_time_start = datetime.strptime(entry_time_start, "%H:%M").time()
        self.entry_time_end = datetime.strptime(entry_time_end, "%H:%M").time()
        self.exit_time = datetime.strptime(exit_time, "%H:%M").time()
        self.max_loss_percent = max_loss_percent
        self.profit_target_percent = profit_target_percent
        self.volatility_threshold = volatility_threshold
        
        # Strategy state
        self.entry_executed = False
        self.straddle_positions: Dict[str, Dict] = {}
        
        logger.info(f"📊 ATM Straddle Strategy initialized - Entry: {entry_time_start}-{entry_time_end}")
    
    def get_strategy_name(self) -> str:
        return "ATM_Straddle"
    
    def generate_signals(self) -> List[TradeSignal]:
        """Generate ATM Straddle trading signals"""
        signals = []
        current_time = datetime.now().time()
        
        try:
            # Check if it's entry time and we haven't entered yet
            if (self.entry_time_start <= current_time <= self.entry_time_end and 
                not self.entry_executed and 
                not self.straddle_positions):
                
                # Get Nifty LTP for ATM strike calculation
                nifty_ltp = self._get_nifty_ltp()
                if nifty_ltp == 0:
                    return signals
                
                # Calculate ATM strike (nearest 50 multiple)
                atm_strike = round(nifty_ltp / 50) * 50
                
                # Check market volatility
                if self._check_volatility_conditions():
                    # Generate Call signal
                    ce_signal = self._create_option_signal(
                        strike=atm_strike,
                        option_type="CE",
                        action="BUY"
                    )
                    
                    # Generate Put signal
                    pe_signal = self._create_option_signal(
                        strike=atm_strike,
                        option_type="PE",
                        action="BUY"
                    )
                    
                    if ce_signal and pe_signal:
                        signals.extend([ce_signal, pe_signal])
                        logger.info(f"🎯 ATM Straddle signals generated for strike {atm_strike}")
            
            return signals
            
        except Exception as e:
            logger.error(f"❌ Error generating ATM Straddle signals: {e}")
            return signals
    
    def _get_nifty_ltp(self) -> float:
        """Get current Nifty 50 LTP"""
        try:
            nifty_token = '256265'  # NSE:NIFTY 50 token
            ltp_data = self.kite.ltp([nifty_token])
            if isinstance(ltp_data, dict) and nifty_token in ltp_data:
                token_data = ltp_data[nifty_token]
                if isinstance(token_data, dict) and 'last_price' in token_data:
                    return float(token_data['last_price'])
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error getting Nifty LTP: {e}")
            return 0.0
    
    def _check_volatility_conditions(self) -> bool:
        """Check if volatility conditions are met for entry"""
        try:
            # Simple volatility check based on price movement
            # In production, use VIX or calculate historical volatility
            current_time = datetime.now()
            if current_time.hour >= 9 and current_time.minute >= 30:
                return True  # Market is open and stable
            return False
        except Exception as e:
            logger.error(f"❌ Error checking volatility: {e}")
            return False
    
    def _create_option_signal(self, strike: float, option_type: str, action: str) -> Optional[TradeSignal]:
        """Create option trading signal"""
        try:
            # Get option symbol
            expiry = self._get_nearest_expiry()
            symbol = f"NIFTY{expiry.replace('-', '')}{int(strike)}{option_type}"
            
            # Get option LTP
            option_ltp = self._get_option_ltp(symbol)
            if option_ltp == 0:
                return None
            
            # Calculate position size
            quantity = self.risk_manager.calculate_position_size(
                entry_price=option_ltp,
                risk_amount=OptionsConfig.MAX_RISK_PER_TRADE
            )
            
            if quantity == 0:
                return None
            
            # Calculate stop loss and target
            stop_loss = option_ltp * (1 - self.max_loss_percent / 100)
            target = option_ltp * (1 + self.profit_target_percent / 100)
            
            signal = TradeSignal(
                symbol=symbol,
                action=f"{action}_{option_type}",
                strike_price=strike,
                option_type=option_type,
                quantity=quantity,
                confidence=8,  # High confidence for ATM straddle
                entry_price=option_ltp,
                stop_loss=stop_loss,
                target=target,
                reason=f"ATM Straddle {action} - Strike: {strike}, LTP: ₹{option_ltp}"
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error creating option signal: {e}")
            return None
    
    def _get_option_ltp(self, symbol: str) -> float:
        """Get option LTP"""
        try:
            quote_response = self.kite.quote([f"NFO:{symbol}"])
            if isinstance(quote_response, dict):
                option_data = quote_response.get(f"NFO:{symbol}", {})
                if isinstance(option_data, dict):
                    return float(option_data.get('last_price', 0))
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error getting option LTP for {symbol}: {e}")
            return 0.0
    
    def _get_nearest_expiry(self) -> str:
        """Get nearest Thursday expiry date"""
        from datetime import timedelta
        today = datetime.now()
        
        # Find next Thursday
        days_ahead = 3 - today.weekday()  # Thursday is 3
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        next_thursday = today + timedelta(days_ahead)
        return next_thursday.strftime('%Y-%m-%d')

class IronCondorStrategy(BaseStrategy):
    """
    Iron Condor Strategy
    Neutral strategy that profits from low volatility
    Sells OTM Call and Put, Buys further OTM options for protection
    """
    
    def __init__(self, 
                 kite_client: KiteConnect,
                 risk_manager: OptionsRiskManager,
                 market_data: MarketDataManager,
                 entry_time_start: str = "09:30",
                 entry_time_end: str = "10:30",
                 exit_time: str = "15:15",
                 wing_width: int = 100,  # Distance between strikes
                 max_loss_percent: float = 80.0,
                 profit_target_percent: float = 50.0,
                 **kwargs):
        """Initialize Iron Condor Strategy"""
        super().__init__(kite_client, risk_manager, market_data, **kwargs)
        
        # Strategy parameters
        self.entry_time_start = datetime.strptime(entry_time_start, "%H:%M").time()
        self.entry_time_end = datetime.strptime(entry_time_end, "%H:%M").time()
        self.exit_time = datetime.strptime(exit_time, "%H:%M").time()
        self.wing_width = wing_width
        self.max_loss_percent = max_loss_percent
        self.profit_target_percent = profit_target_percent
        
        # Strategy state
        self.entry_executed = False
        self.condor_positions: Dict[str, Dict] = {}
        
        logger.info(f"🦅 Iron Condor Strategy initialized - Wing Width: {wing_width}")
    
    def get_strategy_name(self) -> str:
        return "Iron_Condor"
    
    def generate_signals(self) -> List[TradeSignal]:
        """Generate Iron Condor trading signals"""
        signals = []
        current_time = datetime.now().time()
        
        try:
            # Check if it's entry time and we haven't entered yet
            if (self.entry_time_start <= current_time <= self.entry_time_end and 
                not self.entry_executed and 
                not self.condor_positions):
                
                # Get Nifty LTP for strike calculations
                nifty_ltp = self._get_nifty_ltp()
                if nifty_ltp == 0:
                    return signals
                
                # Calculate ATM strike
                atm_strike = round(nifty_ltp / 50) * 50
                
                # Check market conditions for Iron Condor
                if self._check_neutral_conditions():
                    # Iron Condor strikes
                    call_sell_strike = atm_strike + 50  # OTM Call to sell
                    call_buy_strike = call_sell_strike + self.wing_width  # Further OTM Call to buy
                    put_sell_strike = atm_strike - 50   # OTM Put to sell
                    put_buy_strike = put_sell_strike - self.wing_width   # Further OTM Put to buy
                    
                    # Generate all four signals
                    signals.extend([
                        # Call spread
                        self._create_condor_signal(call_sell_strike, "CE", "SELL"),
                        self._create_condor_signal(call_buy_strike, "CE", "BUY"),
                        # Put spread
                        self._create_condor_signal(put_sell_strike, "PE", "SELL"),
                        self._create_condor_signal(put_buy_strike, "PE", "BUY")
                    ])
                    
                    # Filter out None signals
                    signals = [s for s in signals if s is not None]
                    
                    if len(signals) == 4:
                        logger.info(f"🦅 Iron Condor signals generated: {call_buy_strike}/{call_sell_strike}/{put_sell_strike}/{put_buy_strike}")
                    else:
                        signals = []  # Don't execute partial Iron Condor
            
            return signals
            
        except Exception as e:
            logger.error(f"❌ Error generating Iron Condor signals: {e}")
            return signals
    
    def _check_neutral_conditions(self) -> bool:
        """Check if market conditions are suitable for Iron Condor"""
        try:
            # Check for low volatility/neutral market conditions
            # In production, check VIX levels, trend indicators, etc.
            current_time = datetime.now()
            
            # Simple check: market should be stable (not in pre-market rush)
            if current_time.hour >= 10:
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Error checking neutral conditions: {e}")
            return False
    
    def _create_condor_signal(self, strike: float, option_type: str, action: str) -> Optional[TradeSignal]:
        """Create Iron Condor component signal"""
        try:
            # Get option symbol
            expiry = self._get_nearest_expiry()
            symbol = f"NIFTY{expiry.replace('-', '')}{int(strike)}{option_type}"
            
            # Get option LTP
            option_ltp = self._get_option_ltp(symbol)
            if option_ltp == 0:
                return None
            
            # Calculate position size (same for all legs)
            quantity = self.risk_manager.calculate_position_size(
                entry_price=option_ltp,
                risk_amount=OptionsConfig.MAX_RISK_PER_TRADE // 4  # Divide by 4 legs
            )
            
            if quantity == 0:
                return None
            
            # For Iron Condor, stop loss and target depend on the entire position
            # Individual leg targets are not meaningful
            stop_loss = option_ltp * 0.5 if action == "SELL" else option_ltp * 2.0
            target = option_ltp * 1.5 if action == "SELL" else option_ltp * 0.5
            
            signal = TradeSignal(
                symbol=symbol,
                action=f"{action}_{option_type}",
                strike_price=strike,
                option_type=option_type,
                quantity=quantity,
                confidence=7,  # Good confidence for Iron Condor in right conditions
                entry_price=option_ltp,
                stop_loss=stop_loss,
                target=target,
                reason=f"Iron Condor {action} - Strike: {strike}, LTP: ₹{option_ltp}"
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Error creating condor signal: {e}")
            return None
    
    def _get_nifty_ltp(self) -> float:
        """Get current Nifty 50 LTP"""
        try:
            nifty_token = '256265'  # NSE:NIFTY 50 token
            ltp_data = self.kite.ltp([nifty_token])
            if isinstance(ltp_data, dict) and nifty_token in ltp_data:
                token_data = ltp_data[nifty_token]
                if isinstance(token_data, dict) and 'last_price' in token_data:
                    return float(token_data['last_price'])
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error getting Nifty LTP: {e}")
            return 0.0
    
    def _get_option_ltp(self, symbol: str) -> float:
        """Get option LTP"""
        try:
            quote_response = self.kite.quote([f"NFO:{symbol}"])
            if isinstance(quote_response, dict):
                option_data = quote_response.get(f"NFO:{symbol}", {})
                if isinstance(option_data, dict):
                    return float(option_data.get('last_price', 0))
            return 0.0
        except Exception as e:
            logger.error(f"❌ Error getting option LTP for {symbol}: {e}")
            return 0.0
    
    def _get_nearest_expiry(self) -> str:
        """Get nearest Thursday expiry date"""
        from datetime import timedelta
        today = datetime.now()
        
        # Find next Thursday
        days_ahead = 3 - today.weekday()  # Thursday is 3
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        next_thursday = today + timedelta(days_ahead)
        return next_thursday.strftime('%Y-%m-%d')

# Export strategy classes
__all__ = ['ATMStraddleStrategy', 'IronCondorStrategy']