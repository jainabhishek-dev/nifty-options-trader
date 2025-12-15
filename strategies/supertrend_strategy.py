"""
Supertrend Strategy for Options Trading (Long-Only)
===================================================

This strategy implements a trend-following approach using the Supertrend indicator:

1. **Timeframe**: 15-minute candles
2. **Approach**: Long-only (BUY_CALL/BUY_PUT signals only)
3. **Indicator**: Supertrend (ATR-based trend detection)
4. **Risk Management**: 40% target, 50% stop-loss, 2-hour time stop
5. **Position Size**: 1 lot (75 shares per contract)
6. **Strike Selection**: ATM ± 150 points for trend following
"""

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from .base_strategy import BaseStrategy, TradingSignal, SignalType, Position


def get_weekly_expiry_date(current_date: datetime) -> datetime:
    """
    Calculate the correct weekly expiry date for NIFTY options.
    Expiry is on Thursday, but skip market holidays like Christmas.
    
    Args:
        current_date: Current trading date
        
    Returns:
        Next valid Thursday expiry date
    """
    # Find next Thursday
    days_until_thursday = (3 - current_date.weekday()) % 7
    if days_until_thursday == 0:  # If today is Thursday
        days_until_thursday = 7   # Get next Thursday
    
    expiry_date = current_date + timedelta(days=days_until_thursday)
    
    # Check for market holidays and skip them
    # Christmas (25th December) - skip to next valid Thursday
    if expiry_date.month == 12 and expiry_date.day == 25:
        # Skip Christmas, go to next Thursday (26th Dec if it's Thursday, or next week)
        expiry_date = expiry_date + timedelta(days=7)
    
    # Add more holidays here as needed
    # New Year's Day (1st January)
    if expiry_date.month == 1 and expiry_date.day == 1:
        expiry_date = expiry_date + timedelta(days=7)
    
    return expiry_date


@dataclass
class SupertrendConfig:
    """Configuration parameters for supertrend strategy"""
    atr_period: int = 10
    atr_multiplier: float = 3.0
    target_profit: float = 40.0  # 40% profit target
    stop_loss: float = 50.0  # 50% stop loss
    time_stop_minutes: int = 120  # 2-hour time stop
    lot_size: int = 75  # Nifty option lot size
    strike_range: int = 150  # ATM ± 150 strikes
    min_trend_candles: int = 3  # Minimum candles to confirm trend


class SupertrendStrategy(BaseStrategy):
    """
    Long-only supertrend strategy for Nifty options
    
    Signal Generation Logic:
    - BUY_CALL: Price breaks above Supertrend line (bullish trend)
    - BUY_PUT: Price breaks below Supertrend line (bearish trend)
    - Uses ATR-based dynamic support/resistance levels
    """
    
    def __init__(self, config: SupertrendConfig = None, kite_manager=None):
        self.strategy_config = config or SupertrendConfig()
        self.kite_manager = kite_manager  # Store kite_manager for real option chain access
        # Convert config to dictionary for base class
        config_dict = {
            'atr_period': self.strategy_config.atr_period,
            'atr_multiplier': self.strategy_config.atr_multiplier,
            'target_profit': self.strategy_config.target_profit,
            'stop_loss': self.strategy_config.stop_loss,
            'time_stop_minutes': self.strategy_config.time_stop_minutes,
            'lot_size': self.strategy_config.lot_size
        }
        super().__init__("Supertrend Strategy (Long-Only)", config_dict)
        self.data_buffer = pd.DataFrame()  # Store 15-minute OHLCV data
        self.current_trend = None  # 'bullish', 'bearish', or None
        self.trend_start_time = None
        
    def update_market_data(self, ohlcv_data: pd.DataFrame) -> None:
        """
        Update strategy with new 15-minute market data
        
        Expected data format:
        - timestamp, open, high, low, close, volume
        - Data should be for Nifty 50 index (underlying)
        """
        try:
            # Ensure we have required columns
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in ohlcv_data.columns for col in required_cols):
                raise ValueError(f"Missing required columns. Expected: {required_cols}")
            
            # Append new data to buffer
            self.data_buffer = pd.concat([self.data_buffer, ohlcv_data])
            
            # Keep only last 200 candles for memory efficiency
            if len(self.data_buffer) > 200:
                self.data_buffer = self.data_buffer.tail(200).reset_index(drop=True)
                
            # Calculate supertrend indicator
            self._calculate_supertrend()
            
        except Exception as e:
            print(f"Error updating market data in supertrend strategy: {e}")
    
    def _calculate_supertrend(self) -> None:
        """Calculate Supertrend indicator using ATR"""
        if len(self.data_buffer) < self.strategy_config.atr_period + 1:
            return
            
        try:
            # Calculate ATR (Average True Range)
            self.data_buffer['atr'] = self._calculate_atr(self.strategy_config.atr_period)
            
            # Calculate basic upper and lower bands
            hl2 = (self.data_buffer['high'] + self.data_buffer['low']) / 2
            self.data_buffer['basic_upper'] = hl2 + (self.strategy_config.atr_multiplier * self.data_buffer['atr'])
            self.data_buffer['basic_lower'] = hl2 - (self.strategy_config.atr_multiplier * self.data_buffer['atr'])
            
            # Calculate final upper and lower supertrend bands
            self.data_buffer['final_upper'] = self.data_buffer['basic_upper']
            self.data_buffer['final_lower'] = self.data_buffer['basic_lower']
            
            # Apply supertrend logic
            for i in range(1, len(self.data_buffer)):
                # Final upper band
                if (self.data_buffer.loc[i, 'basic_upper'] < self.data_buffer.loc[i-1, 'final_upper'] or 
                    self.data_buffer.loc[i-1, 'close'] > self.data_buffer.loc[i-1, 'final_upper']):
                    self.data_buffer.loc[i, 'final_upper'] = self.data_buffer.loc[i, 'basic_upper']
                else:
                    self.data_buffer.loc[i, 'final_upper'] = self.data_buffer.loc[i-1, 'final_upper']
                
                # Final lower band
                if (self.data_buffer.loc[i, 'basic_lower'] > self.data_buffer.loc[i-1, 'final_lower'] or 
                    self.data_buffer.loc[i-1, 'close'] < self.data_buffer.loc[i-1, 'final_lower']):
                    self.data_buffer.loc[i, 'final_lower'] = self.data_buffer.loc[i, 'basic_lower']
                else:
                    self.data_buffer.loc[i, 'final_lower'] = self.data_buffer.loc[i-1, 'final_lower']
            
            # Determine supertrend line and direction
            self.data_buffer['supertrend'] = np.nan
            self.data_buffer['trend'] = 'neutral'
            
            for i in range(1, len(self.data_buffer)):
                if pd.isna(self.data_buffer.loc[i-1, 'supertrend']):
                    # First calculation
                    if self.data_buffer.loc[i, 'close'] <= self.data_buffer.loc[i, 'final_lower']:
                        self.data_buffer.loc[i, 'supertrend'] = self.data_buffer.loc[i, 'final_lower']
                        self.data_buffer.loc[i, 'trend'] = 'bearish'
                    else:
                        self.data_buffer.loc[i, 'supertrend'] = self.data_buffer.loc[i, 'final_upper']
                        self.data_buffer.loc[i, 'trend'] = 'bullish'
                else:
                    # Subsequent calculations
                    prev_supertrend = self.data_buffer.loc[i-1, 'supertrend']
                    prev_trend = self.data_buffer.loc[i-1, 'trend']
                    
                    if (prev_trend == 'bullish' and 
                        self.data_buffer.loc[i, 'close'] > self.data_buffer.loc[i, 'final_lower']):
                        self.data_buffer.loc[i, 'supertrend'] = self.data_buffer.loc[i, 'final_lower']
                        self.data_buffer.loc[i, 'trend'] = 'bullish'
                    elif (prev_trend == 'bullish' and 
                          self.data_buffer.loc[i, 'close'] <= self.data_buffer.loc[i, 'final_lower']):
                        self.data_buffer.loc[i, 'supertrend'] = self.data_buffer.loc[i, 'final_upper']
                        self.data_buffer.loc[i, 'trend'] = 'bearish'
                    elif (prev_trend == 'bearish' and 
                          self.data_buffer.loc[i, 'close'] < self.data_buffer.loc[i, 'final_upper']):
                        self.data_buffer.loc[i, 'supertrend'] = self.data_buffer.loc[i, 'final_upper']
                        self.data_buffer.loc[i, 'trend'] = 'bearish'
                    elif (prev_trend == 'bearish' and 
                          self.data_buffer.loc[i, 'close'] >= self.data_buffer.loc[i, 'final_upper']):
                        self.data_buffer.loc[i, 'supertrend'] = self.data_buffer.loc[i, 'final_lower']
                        self.data_buffer.loc[i, 'trend'] = 'bullish'
                    else:
                        self.data_buffer.loc[i, 'supertrend'] = prev_supertrend
                        self.data_buffer.loc[i, 'trend'] = prev_trend
            
        except Exception as e:
            print(f"Error calculating supertrend: {e}")
    
    def _calculate_atr(self, period: int) -> pd.Series:
        """Calculate Average True Range"""
        high = self.data_buffer['high']
        low = self.data_buffer['low']
        close_prev = self.data_buffer['close'].shift(1)
        
        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(period).mean()
        
        return atr
    
    def generate_signals(self, current_price: float, timestamp: datetime) -> List[TradingSignal]:
        """
        Generate long-only trading signals based on supertrend
        
        Returns list of signals (can be empty if no signals)
        """
        signals = []
        
        # Need sufficient data
        if len(self.data_buffer) < self.strategy_config.atr_period + 10:
            return signals
        
        try:
            # Get last few candles for trend analysis
            recent_data = self.data_buffer.tail(5)
            
            if 'trend' not in recent_data.columns or recent_data['trend'].isna().all():
                return signals
            
            current_trend = recent_data['trend'].iloc[-1]
            prev_trend = recent_data['trend'].iloc[-2] if len(recent_data) > 1 else current_trend
            
            # Check for trend change (signal generation)
            trend_changed = current_trend != prev_trend
            
            if not trend_changed:
                return signals
            
            # Count consecutive trend candles for confirmation
            trend_candles = 1
            for i in range(len(recent_data) - 2, -1, -1):
                if recent_data['trend'].iloc[i] == current_trend:
                    trend_candles += 1
                else:
                    break
            
            # Require minimum trend confirmation
            if trend_candles < self.strategy_config.min_trend_candles:
                return signals
            
            # Get current supertrend level and ATR for signal strength
            current_supertrend = recent_data['supertrend'].iloc[-1]
            current_atr = recent_data['atr'].iloc[-1]
            
            if pd.isna(current_supertrend) or pd.isna(current_atr):
                return signals
            
            # Calculate signal strength based on price distance from supertrend
            price_distance = abs(current_price - current_supertrend)
            signal_strength = min(price_distance / current_atr, 2.0) / 2.0  # Normalize 0-1
            
            # Generate signals based on trend direction
            if current_trend == 'bullish' and prev_trend == 'bearish':
                # Bullish trend - generate CALL signals using real option symbols
                call_symbols = self._get_real_option_symbols(current_price, 'CALL')
                for symbol in call_symbols:
                    # Extract strike price from the real trading symbol
                    try:
                        # Parse strike from symbol like "NIFTY25JAN25000CE" 
                        strike_match = re.search(r'(\d+)(CE|PE)', symbol)
                        strike = int(strike_match.group(1)) if strike_match else 0
                    except:
                        strike = 0
                    
                    signal = TradingSignal(
                        signal_type=SignalType.BUY_CALL,
                        symbol=symbol,  # Use real trading symbol from Kite Connect
                        strike_price=strike,
                        entry_price=0.0,  # Will be filled by execution engine
                        target_price=0.0,  # Will be calculated after entry
                        stop_loss_price=0.0,  # Will be calculated after entry
                        quantity=self.strategy_config.lot_size,
                        timestamp=timestamp,
                        confidence=signal_strength,
                        metadata={
                            'strategy': 'supertrend',
                            'trend': current_trend,
                            'supertrend_level': current_supertrend,
                            'atr': current_atr,
                            'price_distance': price_distance,
                            'trend_candles': trend_candles,
                            'underlying_price': current_price
                        }
                    )
                    signals.append(signal)
                    
            elif current_trend == 'bearish' and prev_trend == 'bullish':
                # Bearish trend - generate PUT signals using real option symbols
                put_symbols = self._get_real_option_symbols(current_price, 'PUT')
                for symbol in put_symbols:
                    # Extract strike price from the real trading symbol
                    try:
                        # Parse strike from symbol like "NIFTY25JAN25000PE" 
                        strike_match = re.search(r'(\d+)(CE|PE)', symbol)
                        strike = int(strike_match.group(1)) if strike_match else 0
                    except:
                        strike = 0
                    
                    signal = TradingSignal(
                        signal_type=SignalType.BUY_PUT,
                        symbol=symbol,  # Use real trading symbol from Kite Connect
                        strike_price=strike,
                        entry_price=0.0,  # Will be filled by execution engine
                        target_price=0.0,  # Will be calculated after entry
                        stop_loss_price=0.0,  # Will be calculated after entry
                        quantity=self.strategy_config.lot_size,
                        timestamp=timestamp,
                        confidence=signal_strength,
                        metadata={
                            'strategy': 'supertrend',
                            'trend': current_trend,
                            'supertrend_level': current_supertrend,
                            'atr': current_atr,
                            'price_distance': price_distance,
                            'trend_candles': trend_candles,
                            'underlying_price': current_price
                        }
                    )
                    signals.append(signal)
            
            # Update internal trend tracking
            if signals:
                self.current_trend = current_trend
                self.trend_start_time = timestamp
                print(f"Supertrend signal: {current_trend} trend detected with {len(signals)} signals")
            
        except Exception as e:
            print(f"Error generating supertrend signals: {e}")
        
        return signals
    
    def _get_real_option_symbols(self, current_price: float, option_type: str) -> List[str]:
        """
        Get real option symbols from Kite Connect option chain for supertrend strategy
        
        Uses wider strike range (ATM ± 150) for trend following
        """
        try:
            # Get real option chain from Kite Connect (without parameters to use nearest expiry)
            option_chain = self.kite_manager.get_option_chain()
            if not option_chain:
                return []
            
            atm_strike = round(current_price / 50) * 50  # Round to nearest 50
            
            if option_type == 'CALL':
                # For calls in bullish trend, use ATM and slightly ITM/OTM
                target_strikes = [
                    atm_strike - 100,  # ITM
                    atm_strike - 50,   # ITM
                    atm_strike,        # ATM
                    atm_strike + 50    # OTM
                ]
            else:  # PUT
                # For puts in bearish trend, use ATM and slightly ITM/OTM
                target_strikes = [
                    atm_strike + 100,  # ITM
                    atm_strike + 50,   # ITM
                    atm_strike,        # ATM
                    atm_strike - 50    # OTM
                ]
            
            # Extract real trading symbols from option chain
            real_symbols = []
            for option_data in option_chain:
                if option_data.get('strike') in target_strikes:
                    if option_type == 'CALL' and 'ce_symbol' in option_data:
                        real_symbols.append(option_data['ce_symbol'])
                    elif option_type == 'PUT' and 'pe_symbol' in option_data:
                        real_symbols.append(option_data['pe_symbol'])
            
            return real_symbols
            
        except Exception as e:
            print(f"Error getting real option symbols: {e}")
            return []
    
    def should_exit_position(self, position: Position, current_price: float, timestamp: datetime) -> Tuple[bool, str]:
        """
        Check if position should be exited based on supertrend rules
        
        Exit conditions:
        1. 40% profit target reached
        2. 50% stop loss reached  
        3. 2-hour time stop reached
        4. Supertrend trend reversal
        5. Minimum 5-second hold time (prevents rapid exits)
        """
        try:
            # Data validation - ensure position has valid data
            if not hasattr(position, 'entry_price') or position.entry_price is None or position.entry_price <= 0:
                print(f"Warning: Invalid entry price for position: {getattr(position, 'symbol', 'unknown')}")
                return False, "Continue holding - invalid entry price"
            
            if not hasattr(position, 'entry_time') or position.entry_time is None:
                print(f"Warning: Invalid entry time for position: {getattr(position, 'symbol', 'unknown')}")
                return False, "Continue holding - invalid entry time"
            
            if current_price is None or current_price <= 0:
                print(f"Warning: Invalid current price: {current_price}")
                return False, "Continue holding - invalid current price"
            
            # Calculate time elapsed since position entry
            time_elapsed = timestamp - position.entry_time
            
            # MINIMUM HOLD TIME: Prevent exits within first 5 seconds (prevents race conditions)
            if time_elapsed < timedelta(seconds=5):
                return False, f"Minimum hold time not reached ({time_elapsed.total_seconds():.1f}s < 5s)"
            
            # Calculate current P&L percentage
            pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            
            # Profit target check (40%)
            if pnl_pct >= self.strategy_config.target_profit:
                return True, f"Profit target reached: {pnl_pct:.1f}% >= {self.strategy_config.target_profit}%"
            
            # Stop loss check (50%)
            if pnl_pct <= -self.strategy_config.stop_loss:
                return True, f"Stop loss triggered: {pnl_pct:.1f}% <= -{self.strategy_config.stop_loss}%"
            
            # Time stop check (2 hours)
            if time_elapsed >= timedelta(minutes=self.strategy_config.time_stop_minutes):
                return True, f"Time stop reached: {time_elapsed.total_seconds()/60:.0f}min >= {self.strategy_config.time_stop_minutes}min"
            
            # Trend reversal check
            if len(self.data_buffer) > 0 and 'trend' in self.data_buffer.columns:
                current_trend = self.data_buffer['trend'].iloc[-1]
                
                # Check if trend has reversed from position direction
                if ((position.signal_type == SignalType.BUY_CALL and current_trend == 'bearish') or
                    (position.signal_type == SignalType.BUY_PUT and current_trend == 'bullish')):
                    return True, f"Trend reversal: position={position.signal_type.value}, trend={current_trend}"
            
            return False, f"Continue holding (P&L: {pnl_pct:+.2f}%, Time: {time_elapsed.total_seconds():.0f}s)"
            
        except Exception as e:
            # CRITICAL FIX: Don't force exit on exceptions - continue holding and log error
            print(f"Error in exit condition calculation for position {getattr(position, 'symbol', 'unknown')}: {e}")
            print(f"Position data: entry_price={getattr(position, 'entry_price', 'None')}, entry_time={getattr(position, 'entry_time', 'None')}")
            print(f"Current price: {current_price}, Timestamp: {timestamp}")
            return False, f"Continue holding - calculation error: {str(e)[:50]}"
            
    def get_exit_reason_category(self, exit_reason: str) -> str:
        """
        Categorize exit reason for database storage and UI display
        """
        if "Profit target" in exit_reason:
            return "PROFIT_TARGET"
        elif "Stop loss" in exit_reason:
            return "STOP_LOSS"
        elif "Time stop" in exit_reason:
            return "TIME_STOP"
        elif "Trend reversal" in exit_reason:
            return "TREND_REVERSAL"
        elif "calculation error" in exit_reason:
            return "ERROR"
        elif "Minimum hold" in exit_reason:
            return "MIN_HOLD_TIME"
        else:
            return "OTHER"
    
    def get_position_size(self, signal: TradingSignal, available_capital: float) -> int:
        """
        Calculate position size for supertrend strategy
        
        Fixed lot size approach for trend following
        """
        return self.strategy_config.lot_size
    
    def get_strategy_parameters(self) -> Dict[str, Any]:
        """Return current strategy parameters for UI display"""
        return {
            'atr_period': self.strategy_config.atr_period,
            'atr_multiplier': self.strategy_config.atr_multiplier,
            'target_profit': f"{self.strategy_config.target_profit}%",
            'stop_loss': f"{self.strategy_config.stop_loss}%",
            'time_stop': f"{self.strategy_config.time_stop_minutes} minutes",
            'lot_size': self.strategy_config.lot_size,
            'strike_range': f"ATM ± {self.strategy_config.strike_range}",
            'min_trend_candles': self.strategy_config.min_trend_candles
        }
    
    def get_strategy_stats(self) -> Dict:
        """Return current strategy statistics"""
        current_trend = None
        supertrend_level = None
        current_atr = None
        
        if not self.data_buffer.empty and 'trend' in self.data_buffer.columns:
            current_trend = self.data_buffer['trend'].iloc[-1]
            if 'supertrend' in self.data_buffer.columns:
                supertrend_level = self.data_buffer['supertrend'].iloc[-1]
            if 'atr' in self.data_buffer.columns:
                current_atr = self.data_buffer['atr'].iloc[-1]
        
        return {
            'strategy_name': self.name,
            'data_points': len(self.data_buffer),
            'current_trend': current_trend,
            'supertrend_level': supertrend_level,
            'current_atr': current_atr,
            'trend_start_time': self.trend_start_time.isoformat() if self.trend_start_time else None,
            'parameters': self.get_strategy_parameters()
        }