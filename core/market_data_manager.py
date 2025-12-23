"""
Market Data Manager
==================

Handles real-time market data fetching from Kite Connect API for strategy execution.
Provides:
1. Live OHLCV data for Nifty 50 index
2. Option chain data for strike selection
3. Real-time option prices for order execution
4. Market status and trading hours validation
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pytz
from kiteconnect import KiteConnect

from core.kite_manager import KiteManager


class MarketDataManager:
    """
    Manages real-time market data for trading strategies
    """
    
    def __init__(self, kite_manager: KiteManager):
        self.kite_manager = kite_manager
        self.kite = kite_manager.kite
        
        # Nifty 50 instrument token (for underlying data)
        self.nifty_token = 256265  # NSE:NIFTY 50
        
        # Data storage
        self.ohlcv_data = pd.DataFrame()
        self.option_chain = {}
        self.current_prices = {}
        
        # IST timezone
        self.ist = pytz.timezone('Asia/Kolkata')
        
    def is_market_open(self) -> bool:
        """
        Check if market is currently open with robust validation
        - Primary: API-based market status (if available)
        - Fallback: Local time validation with error handling
        - Handles holidays, special sessions, timezone issues
        """
        # Try API-based validation first (most reliable)
        api_status = self._get_api_market_status()
        if api_status is not None:
            return api_status
        
        # Fallback to local time validation
        return self._local_market_hours_check()
    
    def _get_api_market_status(self) -> bool | None:
        """Get market status from API if available"""
        try:
            if self.kite and hasattr(self.kite, 'quote'):
                # Try to get a quote - market closed returns specific error
                response = self.kite.quote(["NSE:NIFTY 50"])
                if response and "NSE:NIFTY 50" in response:
                    # If we get valid quote data, market is likely open
                    quote_data = response["NSE:NIFTY 50"]
                    # Check if last price timestamp is recent (within 5 minutes)
                    if "last_trade_time" in quote_data:
                        import dateutil.parser
                        last_trade = dateutil.parser.parse(quote_data["last_trade_time"])
                        now = datetime.now(self.ist)
                        time_diff = (now - last_trade.astimezone(self.ist)).total_seconds()
                        return time_diff <= 300  # 5 minutes tolerance
                    return True
        except Exception as e:
            print(f"API market status check failed: {e}")
            # Don't return False - fallback to local check
        
        return None  # API check inconclusive
    
    def _local_market_hours_check(self) -> bool:
        """Fallback local time-based market hours validation"""
        try:
            now = datetime.now(self.ist)
            
            # Check if it's a weekday (Monday=0, Sunday=6)
            if now.weekday() > 4:  # Saturday=5, Sunday=6
                return False
            
            # Market hours: 9:15 AM to 3:30 PM IST
            market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            
            # Add buffer for system clock variations (±2 minutes)
            buffer_minutes = 2
            market_open_buffer = market_open - timedelta(minutes=buffer_minutes)
            market_close_buffer = market_close + timedelta(minutes=buffer_minutes)
            
            is_open = market_open_buffer <= now <= market_close_buffer
            
            # Log market status for debugging
            if is_open:
                remaining = (market_close - now).total_seconds() / 60
                print(f"Market open - {remaining:.0f} minutes remaining")
            else:
                if now < market_open:
                    wait_minutes = (market_open - now).total_seconds() / 60
                    print(f"Market closed - opens in {wait_minutes:.0f} minutes")
                else:
                    print(f"Market closed for the day")
            
            return is_open
            
        except Exception as e:
            print(f"Error in local market hours check: {e}")
            # Conservative approach - assume market closed on error
            return False
    
    def get_nifty_ohlcv(self, interval: str = "minute", days: int = 1) -> pd.DataFrame:
        """
        Fetch OHLCV data for Nifty 50
        
        Args:
            interval: Data interval ("minute", "5minute", "15minute", "day")
            days: Number of days to fetch (max 60 for minute data)
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        try:
            if not self.kite_manager.is_authenticated:
                raise Exception("Not authenticated with Kite Connect")
            
            # Calculate from_date
            to_date = datetime.now(self.ist)
            from_date = to_date - timedelta(days=days)
            
            # Fetch historical data
            historical_data = self.kite.historical_data(
                instrument_token=self.nifty_token,
                from_date=from_date.date(),
                to_date=to_date.date(),
                interval=interval
            )
            
            if not historical_data:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(historical_data)
            df.rename(columns={'date': 'timestamp'}, inplace=True)
            
            # Ensure proper data types
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Store for strategy use
            self.ohlcv_data = df
            
            return df
            
        except Exception as e:
            print(f"Error fetching Nifty OHLCV data: {e}")
            return pd.DataFrame()
    
    def get_current_price(self, symbol: str = None) -> float:
        """
        Get current market price for Nifty or option
        
        Args:
            symbol: Option symbol (e.g., "NIFTY24JAN18000CE") or None for Nifty spot
            
        Returns:
            Current price or 0.0 if error
        """
        try:
            if not self.kite_manager.is_authenticated:
                return 0.0
            
            if symbol is None:
                # Get Nifty spot price
                quote = self.kite.quote([f"NSE:NIFTY 50"])
                if f"NSE:NIFTY 50" in quote:
                    return float(quote[f"NSE:NIFTY 50"]["last_price"])
            else:
                # Get option price
                instrument_token = self._get_option_token(symbol)
                if instrument_token:
                    quote = self.kite.quote([instrument_token])
                    if instrument_token in quote:
                        return float(quote[instrument_token]["last_price"])
            
            return 0.0
            
        except Exception as e:
            print(f"Error fetching current price for {symbol}: {e}")
            return 0.0
    
    def get_option_chain(self, expiry_date: str, strikes: List[int] = None) -> Dict[str, Dict]:
        """
        Get option chain data for given expiry and strikes
        
        Args:
            expiry_date: Expiry in "YYMMDD" format (e.g., "24JAN25")
            strikes: List of strike prices, or None for ATM ± 500
            
        Returns:
            Dictionary with option data: {symbol: {price, volume, oi, etc}}
        """
        try:
            if not self.kite_manager.is_authenticated:
                return {}
            
            # Get current Nifty price for ATM calculation
            nifty_price = self.get_current_price()
            if not nifty_price:
                return {}
            
            # Default strikes around ATM
            if strikes is None:
                atm_strike = round(nifty_price / 50) * 50
                strikes = list(range(atm_strike - 500, atm_strike + 550, 50))
            
            option_data = {}
            
            # Fetch data for each strike (both CE and PE)
            for strike in strikes:
                # Call option
                ce_symbol = f"NIFTY{expiry_date}{strike}CE"
                ce_token = self._get_option_token(ce_symbol)
                
                if ce_token:
                    try:
                        quote = self.kite.quote([ce_token])
                        if ce_token in quote:
                            option_data[ce_symbol] = quote[ce_token]
                    except:
                        continue
                
                # Put option
                pe_symbol = f"NIFTY{expiry_date}{strike}PE"
                pe_token = self._get_option_token(pe_symbol)
                
                if pe_token:
                    try:
                        quote = self.kite.quote([pe_token])
                        if pe_token in quote:
                            option_data[pe_symbol] = quote[pe_token]
                    except:
                        continue
            
            self.option_chain = option_data
            return option_data
            
        except Exception as e:
            print(f"Error fetching option chain: {e}")
            return {}
    
    def _get_option_token(self, symbol: str) -> Optional[str]:
        """
        Get instrument token for option symbol
        
        This is a simplified version - in production, you'd maintain
        an instrument master or use Kite's instrument lookup
        """
        try:
            # Try to search for the instrument
            # Note: This is a basic implementation
            # In production, you should maintain instrument master data
            
            # For now, return None - this will be enhanced when we integrate
            # with proper instrument master data
            return None
            
        except Exception as e:
            print(f"Error getting option token for {symbol}: {e}")
            return None
    
    def get_real_time_data(self) -> Dict[str, Any]:
        """
        Get comprehensive real-time market data for dashboard
        
        Returns:
            Dictionary with market status, prices, and key metrics
        """
        try:
            data = {
                'timestamp': datetime.now(self.ist).isoformat(),
                'market_open': self.is_market_open(),
                'nifty_price': 0.0,
                'nifty_change': 0.0,
                'nifty_change_percent': 0.0,
                'volatility': 0.0,
                'data_available': False
            }
            
            # Get current Nifty price and basic stats
            current_price = self.get_current_price()
            if current_price > 0:
                data['nifty_price'] = current_price
                data['data_available'] = True
                
                # Calculate change from previous close (if available)
                if not self.ohlcv_data.empty:
                    prev_close = self.ohlcv_data['close'].iloc[-2] if len(self.ohlcv_data) > 1 else current_price
                    change = current_price - prev_close
                    change_pct = (change / prev_close) * 100
                    
                    data['nifty_change'] = round(change, 2)
                    data['nifty_change_percent'] = round(change_pct, 2)
                    
                    # Calculate simple volatility (based on recent price movements)
                    if len(self.ohlcv_data) >= 20:
                        recent_returns = self.ohlcv_data['close'].pct_change().tail(20)
                        volatility = recent_returns.std() * np.sqrt(252) * 100  # Annualized
                        data['volatility'] = round(volatility, 2)
            
            return data
            
        except Exception as e:
            print(f"Error getting real-time data: {e}")
            return {
                'timestamp': datetime.now(self.ist).isoformat(),
                'market_open': False,
                'nifty_price': 0.0,
                'nifty_change': 0.0,
                'nifty_change_percent': 0.0,
                'volatility': 0.0,
                'data_available': False,
                'error': str(e)
            }
    
    def start_live_data_feed(self, callback_func=None):
        """
        Start live data feed using WebSocket (placeholder for future implementation)
        
        For now, this will be implemented using polling
        """
        print("Live data feed not implemented yet - using polling method")
        # TODO: Implement WebSocket-based live data feed
        pass
    
    def stop_live_data_feed(self):
        """Stop live data feed"""
        # TODO: Implement WebSocket cleanup
        pass
    
    def get_market_summary(self) -> Dict[str, Any]:
        """Get comprehensive market summary for display"""
        try:
            real_time = self.get_real_time_data()
            
            summary = {
                'market_status': 'OPEN' if real_time['market_open'] else 'CLOSED',
                'nifty_spot': real_time['nifty_price'],
                'nifty_change': real_time['nifty_change'],
                'nifty_change_percent': real_time['nifty_change_percent'],
                'volatility': real_time['volatility'],
                'timestamp': real_time['timestamp'],
                'data_quality': 'LIVE' if real_time['data_available'] else 'UNAVAILABLE'
            }
            
            # Add OHLC data if available
            if not self.ohlcv_data.empty:
                latest_candle = self.ohlcv_data.iloc[-1]
                summary.update({
                    'open': float(latest_candle['open']),
                    'high': float(latest_candle['high']),
                    'low': float(latest_candle['low']),
                    'volume': int(latest_candle['volume']) if not pd.isna(latest_candle['volume']) else 0
                })
            
            return summary
            
        except Exception as e:
            print(f"Error getting market summary: {e}")
            return {
                'market_status': 'ERROR',
                'error': str(e),
                'timestamp': datetime.now(self.ist).isoformat()
            }