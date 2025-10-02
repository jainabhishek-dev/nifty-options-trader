# utils/market_utils.py
"""
Market Data Management for Nifty Options Trading
Handles real-time market data, option chains, and market analysis
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union, Any
import pandas as pd
from kiteconnect import KiteConnect
from config.settings import TradingConfig, OptionsConfig

logger = logging.getLogger(__name__)

class MarketDataManager:
    """Manages real-time market data and option chains"""
    
    def __init__(self, kite_client: KiteConnect):
        """Initialize market data manager"""
        self.kite = kite_client
        self.nifty_ltp = 0.0
        self.nifty_change = 0.0
        self.option_chain = {}
        self.instruments_data = {}
        self.last_refresh = datetime.now()
        
        # Performance tracking
        self.refresh_count = 0
        self.last_refresh_duration = 0.0
        
        logger.info("📊 Market Data Manager initialized")
        
        # Load instruments data
        self._load_instruments()
        
        # Initial data fetch
        self.refresh_data()
    
    def _load_instruments(self) -> None:
        """Load and process instruments data"""
        try:
            logger.info("📋 Loading instruments data...")
            
            # Get NFO instruments (for options)
            nfo_instruments = self.kite.instruments("NFO")
            
            if isinstance(nfo_instruments, list):
                # Filter Nifty options
                self.nifty_options = [
                    instr for instr in nfo_instruments
                    if isinstance(instr, dict) and
                    'NIFTY' in str(instr.get('name', '')) and
                    instr.get('instrument_type') in ['CE', 'PE'] and
                    instr.get('segment') == 'NFO'
                ]
                
                # Create lookup dictionaries
                self.instruments_data = {
                    instr['instrument_token']: instr
                    for instr in self.nifty_options
                    if isinstance(instr, dict)
                }
                
                logger.info(f"✅ Loaded {len(self.nifty_options)} Nifty options contracts")
                
                # Log sample data
                if self.nifty_options:
                    sample = self.nifty_options[0]
                    logger.info(f"📋 Sample contract: {sample.get('tradingsymbol')} | Strike: {sample.get('strike')} | Expiry: {sample.get('expiry')}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load instruments: {e}")
            self.nifty_options = []
            self.instruments_data = {}
    
    def refresh_data(self) -> None:
        """Refresh market data"""
        try:
            start_time = time.time()
            
            # Get Nifty 50 quote
            self._update_nifty_data()
            
            # Update option chain for current strikes
            self._update_option_chain()
            
            # Track performance
            self.last_refresh_duration = time.time() - start_time
            self.last_refresh = datetime.now()
            self.refresh_count += 1
            
            if self.refresh_count % 10 == 0:  # Log every 10th refresh
                logger.debug(f"📊 Market data refresh #{self.refresh_count} - {self.last_refresh_duration:.2f}s")
            
        except Exception as e:
            logger.error(f"❌ Market data refresh failed: {e}")
    
    def _update_nifty_data(self) -> None:
        """Update Nifty 50 current price and change"""
        try:
            quote_response = self.kite.quote(["NSE:NIFTY 50"])
            
            if isinstance(quote_response, dict):
                nifty_data = quote_response.get("NSE:NIFTY 50", {})
                
                if isinstance(nifty_data, dict):
                    self.nifty_ltp = float(nifty_data.get("last_price", 0))
                    
                    # Calculate change
                    open_price = float(nifty_data.get("ohlc", {}).get("open", 0))
                    if open_price > 0:
                        self.nifty_change = ((self.nifty_ltp - open_price) / open_price) * 100
                    
                    logger.debug(f"📈 Nifty 50: ₹{self.nifty_ltp:,.2f} ({self.nifty_change:+.2f}%)")
        
        except Exception as e:
            logger.error(f"❌ Failed to update Nifty data: {e}")
    
    def _update_option_chain(self) -> None:
        """Update option chain data for relevant strikes"""
        try:
            if self.nifty_ltp == 0:
                return
            
            # Get ATM and nearby strikes
            relevant_strikes = self._get_relevant_strikes()
            
            # Get quotes for relevant options
            option_symbols = []
            for strike in relevant_strikes:
                # Find CE and PE contracts for this strike
                ce_contract = self._find_option_contract(strike, 'CE')
                pe_contract = self._find_option_contract(strike, 'PE')
                
                if ce_contract:
                    symbol = f"NFO:{ce_contract['tradingsymbol']}"
                    option_symbols.append(symbol)
                
                if pe_contract:
                    symbol = f"NFO:{pe_contract['tradingsymbol']}"
                    option_symbols.append(symbol)
            
            if option_symbols:
                # Get quotes in batches (Kite has limits)
                batch_size = 50
                for i in range(0, len(option_symbols), batch_size):
                    batch = option_symbols[i:i+batch_size]
                    
                    quote_response = self.kite.quote(batch)
                    
                    if isinstance(quote_response, dict):
                        self.option_chain.update(quote_response)
            
        except Exception as e:
            logger.error(f"❌ Failed to update option chain: {e}")
    
    def _get_relevant_strikes(self) -> List[float]:
        """Get relevant option strikes around ATM"""
        if self.nifty_ltp == 0:
            return []
        
        # Round to nearest 50
        atm_strike = round(self.nifty_ltp / 50) * 50
        
        # Get strikes in range
        strikes = []
        for i in range(-10, 11):  # 10 strikes on each side
            strike = atm_strike + (i * 50)
            if strike > 0:
                strikes.append(strike)
        
        return strikes
    
    def _find_option_contract(self, strike: float, option_type: str) -> Optional[Dict[str, Any]]:
        """Find option contract for given strike and type"""
        try:
            # Get current week's expiry (simplified)
            target_expiry = self._get_current_expiry()
            
            for contract in self.nifty_options:
                if (isinstance(contract, dict) and 
                    contract.get('strike') == strike and
                    contract.get('instrument_type') == option_type and
                    str(contract.get('expiry', '')) == target_expiry):
                    return contract
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to find option contract: {e}")
            return None
    
    def _get_current_expiry(self) -> str:
        """Get current week's option expiry (simplified)"""
        try:
            # For now, find the nearest expiry
            if not self.nifty_options:
                return ""
            
            # Get all unique expiries
            expiries = set()
            for contract in self.nifty_options:
                if isinstance(contract, dict):
                    expiry = contract.get('expiry')
                    if expiry:
                        expiries.add(str(expiry))
            
            # Sort and get nearest
            sorted_expiries = sorted(list(expiries))
            
            # Return nearest future expiry
            today = datetime.now().strftime('%Y-%m-%d')
            for expiry in sorted_expiries:
                if expiry >= today:
                    return expiry
            
            return sorted_expiries[0] if sorted_expiries else ""
            
        except Exception as e:
            logger.error(f"❌ Failed to get current expiry: {e}")
            return ""
    
    def get_nifty_ltp(self) -> float:
        """Get current Nifty 50 LTP"""
        return self.nifty_ltp
    
    def get_nifty_change(self) -> float:
        """Get Nifty 50 percentage change"""
        return self.nifty_change
    
    def get_atm_strike(self) -> float:
        """Get ATM strike price"""
        if self.nifty_ltp > 0:
            return round(self.nifty_ltp / 50) * 50
        return 0.0
    
    def get_option_data(self, strike: float, option_type: str) -> Optional[Dict[str, Any]]:
        """Get option data for specific strike and type"""
        try:
            contract = self._find_option_contract(strike, option_type)
            if not contract:
                return None
            
            symbol = f"NFO:{contract['tradingsymbol']}"
            return self.option_chain.get(symbol)
            
        except Exception as e:
            logger.error(f"❌ Failed to get option data: {e}")
            return None
    
    def get_option_premium(self, strike: float, option_type: str) -> float:
        """Get option premium for specific strike and type"""
        try:
            option_data = self.get_option_data(strike, option_type)
            if option_data and isinstance(option_data, dict):
                return float(option_data.get('last_price', 0))
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Failed to get option premium: {e}")
            return 0.0
    
    def find_tradeable_strikes(self, action: str, strike_type: str) -> List[Tuple[float, str, float]]:
        """Find tradeable option strikes based on criteria"""
        try:
            strikes = []
            atm_strike = self.get_atm_strike()
            
            if atm_strike == 0:
                return strikes
            
            # Define strike range based on type
            if strike_type == "ITM":
                if action == "CALL":
                    # ITM calls are below current price
                    strike_range = range(int(atm_strike - 200), int(atm_strike), 50)
                else:  # PUT
                    # ITM puts are above current price
                    strike_range = range(int(atm_strike + 50), int(atm_strike + 250), 50)
            
            elif strike_type == "OTM":
                if action == "CALL":
                    # OTM calls are above current price
                    strike_range = range(int(atm_strike + 50), int(atm_strike + 250), 50)
                else:  # PUT
                    # OTM puts are below current price
                    strike_range = range(int(atm_strike - 200), int(atm_strike), 50)
            
            else:  # ATM
                strike_range = [int(atm_strike)]
            
            # Check each strike for tradability
            option_type = 'CE' if action == 'CALL' else 'PE'
            
            for strike in strike_range:
                premium = self.get_option_premium(float(strike), option_type)
                
                # Apply filters
                if (TradingConfig.MIN_PREMIUM <= premium <= TradingConfig.MAX_PREMIUM):
                    strikes.append((float(strike), option_type, premium))
            
            # Sort by premium (higher first for buying)
            strikes.sort(key=lambda x: x[2], reverse=True)
            
            return strikes[:5]  # Return top 5 strikes
            
        except Exception as e:
            logger.error(f"❌ Failed to find tradeable strikes: {e}")
            return []
    
    def get_market_summary(self) -> Dict[str, Any]:
        """Get comprehensive market summary"""
        return {
            'nifty_ltp': self.nifty_ltp,
            'nifty_change': self.nifty_change,
            'atm_strike': self.get_atm_strike(),
            'last_refresh': self.last_refresh,
            'refresh_count': self.refresh_count,
            'option_contracts': len(self.nifty_options),
            'option_chain_size': len(self.option_chain)
        }

class OptionsAnalyzer:
    """Advanced options analysis utilities"""
    
    def __init__(self, market_data: MarketDataManager):
        self.market_data = market_data
    
    def calculate_iv_percentile(self, strike: float, option_type: str) -> float:
        """Calculate IV percentile (simplified)"""
        # This would require historical IV data
        # For now, return a mock value
        return 50.0
    
    def calculate_greeks(self, strike: float, option_type: str) -> Dict[str, float]:
        """Calculate option Greeks (simplified Black-Scholes)"""
        # This would require proper implementation
        # For now, return mock values
        return {
            'delta': 0.5,
            'gamma': 0.01,
            'theta': -0.05,
            'vega': 0.1,
            'rho': 0.01
        }
    
    def assess_liquidity(self, strike: float, option_type: str) -> Dict[str, Any]:
        """Assess option liquidity"""
        try:
            option_data = self.market_data.get_option_data(strike, option_type)
            
            if not option_data:
                return {'liquid': False, 'reason': 'No data available'}
            
            # Check basic liquidity metrics
            volume = option_data.get('volume', 0)
            oi = option_data.get('oi', 0)
            
            is_liquid = (
                volume >= OptionsConfig.MIN_VOLUME and
                oi >= OptionsConfig.MIN_OPEN_INTEREST
            )
            
            return {
                'liquid': is_liquid,
                'volume': volume,
                'open_interest': oi,
                'reason': 'Sufficient liquidity' if is_liquid else 'Insufficient liquidity'
            }
            
        except Exception as e:
            return {'liquid': False, 'reason': f'Analysis failed: {e}'}

# Export classes
__all__ = ['MarketDataManager', 'OptionsAnalyzer']
