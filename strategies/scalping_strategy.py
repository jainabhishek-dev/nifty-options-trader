"""
Supertrend Scalping Strategy for Options Trading (Long-Only)
===========================================================

This strategy implements a fast Supertrend approach for Nifty options:

1. **Timeframe**: 1-minute candles
2. **Approach**: Long-only (BUY_CALL/BUY_PUT signals only)  
3. **Indicators**: Supertrend (ATR Period: 3, Multiplier: 1.0)
4. **Risk Management**: 30% target, 10% trailing stop-loss, 30-minute time stop
5. **Position Size**: 75 lots per contract
6. **Strike Selection**: ATM ± 100 points
7. **Signal Frequency**: High-frequency trend change detection
"""

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
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
class ScalpingConfig:
    """Configuration parameters for supertrend scalping strategy"""
    rsi_period: int = 3          # ATR period for Supertrend
    rsi_oversold: float = 1.0    # ATR multiplier for Supertrend 
    rsi_overbought: float = 70.0 # Keep for compatibility
    volume_threshold: float = 1.0 # Sensitivity threshold
    price_change_threshold: float = 0.1  # Minimum price change %
    target_profit: float = 15.0  # 15% profit target
    stop_loss: float = 10.0      # 10% trailing stop loss
    time_stop_minutes: int = 30  # 30-minute time stop
    lot_size: int = 75           # Nifty option lot size
    strike_range: int = 100      # ATM ± 100 strikes
    signal_cooldown_seconds: int = 60  # Minimum seconds between opposite signals (0 to disable)


class ScalpingStrategy(BaseStrategy):
    """
    Supertrend-based scalping strategy for Nifty options (Long-Only)
    
    Signal Generation Logic:
    - BUY_CALL: Supertrend changes from bearish to bullish (trend reversal up)
    - BUY_PUT: Supertrend changes from bullish to bearish (trend reversal down)
    - Fast ATR(3) with multiplier 1.0 for high-frequency signals
    - 1-minute candle analysis for real-time execution
    """
    
    def __init__(self, config: ScalpingConfig = None, kite_manager=None, order_executor=None):
        self.strategy_config = config or ScalpingConfig()
        self.kite_manager = kite_manager  # Store kite_manager for real option chain access
        self.order_executor = order_executor  # Store order_executor for position checks
        
        # Convert config to dict for base class
        config_dict = {
            'atr_period': self.strategy_config.rsi_period,        # Use as ATR period (3)
            'atr_multiplier': self.strategy_config.rsi_oversold,  # Use as ATR multiplier (1.0)
            'target_profit': self.strategy_config.target_profit,
            'stop_loss': self.strategy_config.stop_loss,
            'lots_per_trade': 1
        }
        
        super().__init__("scalping", config_dict)
        self.data_buffer = pd.DataFrame()  # Store 1-minute OHLCV data
        self.current_trend = None         # Track current supertrend direction
        self.last_trend = None           # Track previous trend for change detection
        
        # CANDLE CLOSE CONFIRMATION: State tracking variables
        self._new_candle_arrived = False  # Flag when new closed candle is processed
        self._last_signal_time = None     # Timestamp of last signal (for cooldown)
        
    def update_market_data(self, ohlcv_data: pd.DataFrame) -> None:
        """
        Update strategy with new 1-minute market data for Supertrend calculation
        
        CRITICAL: Only use CLOSED candles, exclude last candle (incomplete/live from Kite API)
        
        Expected data format:
        - timestamp, open, high, low, close, volume
        - Data should be for Nifty 50 index (underlying)
        """
        try:
            # Ensure we have required columns
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in ohlcv_data.columns for col in required_cols):
                raise ValueError(f"Missing required columns. Expected: {required_cols}")
            
            # CRITICAL FIX: Remove last candle (incomplete/live data from Kite API)
            # Kite returns current candle with live price as 'close' - we need CLOSED candles only
            if len(ohlcv_data) > 1:
                closed_candles = ohlcv_data.iloc[:-1].copy()
            else:
                # If only 1 candle, can't exclude it - return early
                return
            
            # Check if we have new candle data (different from last processed)
            if len(self.data_buffer) > 0 and len(closed_candles) > 0:
                last_buffered_timestamp = self.data_buffer.iloc[-1]['timestamp']
                last_new_timestamp = closed_candles.iloc[-1]['timestamp']
                
                # Only process if we have genuinely NEW closed candle
                if last_new_timestamp <= last_buffered_timestamp:
                    return  # No new closed candles yet
                
                # New candle detected - add only candles newer than buffer
                new_candles = closed_candles[
                    closed_candles['timestamp'] > last_buffered_timestamp
                ]
                
                if len(new_candles) > 0:
                    self.data_buffer = pd.concat([self.data_buffer, new_candles])
                    self._new_candle_arrived = True  # Flag for signal generation
                    print(f"✅ New closed candle(s) arrived: {len(new_candles)} candle(s)")
            else:
                # First time initialization
                self.data_buffer = closed_candles.copy()
                self._new_candle_arrived = True
                print(f"📊 Initialized with {len(closed_candles)} closed candles")
            
            # Keep only last 50 candles for memory efficiency (sufficient for ATR(3))
            if len(self.data_buffer) > 50:
                self.data_buffer = self.data_buffer.tail(50).reset_index(drop=True)
                
            # Recalculate Supertrend on CLOSED candles only
            self._calculate_supertrend()
            
        except Exception as e:
            print(f"Error updating market data in supertrend scalping strategy: {e}")
    
    def _calculate_supertrend(self) -> None:
        """Calculate Supertrend indicator with ATR(3) and multiplier 1.0"""
        atr_period = self.strategy_config.rsi_period      # ATR period (3)
        atr_multiplier = self.strategy_config.rsi_oversold  # ATR multiplier (1.0)
        
        if len(self.data_buffer) < atr_period + 1:
            return
            
        try:
            # Calculate ATR
            self.data_buffer['atr'] = self._calculate_atr(atr_period)
            
            # Calculate basic upper and lower bands
            hl2 = (self.data_buffer['high'] + self.data_buffer['low']) / 2
            self.data_buffer['basic_upper'] = hl2 + (atr_multiplier * self.data_buffer['atr'])
            self.data_buffer['basic_lower'] = hl2 - (atr_multiplier * self.data_buffer['atr'])
            
            # Calculate final upper and lower bands
            self.data_buffer['final_upper'] = 0.0
            self.data_buffer['final_lower'] = 0.0
            
            for i in range(1, len(self.data_buffer)):
                # Final Upper Band
                if (self.data_buffer.loc[i, 'basic_upper'] < self.data_buffer.loc[i-1, 'final_upper'] or 
                    self.data_buffer.loc[i-1, 'close'] > self.data_buffer.loc[i-1, 'final_upper']):
                    self.data_buffer.loc[i, 'final_upper'] = self.data_buffer.loc[i, 'basic_upper']
                else:
                    self.data_buffer.loc[i, 'final_upper'] = self.data_buffer.loc[i-1, 'final_upper']
                
                # Final Lower Band
                if (self.data_buffer.loc[i, 'basic_lower'] > self.data_buffer.loc[i-1, 'final_lower'] or 
                    self.data_buffer.loc[i-1, 'close'] < self.data_buffer.loc[i-1, 'final_lower']):
                    self.data_buffer.loc[i, 'final_lower'] = self.data_buffer.loc[i, 'basic_lower']
                else:
                    self.data_buffer.loc[i, 'final_lower'] = self.data_buffer.loc[i-1, 'final_lower']
            
            # Determine Supertrend line and direction
            self.data_buffer['supertrend'] = 0.0
            self.data_buffer['trend'] = 'neutral'
            
            for i in range(1, len(self.data_buffer)):
                if i == 1:  # First calculation
                    if self.data_buffer.loc[i, 'close'] <= self.data_buffer.loc[i, 'final_lower']:
                        self.data_buffer.loc[i, 'supertrend'] = self.data_buffer.loc[i, 'final_lower']
                        self.data_buffer.loc[i, 'trend'] = 'bearish'
                    else:
                        self.data_buffer.loc[i, 'supertrend'] = self.data_buffer.loc[i, 'final_upper']
                        self.data_buffer.loc[i, 'trend'] = 'bullish'
                else:
                    # Subsequent calculations
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
                    else:  # prev_trend == 'bearish' and close >= final_upper
                        self.data_buffer.loc[i, 'supertrend'] = self.data_buffer.loc[i, 'final_lower']
                        self.data_buffer.loc[i, 'trend'] = 'bullish'
            
            # Update current trend with CANDLE CLOSE CONFIRMATION
            if len(self.data_buffer) > 0:
                new_trend = self.data_buffer.iloc[-1]['trend']
                
                # First initialization
                if self.current_trend is None:
                    self.current_trend = new_trend
                    self.last_trend = new_trend
                    print(f"🔵 Initial trend set: {new_trend}")
                    return
                
                # Check if trend changed in this CLOSED candle
                if new_trend != self.current_trend:
                    # Trend change detected and CONFIRMED immediately (candle closed on other side)
                    print(f"✅ Trend change CONFIRMED at candle close: {self.current_trend} → {new_trend}")
                    self.current_trend = new_trend
                    # Do NOT update last_trend here - only in generate_signals after signal created
                
        except Exception as e:
            print(f"Error calculating Supertrend: {e}")
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
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
    
    def generate_signals(self, timestamp: datetime, symbol_prices: Dict[str, float] = None, current_price: float = None) -> List[TradingSignal]:
        """
        Generate trading signals based on Supertrend trend changes
        
        Args:
            timestamp: Current timestamp
            symbol_prices: Dictionary of symbol prices for position monitoring
            current_price: Current Nifty price for BUY signal generation (backward compatibility)
        
        Returns list of signals for:
        - BUY signals when trend reversal is detected  
        - SELL signals when exit conditions are met for open positions
        """
        signals = []
        
        # First, check for SELL signals (exit conditions for open positions)
        if self.order_executor and hasattr(self.order_executor, 'positions') and symbol_prices:
            sell_signals = self._generate_sell_signals(timestamp, symbol_prices)
            signals.extend(sell_signals)
        
        # Need sufficient data for Supertrend calculation
        if len(self.data_buffer) < 10 or self.current_trend is None or self.last_trend is None:
            return signals
        
        # For BUY signal generation, we need current_price (Nifty spot price)
        # If not provided (e.g., during position monitoring), just return SELL signals
        if current_price is None:
            return signals
        
        # CRITICAL: Only generate BUY signals on NEW candle arrival
        # This ensures we're working with CLOSED candle data, not intra-candle
        if not self._new_candle_arrived:
            # No new candle - return only SELL signals (exit monitoring)
            return signals
        
        # Reset the flag after checking (will be set again on next new candle)
        self._new_candle_arrived = False
        
        try:
            latest = self.data_buffer.iloc[-1]
            
            # Check for Supertrend trend change (reversal detection)
            trend_changed = self.current_trend != self.last_trend
            
            if not trend_changed:
                return signals
            
            # Check signal cooldown (prevent rapid opposite signals)
            if self.strategy_config.signal_cooldown_seconds > 0 and self._last_signal_time is not None:
                time_since_last = (timestamp - self._last_signal_time).total_seconds()
                if time_since_last < self.strategy_config.signal_cooldown_seconds:
                    print(f"🚫 Signal cooldown active - {time_since_last:.0f}s since last signal (need {self.strategy_config.signal_cooldown_seconds}s)")
                    return signals
            
            print(f"✅ Confirmed trend change at candle boundary: {self.last_trend} → {self.current_trend}")
            
            # BUY_CALL Signal: Trend changed from bearish to bullish
            if self.last_trend == 'bearish' and self.current_trend == 'bullish':
                # Check for existing positions (anti-overtrading and anti-hedging)
                if self.order_executor and hasattr(self.order_executor, 'positions'):
                    # Block if PUT position exists (anti-hedging)
                    open_put_positions = [pos for pos in self.order_executor.positions.values() 
                                        if 'PE' in pos.symbol and pos.quantity > 0]
                    if len(open_put_positions) > 0:
                        print(f"🚫 Skipping BUY_CALL - have {len(open_put_positions)} open PUT position(s) (anti-hedging)")
                        return signals
                    
                    # Also check for existing CALL positions (anti-overtrading)
                    open_call_positions = [pos for pos in self.order_executor.positions.values() 
                                         if 'CE' in pos.symbol and pos.quantity > 0]
                    if len(open_call_positions) > 0:
                        print(f"🚫 Skipping BUY_CALL - already have {len(open_call_positions)} open CALL position(s)")
                        return signals
                
                call_symbols = self._get_real_option_symbols(current_price, 'CALL')
                for symbol in call_symbols:
                    # Extract strike price from real symbol for signal data
                    try:
                        # Extract strike from symbol like "NIFTY25122025800CE"
                        strike = int(symbol.split('NIFTY')[1][6:-2]) if len(symbol) > 10 else 0
                    except:
                        strike = round(current_price / 50) * 50  # Fallback to ATM
                    
                    signal = TradingSignal(
                        signal_type=SignalType.BUY_CALL,
                        symbol=symbol,  # Use real symbol from Kite Connect
                        strike_price=strike,
                        entry_price=0.0,  # Will be filled by execution engine
                        target_price=0.0,  # Will be calculated after entry
                        stop_loss_price=0.0,  # Will be calculated after entry
                        quantity=self._get_real_lot_size(symbol),  # Use real lot size from Kite
                        timestamp=timestamp,
                        confidence=85.0,  # High confidence for trend reversal
                        metadata={
                            'strategy': 'supertrend_scalping',
                            'trend_change': f'{self.last_trend} → {self.current_trend}',
                            'supertrend_level': latest.get('supertrend', 0),
                            'atr': latest.get('atr', 0),
                            'signal_reason': 'Bullish trend reversal (OTM Call)'
                        }
                    )
                    signals.append(signal)
                    print(f"Generated BUY_CALL signal: {signal.symbol} (bullish reversal)")
                
                # Update last_trend and last_signal_time AFTER signal generated
                self.last_trend = self.current_trend
                self._last_signal_time = timestamp
            
            # BUY_PUT Signal: Trend changed from bullish to bearish  
            elif self.last_trend == 'bullish' and self.current_trend == 'bearish':
                # Check for existing positions (anti-overtrading and anti-hedging)
                if self.order_executor and hasattr(self.order_executor, 'positions'):
                    # Block if CALL position exists (anti-hedging)
                    open_call_positions = [pos for pos in self.order_executor.positions.values() 
                                         if 'CE' in pos.symbol and pos.quantity > 0]
                    if len(open_call_positions) > 0:
                        print(f"🚫 Skipping BUY_PUT - have {len(open_call_positions)} open CALL position(s) (anti-hedging)")
                        return signals
                    
                    # Also check for existing PUT positions (anti-overtrading)
                    open_put_positions = [pos for pos in self.order_executor.positions.values() 
                                        if 'PE' in pos.symbol and pos.quantity > 0]
                    if len(open_put_positions) > 0:
                        print(f"🚫 Skipping BUY_PUT - already have {len(open_put_positions)} open PUT position(s)")
                        return signals
                
                put_symbols = self._get_real_option_symbols(current_price, 'PUT')
                for symbol in put_symbols:
                    # Extract strike price from real symbol for signal data
                    try:
                        # Extract strike from symbol like "NIFTY25122025800PE"
                        strike = int(symbol.split('NIFTY')[1][6:-2]) if len(symbol) > 10 else 0
                    except:
                        strike = round(current_price / 50) * 50  # Fallback to ATM
                    
                    signal = TradingSignal(
                        signal_type=SignalType.BUY_PUT,
                        symbol=symbol,  # Use real symbol from Kite Connect
                        strike_price=strike,
                        entry_price=0.0,  # Will be filled by execution engine
                        target_price=0.0,  # Will be calculated after entry
                        stop_loss_price=0.0,  # Will be calculated after entry
                        quantity=self._get_real_lot_size(symbol),  # Use real lot size from Kite
                        timestamp=timestamp,
                        confidence=85.0,  # High confidence for trend reversal
                        metadata={
                            'strategy': 'supertrend_scalping',
                            'trend_change': f'{self.last_trend} → {self.current_trend}',
                            'supertrend_level': latest.get('supertrend', 0),
                            'atr': latest.get('atr', 0),
                            'signal_reason': 'Bearish trend reversal (OTM Put)',
                            'underlying_price': current_price
                        }
                    )
                    signals.append(signal)
                    print(f"Generated BUY_PUT signal: {signal.symbol} (bearish reversal)")
                
                # Update last_trend and last_signal_time AFTER signal generated
                self.last_trend = self.current_trend
                self._last_signal_time = timestamp
            
        except Exception as e:
            print(f"Error generating scalping signals: {e}")
        
        return signals
    
    def _get_real_option_symbols(self, current_price: float, option_type: str) -> List[str]:
        """
        Get SINGLE OTM option symbol from Kite Connect instruments
        - For CALL: ATM+50 (OTM option for bullish trend)
        - For PUT: ATM-50 (OTM option for bearish trend)
        """
        if not self.kite_manager:
            print("[WARNING] No kite_manager available, using fallback symbols")
            return self._get_fallback_symbols(current_price, option_type)
        
        try:
            # Get real option chain from Kite Connect (without parameters to use nearest expiry)
            option_chain = self.kite_manager.get_option_chain()
            
            if not option_chain:
                print("[WARNING] No option chain data available, using fallback")
                return self._get_fallback_symbols(current_price, option_type)
            
            # Calculate ATM strike
            atm_strike = round(current_price / 50) * 50
            
            # Select single OTM strike based on strategy
            if option_type == 'CALL':
                # For bullish trend: Buy OTM Call (ATM+50)
                target_strike = atm_strike + 50
            else:  # PUT
                # For bearish trend: Buy OTM Put (ATM-50)
                target_strike = atm_strike - 50
            
            # Find the specific strike in option chain
            for option_data in option_chain:
                if option_data.get('strike') == target_strike:
                    if option_type == 'CALL' and 'ce_symbol' in option_data:
                        symbol = option_data['ce_symbol']
                        print(f"[SUCCESS] Found OTM CALL: {symbol} (Strike: {target_strike})")
                        return [symbol]  # Return single symbol
                    elif option_type == 'PUT' and 'pe_symbol' in option_data:
                        symbol = option_data['pe_symbol']
                        print(f"[SUCCESS] Found OTM PUT: {symbol} (Strike: {target_strike})")
                        return [symbol]  # Return single symbol
            
            # If not found, fallback
            print(f"⚠️ No real {option_type} symbol found for OTM strike {target_strike}")
            return self._get_fallback_symbols(current_price, option_type)
                
        except Exception as e:
            print(f"[ERROR] Error getting real option symbol: {e}")
            return self._get_fallback_symbols(current_price, option_type)
    
    def _get_fallback_symbols(self, current_price: float, option_type: str) -> List[str]:
        """Fallback method using manual symbol construction for single OTM strike"""
        atm_strike = round(current_price / 50) * 50
        
        # Select single OTM strike
        if option_type == 'CALL':
            # OTM Call: ATM+50
            strike = atm_strike + 50
        else:  # PUT
            # OTM Put: ATM-50
            strike = atm_strike - 50
        
        # Use nearest Thursday as expiry (this is the old problematic method)
        from datetime import datetime, timedelta
        today = datetime.now()
        days_ahead = (3 - today.weekday()) % 7  # Thursday is 3
        if days_ahead == 0:
            days_ahead = 7
        expiry_date = today + timedelta(days=days_ahead)
        expiry_str = expiry_date.strftime('%y%m%d')
        
        suffix = 'CE' if option_type == 'CALL' else 'PE'
        return [f"NIFTY{expiry_str}{strike}{suffix}"]  # Return single symbol
    
    def _calculate_confidence(self, rsi: float, volume: float, avg_volume: float) -> float:
        """Calculate signal confidence score (0.0 to 1.0)"""
        try:
            # RSI component (how extreme the RSI is)
            if rsi <= 30:
                rsi_score = (30 - rsi) / 30  # Higher score for lower RSI
            elif rsi >= 70:
                rsi_score = (rsi - 70) / 30  # Higher score for higher RSI
            else:
                rsi_score = 0
            
            # Volume component (how much above average)
            volume_ratio = volume / avg_volume
            volume_score = min(volume_ratio / 3.0, 1.0)  # Cap at 1.0
            
            # Combined confidence
            confidence = (rsi_score * 0.6 + volume_score * 0.4)
            return min(max(confidence, 0.0), 1.0)
            
        except:
            return 0.5  # Default moderate confidence
    
    def should_exit_position(self, position: Position, current_price: float, timestamp: datetime) -> Tuple[bool, str]:
        """
        Check if position should be exited based on supertrend scalping rules
        
        Exit conditions:
        1. 30% profit target reached
        2. 10% trailing stop loss reached  
        3. 30-minute time stop reached
        4. Minimum 5-second hold time (prevents rapid exits)
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
            
            # ===== TRAILING STOP LOSS: Track highest price reached =====
            # Initialize highest_price if not set (backward compatibility with existing positions)
            if position.highest_price is None:
                position.highest_price = position.entry_price
            
            # Update highest price if current price is higher (lock in gains)
            if current_price > position.highest_price:
                old_peak = position.highest_price
                position.highest_price = current_price
                print(f"📈 New peak for {position.symbol}: ₹{old_peak:.2f} → ₹{current_price:.2f}")
            
            # Calculate current P&L percentage from entry
            pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            
            # Profit target check (30%)
            if pnl_pct >= self.strategy_config.target_profit:
                return True, f"Profit target reached: {pnl_pct:.1f}% >= {self.strategy_config.target_profit}%"
            
            # TRAILING STOP LOSS: Exit if price drops 10% from highest price reached
            peak_drawdown_pct = ((current_price - position.highest_price) / position.highest_price) * 100
            if peak_drawdown_pct <= -self.strategy_config.stop_loss:
                return True, f"Trailing stop loss: {peak_drawdown_pct:.1f}% from peak ₹{position.highest_price:.2f} (P&L: {pnl_pct:+.1f}%)"
            
            # Time stop check (30 minutes)
            if time_elapsed >= timedelta(minutes=self.strategy_config.time_stop_minutes):
                return True, f"Time stop reached: {time_elapsed.total_seconds()/60:.0f}min >= {self.strategy_config.time_stop_minutes}min"
            
            return False, f"Continue holding (P&L: {pnl_pct:+.2f}%, Peak: ₹{position.highest_price:.2f}, Drawdown: {peak_drawdown_pct:.2f}%)"
            
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
        elif "calculation error" in exit_reason:
            return "ERROR"
        elif "Minimum hold" in exit_reason:
            return "MIN_HOLD_TIME"
        else:
            return "OTHER"
    
    def _get_real_lot_size(self, symbol: str) -> int:
        """
        Get real lot size from Kite Connect instruments data
        Falls back to configured lot size if not found
        """
        if not self.kite_manager or not self.kite_manager.instruments:
            return self.strategy_config.lot_size  # Fallback to configured size
        
        try:
            # Look up instrument data for this symbol
            instrument = self.kite_manager.instruments.get(symbol)
            if instrument and 'lot_size' in instrument:
                real_lot_size = int(instrument['lot_size'])
                print(f"[INFO] Real lot size for {symbol}: {real_lot_size}")
                return real_lot_size
            else:
                print(f"[WARNING] No lot size found for {symbol}, using configured: {self.strategy_config.lot_size}")
                return self.strategy_config.lot_size
                
        except Exception as e:
            print(f"[ERROR] Error getting lot size for {symbol}: {e}")
            return self.strategy_config.lot_size  # Fallback
    
    def get_position_size(self, signal: TradingSignal, available_capital: float) -> int:
        """
        Calculate position size for scalping strategy using real lot size
        """
        return self._get_real_lot_size(signal.symbol)
    
    def get_strategy_parameters(self) -> Dict[str, Any]:
        """Return current strategy parameters for UI display"""
        return {
            'atr_period': self.strategy_config.rsi_period,        # ATR period (3)
            'atr_multiplier': self.strategy_config.rsi_oversold,  # ATR multiplier (1.0)  
            'target_profit': f"{self.strategy_config.target_profit}%",
            'stop_loss': f"{self.strategy_config.stop_loss}%",
            'time_stop_minutes': self.strategy_config.time_stop_minutes,
            'lot_size': self.strategy_config.lot_size,
            'strike_range': f"ATM ± {self.strategy_config.strike_range}",
            'timeframe': '1-minute',
            'algorithm': 'Supertrend'
        }
    
    def _generate_sell_signals(self, timestamp: datetime, symbol_prices: Dict[str, float]) -> List[TradingSignal]:
        """
        Generate SELL signals for open positions that meet exit conditions
        
        Args:
            timestamp: Current timestamp
            symbol_prices: Dictionary mapping symbols to their current prices
        """
        sell_signals = []
        
        try:
            # Check all open positions for exit conditions
            for position_key, position in self.order_executor.positions.items():
                if getattr(position, 'is_closed', False):
                    continue  # Skip closed positions
                
                # Get the correct current price for THIS specific position
                current_price = symbol_prices.get(position.symbol, 0)
                
                if current_price <= 0:
                    print(f"⚠️  No price available for {position.symbol}, skipping exit check")
                    continue
                
                # Update position current price for exit calculation
                position.current_price = current_price
                
                # Check if this position should exit
                should_exit, reason = self.should_exit_position(position, current_price, timestamp)
                
                if should_exit:
                    # Determine SELL signal type based on position type
                    if position.signal_type == SignalType.BUY_CALL:
                        sell_signal_type = SignalType.SELL_CALL
                    elif position.signal_type == SignalType.BUY_PUT:
                        sell_signal_type = SignalType.SELL_PUT
                    else:
                        continue  # Unknown position type
                    
                    # Extract strike price from symbol
                    strike_price = self._extract_strike_from_symbol(position.symbol)
                    
                    # Calculate target and stop loss prices based on entry price
                    target_price = position.entry_price * (1 + self.strategy_config.target_profit / 100)
                    stop_loss_price = position.entry_price * (1 - self.strategy_config.stop_loss / 100)
                    
                    # Create SELL signal with all required fields
                    sell_signal = TradingSignal(
                        signal_type=sell_signal_type,
                        symbol=position.symbol,
                        strike_price=strike_price,
                        entry_price=position.entry_price,
                        target_price=target_price,
                        stop_loss_price=stop_loss_price,
                        quantity=position.quantity,
                        timestamp=timestamp,
                        confidence=1.0,  # High confidence for exit conditions
                        metadata={
                            'strategy': self.name,
                            'exit_reason': reason,
                            'exit_reason_category': self.get_exit_reason_category(reason),
                            'is_closing_order': True,
                            'original_entry_price': position.entry_price,
                            'original_entry_time': position.entry_time.isoformat() if hasattr(position.entry_time, 'isoformat') else str(position.entry_time),
                            'position_key': position_key  # Track which position this closes
                        }
                    )
                    
                    sell_signals.append(sell_signal)
                    print(f"🔴 Generated SELL signal: {position.symbol} @ Rs.{current_price:.2f} - {reason}")
        
        except Exception as e:
            print(f"Error generating SELL signals: {e}")
        
        return sell_signals
    
    def _extract_strike_from_symbol(self, symbol: str) -> int:
        """
        Extract strike price from option symbol
        
        Examples:
        - NIFTY25D1625850CE -> 25850
        - NIFTY25122025800PE -> 25800
        
        Returns:
            Strike price as integer, or 0 if extraction fails
        """
        try:
            # Pattern: Extract last 5 digits before CE/PE
            # NIFTY25D16[25850]CE or NIFTY251220[25800]PE
            import re
            
            # Match exactly 5 digits before CE/PE (standard Nifty strike format)
            match = re.search(r'(\d{5})(CE|PE)$', symbol)
            if match:
                return int(match.group(1))
            
            # Fallback: Match 4-6 digits before CE/PE
            match = re.search(r'(\d{4,6})(CE|PE)$', symbol)
            if match:
                return int(match.group(1))
                
        except Exception as e:
            print(f"Warning: Could not extract strike from {symbol}: {e}")
        
        return 0  # Return 0 if extraction fails
    
    def get_strategy_stats(self) -> Dict:
        """Return current strategy statistics"""
        latest_data = self.data_buffer.iloc[-1] if not self.data_buffer.empty else {}
        return {
            'strategy_name': self.name,
            'data_points': len(self.data_buffer),
            'current_trend': self.current_trend,
            'last_trend_change': f"{self.last_trend} → {self.current_trend}" if self.last_trend and self.current_trend else None,
            'current_atr': latest_data.get('atr', None),
            'supertrend_level': latest_data.get('supertrend', None),
            'parameters': self.get_strategy_parameters()
        }