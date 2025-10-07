#!/usr/bin/env python3
"""
Options Data Provider
Handles fetching, processing, and caching of options chain data
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import requests
import json

from core.kite_manager import KiteManager

logger = logging.getLogger(__name__)

class OptionsDataProvider:
    """
    Provides comprehensive options chain data with real-time updates
    Handles data fetching, processing, and caching for optimal performance
    """
    
    def __init__(self, kite_manager: KiteManager):
        self.kite_manager = kite_manager
        self.cache = {}
        self.cache_ttl = 30  # seconds
        self.last_update = {}
        
        # Nifty instrument token (this is the standard Nifty 50 token)
        self.nifty_token = 256265  # NSE:NIFTY 50 token
        
        logger.info("🔗 Options Data Provider initialized")
    
    def get_options_chain(self, symbol: str = "NIFTY", expiry: Optional[str] = None) -> Dict[str, Any]:
        """
        Get complete options chain data for a symbol - LIVE DATA ONLY
        
        Args:
            symbol: Trading symbol (default: NIFTY)
            expiry: Expiry date string (YYYY-MM-DD) or None for current week
            
        Returns:
            Dictionary containing options chain data or error structure
        """
        try:
            # Check cache first
            cache_key = f"{symbol}_{expiry}"
            if self._is_cache_valid(cache_key):
                logger.debug(f"📚 Returning cached options data for {cache_key}")
                return self.cache[cache_key]
            
            # Get LIVE spot price - NO FALLBACKS
            spot_price = self._get_spot_price(symbol)
            if not spot_price:
                error_msg = f"❌ Cannot get LIVE spot price for {symbol}. Check Kite authentication."
                logger.error(error_msg)
                return self._error_options_chain(error_msg)
            
            # Get expiry dates
            expiry_dates = self._get_expiry_dates(symbol)
            if not expiry_dates:
                error_msg = f"❌ No expiry dates available for {symbol}"
                logger.error(error_msg)
                return self._error_options_chain(error_msg)
            
            # Use current expiry if not specified
            if not expiry:
                expiry = expiry_dates[0]  # Current week expiry
            
            # Generate EXACTLY 41 strikes around ATM (20 below + ATM + 20 above)
            strikes = self._generate_strikes(spot_price)
            if len(strikes) != 41:
                error_msg = f"❌ Failed to generate proper strike range (got {len(strikes)}, expected 41)"
                logger.error(error_msg)
                return self._error_options_chain(error_msg)
            
            # Build options chain
            options_data = self._build_options_chain(symbol, expiry, strikes, spot_price)
            
            # Cache the result
            self.cache[cache_key] = options_data
            self.last_update[cache_key] = datetime.now()
            
            logger.info(f"✅ Options chain loaded: {len(strikes)} strikes for {symbol} {expiry}")
            return options_data
            
        except Exception as e:
            error_msg = f"❌ Critical system error getting options chain: {str(e)}"
            logger.error(error_msg)
            return self._error_options_chain(error_msg)
    
    def get_live_options_data(self, instruments: List[str]) -> Dict[str, Any]:
        """
        Get live data for specific option instruments - LIVE DATA ONLY
        
        Args:
            instruments: List of instrument tokens or trading symbols
            
        Returns:
            Dictionary with live options data or empty dict if error
        """
        try:
            if not self.kite_manager.is_authenticated:
                logger.error("❌ Kite not authenticated - cannot fetch live options data")
                return {}
            
            # Get live data from Kite Connect only
            if hasattr(self.kite_manager, 'kite') and self.kite_manager.kite:
                live_data = self.kite_manager.kite.ltp(instruments)
                
                if not live_data or not isinstance(live_data, dict):
                    logger.error("❌ No live options data available from Kite Connect")
                    return {}
                    
                return live_data
            else:
                logger.error("❌ Kite Connect client not available")
                return {}
            
        except Exception as e:
            logger.error(f"❌ Error getting live options data: {e}")
            return {}
    
    def _get_spot_price(self, symbol: str) -> Optional[float]:
        """Get current spot price for the symbol - LIVE DATA ONLY"""
        try:
            if symbol == "NIFTY":
                # ONLY use live data from Kite Manager - NO MOCK DATA
                if not self.kite_manager.is_authenticated:
                    logger.error("❌ Kite Manager not authenticated - cannot get live price")
                    return None
                    
                live_price = self.kite_manager.get_nifty_ltp()
                if live_price and live_price > 0:
                    logger.info(f"📈 Using LIVE Nifty price: {live_price}")
                    return live_price
                else:
                    logger.error("❌ Failed to fetch live Nifty price from Kite")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting live spot price: {e}")
            return None
    
    def _get_expiry_dates(self, symbol: str) -> List[str]:
        """Get available expiry dates from Kite Connect"""
        try:
            if not self.kite_manager.is_authenticated:
                logger.error("❌ Kite Manager not authenticated - cannot get expiry dates")
                return []
            
            # Get expiry dates from Kite Connect instruments
            if not self.kite_manager.instruments:
                self.kite_manager.load_instruments()
            
            expiry_dates = set()
            
            # Extract expiry dates from NIFTY option instruments
            for symbol_key, instrument in self.kite_manager.instruments.items():
                if (instrument.get('name') == 'NIFTY' and 
                    instrument.get('segment') == 'NFO-OPT' and
                    instrument.get('instrument_type') in ['CE', 'PE'] and
                    instrument.get('expiry')):
                    
                    # Handle both date objects and strings
                    expiry = instrument['expiry']
                    if hasattr(expiry, 'strftime'):  # It's a date object
                        expiry_str = expiry.strftime('%Y-%m-%d')
                    else:  # It's a string
                        expiry_str = str(expiry)
                    expiry_dates.add(expiry_str)
            
            # Sort expiry dates and return next 4-5 expiries
            sorted_expiries = sorted(list(expiry_dates))
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # Filter future expiries only
            future_expiries = [exp for exp in sorted_expiries if exp >= current_date]
            
            if not future_expiries:
                logger.warning("❌ No future expiry dates found in Kite Connect instruments")
                return []
            
            logger.info(f"✅ Found {len(future_expiries)} expiry dates from Kite Connect")
            return future_expiries[:5]  # Return next 5 expiries
            
        except Exception as e:
            logger.error(f"❌ Error getting expiry dates from Kite Connect: {e}")
            return []
    
    def _generate_strikes(self, spot_price: float, range_points: int = 1000) -> List[int]:
        """Generate strike prices dynamically around the current spot price"""
        try:
            # Round spot to nearest 50 for ATM
            atm_strike = round(spot_price / 50) * 50
            
            # Generate strikes with adequate range for perfect centering
            strikes = []
            
            # Generate 20 strikes below and 20 above ATM (41 total for perfect centering)
            # This ensures ATM is always at index 20, allowing ±12 strikes for centered display
            for i in range(-20, 21):  # 41 strikes total
                strike = atm_strike + (i * 50)
                if strike > 0:  # Ensure positive strike prices
                    strikes.append(int(strike))
            
            logger.debug(f"📋 Generated {len(strikes)} strikes around spot {spot_price:.2f} → ATM {atm_strike}")
            logger.debug(f"📐 Strike range: {min(strikes)} to {max(strikes)}")
            
            return sorted(strikes)
            
        except Exception as e:
            logger.error(f"❌ Error generating strikes: {e}")
            # NO FALLBACK - Return empty list to force error handling
            return []
    
    def _build_options_chain(self, symbol: str, expiry: str, strikes: List[int], spot_price: float) -> Dict[str, Any]:
        """Build options chain using REAL Kite Connect data"""
        try:
            if not self.kite_manager.is_authenticated:
                error_msg = "❌ Kite Manager not authenticated - cannot fetch real options data"
                logger.error(error_msg)
                return self._error_options_chain(error_msg)
            
            # Use Kite Manager to get REAL options chain data
            real_options_data = self.kite_manager.get_option_chain(expiry, strikes)
            
            if not real_options_data:
                error_msg = f"❌ No real options data available from Kite Connect for expiry {expiry}"
                logger.error(error_msg)
                return self._error_options_chain(error_msg)
            
            # Convert Kite data to our format
            options_chain = {
                'symbol': symbol,
                'expiry': expiry,
                'spot_price': spot_price,
                'timestamp': datetime.now().isoformat(),
                'data': []
            }
            
            # Convert each option from Kite format to our format
            for option in real_options_data:
                # Extract CE data (now includes OI, Volume, Bid, Ask)
                ce_data = option.get('ce_data', {})
                pe_data = option.get('pe_data', {})
                
                strike_data = {
                    'strike_price': option.get('strike', 0),
                    'CE': {
                        'last_price': ce_data.get('last_price', 0),
                        'open_interest': ce_data.get('open_interest', 0),
                        'volume': ce_data.get('volume', 0),
                        'bid': ce_data.get('bid', 0),
                        'ask': ce_data.get('ask', 0),
                        'change': ce_data.get('change', 0),
                        'change_percent': ce_data.get('change_percent', 0)
                    },
                    'PE': {
                        'last_price': pe_data.get('last_price', 0),
                        'open_interest': pe_data.get('open_interest', 0),
                        'volume': pe_data.get('volume', 0),
                        'bid': pe_data.get('bid', 0),
                        'ask': pe_data.get('ask', 0),
                        'change': pe_data.get('change', 0),
                        'change_percent': pe_data.get('change_percent', 0)
                    }
                }
                options_chain['data'].append(strike_data)
            
            logger.info(f"✅ Built options chain with {len(options_chain['data'])} real strikes from Kite Connect")
            return options_chain
            
        except Exception as e:
            error_msg = f"❌ Error building options chain from Kite Connect: {str(e)}"
            logger.error(error_msg)
            return self._error_options_chain(error_msg)
    
    def _generate_strike_data(self, strike: int, spot_price: float, expiry: str) -> Dict[str, Any]:
        """Generate realistic options data for a strike"""
        try:
            # Calculate time to expiry in days
            expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
            today = datetime.now()
            days_to_expiry = (expiry_date - today).days
            time_to_expiry = max(days_to_expiry / 365.0, 0.001)  # Avoid division by zero
            
            # Calculate moneyness
            moneyness = strike / spot_price
            
            # Generate realistic option prices based on moneyness and time
            call_data = self._generate_option_data('CE', strike, spot_price, time_to_expiry, moneyness)
            put_data = self._generate_option_data('PE', strike, spot_price, time_to_expiry, moneyness)
            
            return {
                'strike_price': strike,
                'CE': call_data,
                'PE': put_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating strike data: {e}")
            return {'strike_price': strike, 'CE': {}, 'PE': {}}
    
    def _generate_option_data(self, option_type: str, strike: int, spot_price: float, 
                            time_to_expiry: float, moneyness: float) -> Dict[str, Any]:
        """Generate realistic option data (price, Greeks, etc.)"""
        try:
            # Simple Black-Scholes approximation for realistic prices
            volatility = 0.20  # 20% volatility assumption
            risk_free_rate = 0.06  # 6% risk-free rate
            
            # Calculate intrinsic value
            if option_type == 'CE':  # Call
                intrinsic_value = max(spot_price - strike, 0)
            else:  # Put
                intrinsic_value = max(strike - spot_price, 0)
            
            # Estimate time value based on distance from ATM
            atm_distance = abs(moneyness - 1.0)
            time_value = max(50 * np.exp(-5 * atm_distance) * np.sqrt(time_to_expiry), 0.05)
            
            # Calculate option price
            last_price = intrinsic_value + time_value
            
            # Generate bid/ask spread (typically 1-2% of price)
            spread_percent = min(0.02, max(0.005, 0.1 / max(last_price, 1)))
            bid = max(last_price * (1 - spread_percent), 0.05)
            ask = last_price * (1 + spread_percent)
            
            # Generate volume and OI based on moneyness
            base_volume = int(1000 * np.exp(-2 * atm_distance))
            base_oi = int(5000 * np.exp(-1.5 * atm_distance))
            
            # Add randomness
            volume = max(int(base_volume * np.random.uniform(0.5, 2.0)), 0)
            open_interest = max(int(base_oi * np.random.uniform(0.8, 1.5)), 0)
            
            return {
                'last_price': round(last_price, 2),
                'bid': round(bid, 2),
                'ask': round(ask, 2),
                'volume': volume,
                'open_interest': open_interest,
                'change': round(np.random.uniform(-5, 5), 2),
                'change_percent': round(np.random.uniform(-20, 20), 2)
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating option data: {e}")
            return {
                'last_price': 0.0, 'bid': 0.0, 'ask': 0.0,
                'volume': 0, 'open_interest': 0, 'change': 0.0, 'change_percent': 0.0
            }
    
    # Removed mock data generation - Live data only
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self.cache or cache_key not in self.last_update:
            return False
        
        time_diff = (datetime.now() - self.last_update[cache_key]).seconds
        return time_diff < self.cache_ttl
    
    def _empty_options_chain(self) -> Dict[str, Any]:
        """Return empty options chain structure"""
        return {
            'symbol': 'NIFTY',
            'expiry': datetime.now().strftime('%Y-%m-%d'),
            'spot_price': 0,
            'timestamp': datetime.now().isoformat(),
            'data': [],
            'error': None
        }
    
    def _error_options_chain(self, error_message: str) -> Dict[str, Any]:
        """Return error options chain structure"""
        return {
            'symbol': 'NIFTY',
            'expiry': '',
            'spot_price': 0,
            'timestamp': datetime.now().isoformat(),
            'data': [],
            'error': error_message
        }
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        self.last_update.clear()
        logger.info("🧹 Options data cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            'cached_items': len(self.cache),
            'cache_ttl_seconds': self.cache_ttl
        }