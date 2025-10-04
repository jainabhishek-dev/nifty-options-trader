#!/usr/bin/env python3
"""
Core Kite Connect Manager
Handles all interactions with Kite Connect API including authentication, 
market data, and order management.
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
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
        # Use environment variables for cloud deployment, fallback to config
        self.api_key = os.environ.get('KITE_API_KEY', TradingConfig.KITE_API_KEY)
        self.api_secret = os.environ.get('KITE_API_SECRET', TradingConfig.KITE_API_SECRET)
        
        self.kite = KiteConnect(api_key=self.api_key)
        self.access_token = None
        self.is_authenticated = False
        
        # Load existing access token if available
        self._load_access_token()
        
        # Market instruments cache
        self.instruments = {}
        self.nifty_instruments = {}
        
    def _load_access_token(self):
        """Load access token from file if exists"""
        try:
            with open('access_token.txt', 'r') as f:
                self.access_token = f.read().strip()
                if self.access_token:
                    self.kite.set_access_token(self.access_token)
                    # Verify token by getting profile
                    profile = self.kite.profile()
                    if profile and 'user_name' in profile:
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
    
    def authenticate(self, request_token: str = None) -> Dict[str, Any]:
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
            self.access_token = data['access_token']
            
            # Save access token
            with open('access_token.txt', 'w') as f:
                f.write(self.access_token)
            
            self.is_authenticated = True
            
            # Get user profile
            profile = self.kite.profile()
            
            logger.info(f"Successfully authenticated: {profile['user_name']}")
            
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
            return self.kite.profile()
        except Exception as e:
            logger.error(f"Error getting profile: {e}")
            return None
    
    def get_portfolio(self) -> List[Dict]:
        """Get current portfolio holdings"""
        if not self.is_authenticated:
            return []
        
        try:
            holdings = self.kite.holdings()
            return holdings
        except Exception as e:
            logger.error(f"Error getting portfolio: {e}")
            return []
    
    def get_positions(self) -> Dict[str, List]:
        """Get current positions"""
        if not self.is_authenticated:
            return {'net': [], 'day': []}
        
        try:
            positions = self.kite.positions()
            return positions
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return {'net': [], 'day': []}
    
    def get_funds(self) -> Dict[str, float]:
        """Get account funds and margins"""
        if not self.is_authenticated:
            return {}
        
        try:
            margins = self.kite.margins()
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
            return False
        
        try:
            # Get all instruments
            instruments = self.kite.instruments()
            
            # Cache instruments by trading symbol
            self.instruments = {inst['tradingsymbol']: inst for inst in instruments}
            
            # Cache Nifty options specifically
            self.nifty_instruments = {
                inst['tradingsymbol']: inst 
                for inst in instruments 
                if inst['name'] == 'NIFTY' and inst['segment'] == 'NFO-OPT'
            }
            
            logger.info(f"Loaded {len(self.instruments)} instruments, {len(self.nifty_instruments)} Nifty options")
            return True
            
        except Exception as e:
            logger.error(f"Error loading instruments: {e}")
            return False
    
    def get_nifty_ltp(self) -> float:
        """Get Nifty 50 last traded price"""
        if not self.is_authenticated:
            return 0.0
        
        try:
            # Nifty 50 instrument token
            nifty_token = '256265'  # NSE:NIFTY 50 token
            ltp_data = self.kite.ltp([nifty_token])
            return ltp_data[nifty_token]['last_price']
        except Exception as e:
            logger.error(f"Error getting Nifty LTP: {e}")
            return 0.0
    
    def get_option_chain(self, expiry: str = None, strikes: List[int] = None) -> List[Dict]:
        """
        Get Nifty options chain data
        
        Args:
            expiry: Expiry date in YYYY-MM-DD format (optional)
            strikes: List of strike prices (optional)
            
        Returns:
            List of option contracts with LTP data
        """
        if not self.is_authenticated or not self.nifty_instruments:
            return []
        
        try:
            # If no expiry specified, use nearest Thursday
            if not expiry:
                expiry = self._get_nearest_expiry()
            
            # Get ATM strike if no strikes specified
            if not strikes:
                nifty_ltp = self.get_nifty_ltp()
                atm_strike = round(nifty_ltp / 50) * 50
                strikes = [atm_strike + i * 50 for i in range(-5, 6)]  # ATM ±5 strikes
            
            option_chain = []
            
            for strike in strikes:
                # CE (Call) option
                ce_symbol = f"NIFTY{expiry.replace('-', '')}{strike}CE"
                pe_symbol = f"NIFTY{expiry.replace('-', '')}{strike}PE"
                
                ce_data = self.nifty_instruments.get(ce_symbol)
                pe_data = self.nifty_instruments.get(pe_symbol)
                
                if ce_data and pe_data:
                    # Get LTP for both options
                    tokens = [ce_data['instrument_token'], pe_data['instrument_token']]
                    ltp_data = self.kite.ltp(tokens)
                    
                    option_chain.append({
                        'strike': strike,
                        'ce_symbol': ce_symbol,
                        'ce_ltp': ltp_data.get(str(ce_data['instrument_token']), {}).get('last_price', 0),
                        'ce_token': ce_data['instrument_token'],
                        'pe_symbol': pe_symbol, 
                        'pe_ltp': ltp_data.get(str(pe_data['instrument_token']), {}).get('last_price', 0),
                        'pe_token': pe_data['instrument_token']
                    })
            
            return sorted(option_chain, key=lambda x: x['strike'])
            
        except Exception as e:
            logger.error(f"Error getting option chain: {e}")
            return []
    
    def _get_nearest_expiry(self) -> str:
        """Get nearest Thursday expiry date"""
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
                   price: float = None,
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
            return self.kite.orders()
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
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get connection status and diagnostics"""
        status = {
            'authenticated': self.is_authenticated,
            'api_key_configured': bool(self.api_key),
            'access_token_available': bool(self.access_token),
            'instruments_loaded': bool(self.instruments),
            'market_open': self.is_market_open()
        }
        
        if self.is_authenticated:
            try:
                profile = self.get_profile()
                status['user'] = profile.get('user_name', 'Unknown') if profile else 'Error'
                status['broker'] = profile.get('broker', 'Unknown') if profile else 'Error'
            except:
                status['user'] = 'Error getting profile'
                status['broker'] = 'Error'
        
        return status