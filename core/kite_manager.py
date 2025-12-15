#!/usr/bin/env python3
"""
Core Kite Connect Manager
Handles all interactions with Kite Connect API including authentication, 
market data, and order management.
"""

import logging
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, cast
from kiteconnect import KiteConnect
from config.settings import TradingConfig

logger = logging.getLogger(__name__)

class KiteManager:
    """
    Core Kite Connect wrapper for the trading platform
    Handles authentication, market data, orders, and portfolio management
    """
    
    def __init__(self):
        """Initialize Kite Connect manager"""
        # Load API credentials from environment
        self.api_key = os.environ.get('KITE_API_KEY')
        self.api_secret = os.environ.get('KITE_API_SECRET')
        self.redirect_url = os.environ.get('KITE_REDIRECT_URL', 'http://127.0.0.1:5000/auth')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("KITE_API_KEY and KITE_API_SECRET must be set in environment")
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.access_token = None
        
        # Rate limiting to prevent "Too many requests"
        self.last_api_call = 0
        self.api_call_delay = 0.2  # 200ms between calls
        self.is_authenticated = False
        
        # Load existing access token if available
        self._load_access_token()
        
        # Market instruments cache
        self.instruments = {}
        self.nifty_instruments = {}
        
        logger.info("🔌 KiteManager initialized")
    
    def set_access_token(self, access_token: str):
        """Set the access token for Kite Connect"""
        self.access_token = access_token
        self.kite.set_access_token(access_token)
        self.is_authenticated = True
        
        # Save token to file
        try:
            with open('access_token.txt', 'w') as f:
                f.write(access_token)
            logger.info("Access token saved successfully")
        except Exception as e:
            logger.error(f"Failed to save access token: {e}")
    
    def _rate_limit(self):
        """Enforce rate limiting between API calls to prevent 'Too many requests'"""
        current_time = time.time()
        time_since_last = current_time - self.last_api_call
        if time_since_last < self.api_call_delay:
            sleep_time = self.api_call_delay - time_since_last
            time.sleep(sleep_time)
        self.last_api_call = time.time()
        
    def _load_access_token(self):
        """Load access token from file if exists"""
        try:
            with open('access_token.txt', 'r') as f:
                self.access_token = f.read().strip()
                if self.access_token:
                    self.kite.set_access_token(self.access_token)
                    # Verify token by getting profile
                    profile = self.kite.profile()
                    if isinstance(profile, dict) and 'user_name' in profile:
                        self.is_authenticated = True
                        logger.info(f"Authenticated as: {profile['user_name']}")
                    else:
                        self.is_authenticated = False
                        logger.warning("Access token exists but authentication failed")
        except FileNotFoundError:
            logger.info("No access token file found")
        except Exception as e:
            logger.error(f"Error loading access token: {e}")
            self.is_authenticated = False
    
    def authenticate(self, request_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Authenticate with Kite Connect
        
        Args:
            request_token: Request token from Kite login (optional if already authenticated)
            
        Returns:
            Authentication status and user info
        """
        if self.is_authenticated:
            try:
                profile = self.kite.profile()
                return {
                    'success': True,
                    'message': 'Already authenticated',
                    'user': profile
                }
            except:
                self.is_authenticated = False
        
        if not request_token:
            # Generate login URL
            login_url = self.kite.login_url()
            return {
                'success': False,
                'message': 'Login required',
                'login_url': login_url
            }
        
        try:
            # Generate access token
            data = self.kite.generate_session(request_token, api_secret=self.api_secret)
            if isinstance(data, dict) and 'access_token' in data:
                self.access_token = data['access_token']
            else:
                raise Exception('Invalid session data received')
            
            # Save access token
            with open('access_token.txt', 'w') as f:
                f.write(self.access_token)
            
            self.is_authenticated = True
            
            # Get user profile
            profile = self.kite.profile()
            
            if isinstance(profile, dict) and 'user_name' in profile:
                logger.info(f"Successfully authenticated: {profile['user_name']}")
            else:
                logger.info("Successfully authenticated")
            
            return {
                'success': True,
                'message': 'Authentication successful',
                'user': profile
            }
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return {
                'success': False,
                'message': f'Authentication failed: {str(e)}'
            }
    
    def get_profile(self) -> Optional[Dict]:
        """Get user profile information"""
        if not self.is_authenticated:
            return None
        
        try:
            profile = self.kite.profile()
            return profile if isinstance(profile, dict) else None
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
            return None
    
    def get_portfolio(self) -> List[Dict]:
        """Get current portfolio holdings"""
        if not self.is_authenticated:
            return []
        
        try:
            holdings = self.kite.holdings()
            return holdings if isinstance(holdings, list) else []
        except Exception as e:
            logger.error(f"Error getting portfolio: {e}")
            return []
    
    def get_positions(self) -> Dict[str, List]:
        """Get current positions"""
        if not self.is_authenticated:
            return {'net': [], 'day': []}
        
        try:
            positions = self.kite.positions()
            return positions if isinstance(positions, dict) else {'net': [], 'day': []}
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return {'net': [], 'day': []}
    
    def get_funds(self) -> Dict[str, float]:
        """Get account funds and margins"""
        if not self.is_authenticated:
            return {}
        
        try:
            margins = self.kite.margins()
            if not isinstance(margins, dict):
                return {}
            equity_margins = margins.get('equity', {})
            available = equity_margins.get('available', {})
            utilised = equity_margins.get('utilised', {})
            
            # Use live_balance as the primary available cash (more accurate than 'cash' field)
            available_cash = available.get('live_balance', 0)
            
            # If live_balance is 0, fallback to other possible cash fields
            if available_cash == 0:
                available_cash = available.get('cash', 0)
                if available_cash == 0:
                    available_cash = available.get('intraday_payin', 0)
            
            return {
                'available_cash': available_cash,
                'used_margin': utilised.get('debits', 0),
                'available_margin': available.get('adhoc_margin', 0),
                'total_margin': equity_margins.get('net', 0)
            }
        except Exception as e:
            logger.error(f"Error getting funds: {e}")
            return {}
    
    def load_instruments(self) -> bool:
        """Load and cache market instruments"""
        if not self.is_authenticated:
            logger.error("❌ Cannot load instruments - not authenticated")
            return False
        
        try:
            # Rate limit the API call
            self._rate_limit()
            
            # Get all instruments - handle both callable and pre-cached scenarios
            instruments_data = self.kite.instruments()
            
            # Handle case where instruments() returns a dict instead of list
            if isinstance(instruments_data, dict):
                logger.warning("⚠️ Instruments API returned dict instead of list - extracting values")
                instruments_data = list(instruments_data.values()) if instruments_data else []
            
            if not isinstance(instruments_data, list):
                raise Exception(f"Unexpected instruments data type: {type(instruments_data)}")
            
            if not instruments_data:
                raise Exception("No instruments data received from Kite Connect")
            
            # Cache instruments by trading symbol
            self.instruments = {inst['tradingsymbol']: inst for inst in instruments_data if isinstance(inst, dict)}
            
            # Cache Nifty options specifically  
            self.nifty_instruments = {
                inst['tradingsymbol']: inst 
                for inst in instruments_data 
                if isinstance(inst, dict) and 
                   inst.get('name') == 'NIFTY' and 
                   inst.get('segment') == 'NFO-OPT'
            }
            
            logger.info(f"Loaded {len(self.instruments)} instruments, {len(self.nifty_instruments)} Nifty options")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load instruments: {e}")
            return False

    def get_instruments(self) -> Dict[str, Any]:
        """Get cached instruments data"""
        if not self.instruments:
            self.load_instruments()
        return self.instruments
    
    def get_nifty_ltp(self) -> float:
        """Get Nifty 50 last traded price"""
        if not self.is_authenticated:
            return 0.0
        
        try:
            # Nifty 50 instrument token
            nifty_token = '256265'  # NSE:NIFTY 50 token
            ltp_data = self.kite.ltp([nifty_token])
            if isinstance(ltp_data, dict) and nifty_token in ltp_data:
                token_data = ltp_data[nifty_token]
                if isinstance(token_data, dict) and 'last_price' in token_data:
                    return float(token_data['last_price'])
            return 0.0
        except Exception as e:
            logger.error(f"Error getting Nifty LTP: {e}")
            return 0.0

    def get_current_price(self, symbol: str) -> float:
        """Get current market price for any symbol (options, stocks, etc.)"""
        if not self.is_authenticated:
            return 0.0
        
        try:
            # Use the symbol directly with Kite API
            ltp_data = self.kite.ltp([symbol])
            if isinstance(ltp_data, dict) and symbol in ltp_data:
                token_data = ltp_data[symbol]
                if isinstance(token_data, dict) and 'last_price' in token_data:
                    return float(token_data['last_price'])
            return 0.0
        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")
            return 0.0
    
    def get_option_chain(self, expiry: Optional[str] = None, strikes: Optional[List[int]] = None) -> List[Dict]:
        """
        Get REAL Nifty options chain data from Kite Connect
        
        Args:
            expiry: Expiry date in YYYY-MM-DD format (optional)
            strikes: List of strike prices (optional)
            
        Returns:
            List of option contracts with LIVE market data
        """
        if not self.is_authenticated:
            logger.error("❌ Not authenticated to Kite Connect")
            return []
            
        if not self.instruments:
            logger.warning("⚠️ Instruments not loaded, loading now...")
            self.load_instruments()
            
        if not self.instruments:
            logger.error("❌ Failed to load instruments from Kite Connect")
            return []
        
        try:
            # If no expiry specified, find the nearest expiry from real instruments
            if not expiry:
                expiry = self._get_nearest_real_expiry()
                if not expiry:
                    logger.error("❌ No expiry dates found in Kite Connect instruments")
                    return []
            
            # Get ATM strikes if not specified
            if not strikes:
                nifty_ltp = self.get_nifty_ltp()
                if not nifty_ltp:
                    logger.error("❌ Cannot get Nifty LTP for ATM calculation")
                    return []
                    
                atm_strike = round(nifty_ltp / 50) * 50
                # Generate 41 strikes around ATM (20 below + ATM + 20 above)
                strikes = [atm_strike + i * 50 for i in range(-20, 21)]
            
            option_chain = []
            
            # Convert expiry to the format used in Kite instruments
            expiry_date = datetime.strptime(expiry, '%Y-%m-%d')
            
            for strike in strikes:
                try:
                    # Find CE and PE instruments for this strike and expiry
                    ce_instrument = None
                    pe_instrument = None
                    
                    # Search through instruments for matching options
                    for symbol_key, instrument in self.instruments.items():
                        if (instrument.get('name') == 'NIFTY' and 
                            instrument.get('segment') == 'NFO-OPT' and
                            instrument.get('strike') == strike and
                            instrument.get('expiry') and
                            instrument['expiry'] == expiry_date.date()):
                            
                            if instrument.get('instrument_type') == 'CE':
                                ce_instrument = instrument
                            elif instrument.get('instrument_type') == 'PE':
                                pe_instrument = instrument
                    
                    if ce_instrument and pe_instrument:
                        # Get complete market data for both options using quote()
                        ce_token = str(ce_instrument['instrument_token'])
                        pe_token = str(pe_instrument['instrument_token'])
                        
                        try:
                            # Rate limit API call to prevent "Too many requests"
                            self._rate_limit()
                            
                            # Fetch complete quote data (includes OI, Volume, Bid, Ask, LTP)
                            quote_data = self.kite.quote([ce_token, pe_token])
                            
                            # Helper function to safely extract bid/ask from depth
                            def extract_bid_ask(quote_dict):
                                bid_price = 0
                                ask_price = 0
                                
                                try:
                                    depth = quote_dict.get('depth', {})
                                    if isinstance(depth, dict):
                                        # Extract bid price
                                        buy_orders = depth.get('buy', [])
                                        if isinstance(buy_orders, list) and len(buy_orders) > 0:
                                            first_buy = buy_orders[0]
                                            if isinstance(first_buy, dict):
                                                bid_price = first_buy.get('price', 0)
                                        
                                        # Extract ask price
                                        sell_orders = depth.get('sell', [])
                                        if isinstance(sell_orders, list) and len(sell_orders) > 0:
                                            first_sell = sell_orders[0]
                                            if isinstance(first_sell, dict):
                                                ask_price = first_sell.get('price', 0)
                                except Exception:
                                    pass  # Return 0 values if extraction fails
                                
                                return bid_price, ask_price
                            
                            # Helper function to safely extract data from quote
                            def extract_quote_data(quote_dict):
                                if not isinstance(quote_dict, dict):
                                    return {
                                        'last_price': 0,
                                        'open_interest': 0,
                                        'volume': 0,
                                        'bid': 0,
                                        'ask': 0,
                                        'change': 0,
                                        'change_percent': 0
                                    }
                                
                                bid_price, ask_price = extract_bid_ask(quote_dict)
                                
                                return {
                                    'last_price': quote_dict.get('last_price', 0),
                                    'open_interest': quote_dict.get('oi', 0),
                                    'volume': quote_dict.get('volume', 0),
                                    'bid': bid_price,
                                    'ask': ask_price,
                                    'change': quote_dict.get('net_change', 0),
                                    'change_percent': quote_dict.get('net_change_percent', 0)
                                }
                            
                            # Extract complete market data for CE
                            ce_quote_raw = quote_data.get(ce_token, {}) if isinstance(quote_data, dict) else {}
                            ce_data = extract_quote_data(ce_quote_raw)
                            
                            # Extract complete market data for PE
                            pe_quote_raw = quote_data.get(pe_token, {}) if isinstance(quote_data, dict) else {}
                            pe_data = extract_quote_data(pe_quote_raw)
                            
                        except Exception as quote_error:
                            logger.warning(f"⚠️ Quote API error for strike {strike}: {quote_error}, falling back to LTP")
                            # Rate limit fallback call
                            self._rate_limit()
                            
                            # Fallback to LTP if quote fails
                            ltp_data = self.kite.ltp([ce_token, pe_token])
                            
                            ce_ltp_data = ltp_data.get(ce_token, {}) if isinstance(ltp_data, dict) else {}
                            pe_ltp_data = ltp_data.get(pe_token, {}) if isinstance(ltp_data, dict) else {}
                            
                            ce_data = {
                                'last_price': ce_ltp_data.get('last_price', 0),
                                'open_interest': 0, 'volume': 0, 'bid': 0, 'ask': 0, 'change': 0, 'change_percent': 0
                            }
                            pe_data = {
                                'last_price': pe_ltp_data.get('last_price', 0),
                                'open_interest': 0, 'volume': 0, 'bid': 0, 'ask': 0, 'change': 0, 'change_percent': 0
                            }
                        
                        option_chain.append({
                            'strike': strike,
                            'ce_symbol': ce_instrument.get('tradingsymbol', f'NIFTY{strike}CE'),
                            'ce_data': ce_data,
                            'ce_token': ce_instrument['instrument_token'],
                            'pe_symbol': pe_instrument.get('tradingsymbol', f'NIFTY{strike}PE'),
                            'pe_data': pe_data,
                            'pe_token': pe_instrument['instrument_token']
                        })
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error processing strike {strike}: {e}")
                    continue
            
            logger.info(f"✅ Fetched {len(option_chain)} real options from Kite Connect for expiry {expiry}")
            return sorted(option_chain, key=lambda x: x['strike'])
            
        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            return []
    
    def _get_nearest_real_expiry(self) -> Optional[str]:
        """Get nearest expiry date from real Kite Connect instruments"""
        try:
            expiry_dates = set()
            current_date = datetime.now().date()
            
            # Extract expiry dates from NIFTY option instruments
            for symbol_key, instrument in self.instruments.items():
                if (instrument.get('name') == 'NIFTY' and 
                    instrument.get('segment') == 'NFO-OPT' and
                    instrument.get('instrument_type') in ['CE', 'PE'] and
                    instrument.get('expiry')):
                    
                    expiry = instrument['expiry']
                    # Handle different types - could be datetime.date or datetime.datetime
                    if hasattr(expiry, 'date'):
                        expiry_date = expiry.date()
                    else:
                        expiry_date = expiry
                    
                    if expiry_date >= current_date:  # Only future expiries
                        expiry_dates.add(expiry_date.strftime('%Y-%m-%d'))
            
            if not expiry_dates:
                logger.warning("⚠️ No future expiry dates found in instruments")
                return None
                
            # Return the nearest future expiry
            return sorted(list(expiry_dates))[0]
            
        except Exception as e:
            logger.error(f"❌ Error getting nearest real expiry: {e}")
            return None
    
    def _get_nearest_expiry(self) -> str:
        """Get nearest Thursday expiry date (fallback)"""
        today = datetime.now()
        
        # Find next Thursday
        days_ahead = 3 - today.weekday()  # Thursday is 3
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        next_thursday = today + timedelta(days_ahead)
        return next_thursday.strftime('%Y-%m-%d')
    
    def place_order(self, 
                   tradingsymbol: str,
                   transaction_type: str,
                   quantity: int,
                   order_type: str = 'MARKET',
                   price: Optional[float] = None,
                   product: str = 'MIS',
                   validity: str = 'DAY') -> Dict[str, Any]:
        """
        Place an order
        
        Args:
            tradingsymbol: Trading symbol (e.g., 'NIFTY24O0324900CE')
            transaction_type: 'BUY' or 'SELL'
            quantity: Order quantity
            order_type: 'MARKET', 'LIMIT', 'SL', 'SL-M'
            price: Order price (for LIMIT orders)
            product: 'MIS', 'CNC', 'NRML'
            validity: 'DAY', 'IOC'
            
        Returns:
            Order placement result
        """
        if not self.is_authenticated:
            return {'success': False, 'message': 'Not authenticated'}
        
        try:
            order_params = {
                'tradingsymbol': tradingsymbol,
                'exchange': 'NFO',
                'transaction_type': transaction_type,
                'quantity': quantity,
                'order_type': order_type,
                'product': product,
                'validity': validity
            }
            
            if price and order_type in ['LIMIT', 'SL']:
                order_params['price'] = price
            
            order_id = self.kite.place_order(**order_params)
            
            logger.info(f"Order placed: {order_id} - {transaction_type} {quantity} {tradingsymbol}")
            
            return {
                'success': True,
                'order_id': order_id,
                'message': 'Order placed successfully'
            }
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {
                'success': False,
                'message': f'Order placement failed: {str(e)}'
            }
    
    def get_orders(self) -> List[Dict]:
        """Get order history"""
        if not self.is_authenticated:
            return []
        
        try:
            orders = self.kite.orders()
            return orders if isinstance(orders, list) else []
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an order"""
        if not self.is_authenticated:
            return {'success': False, 'message': 'Not authenticated'}
        
        try:
            self.kite.cancel_order(variety='regular', order_id=order_id)
            return {'success': True, 'message': 'Order cancelled'}
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_historical_data(self, 
                          instrument_token: str,
                          from_date: datetime,
                          to_date: datetime,
                          interval: str = 'minute') -> List[Dict]:
        """
        Get historical market data
        
        Args:
            instrument_token: Instrument token
            from_date: Start date
            to_date: End date  
            interval: Data interval ('minute', '5minute', 'day', etc.)
            
        Returns:
            Historical OHLCV data
        """
        if not self.is_authenticated:
            return []
        
        try:
            data = self.kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )
            return data
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return []
    
    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        now = datetime.now()
        
        # Check if it's a weekday (Monday = 0, Sunday = 6)
        if now.weekday() > 4:  # Saturday or Sunday
            return False
        
        # Market hours: 9:15 AM to 3:30 PM
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    def quote(self, instruments: List[str]) -> Dict[str, Any]:
        """Get quote data for instruments with rate limiting"""
        try:
            self._rate_limit()
            result = self.kite.quote(instruments)
            # Type cast since Kite API returns complex nested types that don't match our typing
            return cast(Dict[str, Any], result) if result else {}
        except Exception as e:
            logger.error(f"❌ Quote API error: {e}")
            return {}
    
    def ltp(self, instruments: List[str]) -> Dict[str, Any]:
        """Get Last Traded Price for instruments with rate limiting"""
        try:
            self._rate_limit()
            result = self.kite.ltp(instruments)
            # Type cast since Kite API returns complex nested types that don't match our typing
            return cast(Dict[str, Any], result) if result else {}
        except Exception as e:
            logger.error(f"❌ LTP API error: {e}")
            return {}

    def get_connection_status(self) -> Dict[str, Any]:
        """Get connection status and diagnostics"""
        status: Dict[str, Any] = {
            'authenticated': self.is_authenticated,
            'api_key_configured': bool(self.api_key),
            'access_token_available': bool(self.access_token),
            'instruments_loaded': bool(self.instruments),
            'market_open': self.is_market_open()
        }
        
        if self.is_authenticated:
            try:
                profile = self.get_profile()
                if profile and isinstance(profile, dict):
                    status['user'] = profile.get('user_name', 'Unknown')
                    status['broker'] = profile.get('broker', 'Unknown')
                else:
                    status['user'] = 'Error'
                    status['broker'] = 'Error'
            except:
                status['user'] = 'Error getting profile'
                status['broker'] = 'Error'
        
        return status