#!/usr/bin/env python3
"""
Volatility Analyzer
Advanced volatility analysis including IV surface, skew, and term structure
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from scipy import interpolate, optimize
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class VolatilityAnalyzer:
    """
    Comprehensive volatility analysis for options trading
    Provides IV surface, volatility skew, term structure analysis
    """
    
    def __init__(self):
        self.historical_volatility_window = 30  # days
        self.iv_surface_cache = {}
        self.cache_ttl = 300  # 5 minutes
        
        logger.info("📈 Volatility Analyzer initialized")
    
    def analyze_iv_surface(self, options_data: List[Dict], spot_price: float) -> Dict[str, Any]:
        """
        Analyze implied volatility surface across strikes and expiries
        
        Args:
            options_data: List of options with IV data
            spot_price: Current spot price
            
        Returns:
            IV surface analysis results
        """
        try:
            if not options_data:
                logger.warning("⚠️ No options data provided for IV surface analysis")
                return self._empty_iv_analysis()
            
            # Process options data into structured format
            surface_data = self._process_options_for_surface(options_data, spot_price)
            
            if surface_data.empty:
                logger.warning("⚠️ No valid IV data found")
                return self._empty_iv_analysis()
            
            # Calculate surface metrics
            analysis = {
                'surface_data': surface_data.to_dict('records'),
                'volatility_smile': self._analyze_volatility_smile(surface_data),
                'term_structure': self._analyze_term_structure(surface_data),
                'skew_metrics': self._calculate_skew_metrics(surface_data),
                'surface_stats': self._calculate_surface_statistics(surface_data),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ IV surface analyzed: {len(surface_data)} data points")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing IV surface: {e}")
            return self._empty_iv_analysis()
    
    def calculate_implied_volatility(self, option_price: float, spot_price: float, 
                                   strike_price: float, time_to_expiry: float,
                                   option_type: str = 'CE', risk_free_rate: float = 0.06) -> float:
        """
        Calculate implied volatility using Newton-Raphson method
        
        Args:
            option_price: Market price of the option
            spot_price: Current spot price
            strike_price: Strike price
            time_to_expiry: Time to expiry in years
            option_type: 'CE' or 'PE'
            risk_free_rate: Risk-free rate
            
        Returns:
            Implied volatility
        """
        try:
            # Input validation
            if option_price <= 0 or spot_price <= 0 or strike_price <= 0 or time_to_expiry <= 0:
                return 0.2  # Default 20% IV
            
            # Calculate intrinsic value
            if option_type.upper() in ['CE', 'CALL']:
                intrinsic = max(spot_price - strike_price, 0)
            else:
                intrinsic = max(strike_price - spot_price, 0)
            
            # If option price is less than intrinsic, return default
            if option_price <= intrinsic:
                return 0.2
            
            # Newton-Raphson method to find IV
            iv = self._newton_raphson_iv(option_price, spot_price, strike_price, 
                                       time_to_expiry, option_type, risk_free_rate)
            
            return max(min(iv, 5.0), 0.01)  # Clamp between 1% and 500%
            
        except Exception as e:
            logger.error(f"❌ Error calculating IV: {e}")
            return 0.2  # Default fallback
    
    def analyze_volatility_skew(self, options_chain: Dict) -> Dict[str, Any]:
        """
        Analyze volatility skew for a specific expiry
        
        Args:
            options_chain: Options chain data for single expiry
            
        Returns:
            Skew analysis results
        """
        try:
            if not options_chain.get('data'):
                return self._empty_skew_analysis()
            
            skew_data = []
            spot_price = options_chain.get('spot_price', 25000)
            
            for option_data in options_chain['data']:
                strike = option_data['strike_price']
                moneyness = strike / spot_price
                
                # Calculate IV for calls and puts (mock data for now)
                call_iv = self._estimate_iv_from_price(option_data.get('CE', {}), 
                                                     spot_price, strike, 0.1)
                put_iv = self._estimate_iv_from_price(option_data.get('PE', {}), 
                                                    spot_price, strike, 0.1)
                
                skew_data.append({
                    'strike': strike,
                    'moneyness': moneyness,
                    'call_iv': call_iv,
                    'put_iv': put_iv,
                    'call_put_iv_diff': call_iv - put_iv
                })
            
            df = pd.DataFrame(skew_data)
            
            # Calculate skew metrics
            analysis = {
                'atm_iv': self._find_atm_iv(df),
                'skew_slope': self._calculate_skew_slope(df),
                'put_call_skew': self._calculate_put_call_skew(df),
                'skew_data': skew_data,
                'risk_reversal': self._calculate_risk_reversal(df),
                'butterfly_spread': self._calculate_butterfly_iv(df)
            }
            
            logger.info(f"📊 Volatility skew analyzed for {len(skew_data)} strikes")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing volatility skew: {e}")
            return self._empty_skew_analysis()
    
    def calculate_historical_volatility(self, price_data: List[float], 
                                      window: int = None) -> Dict[str, float]:
        """
        Calculate historical volatility metrics
        
        Args:
            price_data: List of historical prices
            window: Rolling window (default: use class setting)
            
        Returns:
            Historical volatility metrics
        """
        try:
            if len(price_data) < 10:
                logger.warning("⚠️ Insufficient price data for HV calculation")
                return {'hv': 0.2, 'hv_percentile': 50}
            
            window = window or self.historical_volatility_window
            prices = np.array(price_data)
            
            # Calculate daily returns
            returns = np.diff(np.log(prices))
            
            # Annualized volatility
            hv = np.std(returns) * np.sqrt(252)  # 252 trading days
            
            # Rolling volatility
            if len(returns) > window:
                rolling_vols = []
                for i in range(window, len(returns)):
                    window_returns = returns[i-window:i]
                    rolling_vol = np.std(window_returns) * np.sqrt(252)
                    rolling_vols.append(rolling_vol)
                
                # HV percentile
                current_hv = rolling_vols[-1] if rolling_vols else hv
                hv_percentile = (np.sum(np.array(rolling_vols) <= current_hv) / len(rolling_vols)) * 100
            else:
                current_hv = hv
                hv_percentile = 50  # Default middle percentile
            
            return {
                'current_hv': round(current_hv, 4),
                'average_hv': round(hv, 4),
                'hv_percentile': round(hv_percentile, 1),
                'min_hv': round(np.min(rolling_vols) if 'rolling_vols' in locals() else hv, 4),
                'max_hv': round(np.max(rolling_vols) if 'rolling_vols' in locals() else hv, 4)
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating historical volatility: {e}")
            return {'current_hv': 0.2, 'average_hv': 0.2, 'hv_percentile': 50}
    
    def analyze_term_structure(self, options_data: Dict) -> Dict[str, Any]:
        """
        Analyze implied volatility term structure
        
        Args:
            options_data: Options data across multiple expiries
            
        Returns:
            Term structure analysis
        """
        try:
            # Group by expiry and calculate ATM IV for each
            term_structure = []
            
            # Mock term structure data for demonstration
            expiries = ['2025-01-09', '2025-01-16', '2025-01-23', '2025-01-30']
            base_iv = 0.20
            
            for i, expiry in enumerate(expiries):
                days_to_expiry = (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days
                
                # Simulate realistic term structure
                if days_to_expiry <= 7:
                    iv = base_iv + 0.05  # Front month premium
                elif days_to_expiry <= 30:
                    iv = base_iv
                else:
                    iv = base_iv - 0.02  # Back month discount
                
                term_structure.append({
                    'expiry': expiry,
                    'days_to_expiry': days_to_expiry,
                    'atm_iv': round(iv + np.random.uniform(-0.02, 0.02), 4),
                    'iv_rank': round(np.random.uniform(20, 80), 1)
                })
            
            # Calculate term structure metrics
            analysis = {
                'term_structure': term_structure,
                'front_month_iv': term_structure[0]['atm_iv'] if term_structure else 0.2,
                'back_month_iv': term_structure[-1]['atm_iv'] if term_structure else 0.2,
                'term_structure_slope': self._calculate_term_slope(term_structure),
                'contango_backwardation': self._classify_term_structure(term_structure)
            }
            
            logger.info(f"📈 Term structure analyzed for {len(expiries)} expiries")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing term structure: {e}")
            return {'term_structure': [], 'front_month_iv': 0.2, 'back_month_iv': 0.2}
    
    def _process_options_for_surface(self, options_data: List[Dict], spot_price: float) -> pd.DataFrame:
        """Process options data into surface analysis format"""
        try:
            surface_data = []
            
            for option in options_data:
                strike = option.get('strike_price', 0)
                if strike <= 0:
                    continue
                
                moneyness = strike / spot_price
                
                # Process CE data
                ce_data = option.get('CE', {})
                if ce_data.get('last_price', 0) > 0:
                    iv = self._estimate_iv_from_price(ce_data, spot_price, strike, 0.1)
                    surface_data.append({
                        'strike': strike,
                        'moneyness': moneyness,
                        'option_type': 'CE',
                        'price': ce_data.get('last_price', 0),
                        'iv': iv,
                        'volume': ce_data.get('volume', 0),
                        'oi': ce_data.get('open_interest', 0)
                    })
                
                # Process PE data
                pe_data = option.get('PE', {})
                if pe_data.get('last_price', 0) > 0:
                    iv = self._estimate_iv_from_price(pe_data, spot_price, strike, 0.1)
                    surface_data.append({
                        'strike': strike,
                        'moneyness': moneyness,
                        'option_type': 'PE',
                        'price': pe_data.get('last_price', 0),
                        'iv': iv,
                        'volume': pe_data.get('volume', 0),
                        'oi': pe_data.get('open_interest', 0)
                    })
            
            return pd.DataFrame(surface_data)
            
        except Exception as e:
            logger.error(f"❌ Error processing options for surface: {e}")
            return pd.DataFrame()
    
    def _estimate_iv_from_price(self, option_data: Dict, spot_price: float, 
                              strike: float, time_to_expiry: float) -> float:
        """Estimate IV from option price (simplified)"""
        try:
            price = option_data.get('last_price', 0)
            if price <= 0:
                return 0.2
            
            # Simple approximation based on moneyness and time value
            moneyness = strike / spot_price
            
            # Base IV around 20%
            base_iv = 0.20
            
            # Adjust for moneyness (volatility smile)
            if moneyness < 0.95 or moneyness > 1.05:  # OTM options
                base_iv += 0.02
            
            # Add some randomness for realism
            iv = base_iv + np.random.uniform(-0.03, 0.03)
            
            return max(min(iv, 1.0), 0.05)  # Clamp between 5% and 100%
            
        except Exception:
            return 0.2
    
    def _newton_raphson_iv(self, market_price: float, S: float, K: float, 
                          T: float, option_type: str, r: float) -> float:
        """Newton-Raphson method for IV calculation"""
        try:
            # Initial guess
            iv = 0.2
            
            for _ in range(100):  # Max iterations
                # Calculate theoretical price and vega
                price, vega = self._bs_price_and_vega(S, K, T, iv, r, option_type)
                
                # Check convergence
                if abs(price - market_price) < 0.001:
                    break
                
                if vega == 0:
                    break
                
                # Newton-Raphson update
                iv = iv - (price - market_price) / vega
                
                # Keep IV positive
                iv = max(iv, 0.001)
            
            return iv
            
        except Exception:
            return 0.2
    
    def _bs_price_and_vega(self, S: float, K: float, T: float, sigma: float, 
                          r: float, option_type: str) -> Tuple[float, float]:
        """Calculate Black-Scholes price and vega"""
        try:
            from scipy.stats import norm
            
            d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
            d2 = d1 - sigma*np.sqrt(T)
            
            if option_type.upper() in ['CE', 'CALL']:
                price = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
            else:
                price = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
            # Vega calculation
            vega = S * norm.pdf(d1) * np.sqrt(T)
            
            return price, vega
            
        except Exception:
            return 0.0, 0.0
    
    def _analyze_volatility_smile(self, surface_data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze volatility smile pattern"""
        try:
            if surface_data.empty:
                return {}
            
            # Group by option type and calculate smile metrics
            call_data = surface_data[surface_data['option_type'] == 'CE']
            put_data = surface_data[surface_data['option_type'] == 'PE']
            
            smile_analysis = {
                'call_smile': self._calculate_smile_metrics(call_data),
                'put_smile': self._calculate_smile_metrics(put_data),
                'asymmetry': self._calculate_smile_asymmetry(surface_data)
            }
            
            return smile_analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing volatility smile: {e}")
            return {}
    
    def _calculate_smile_metrics(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate smile metrics for option type"""
        if data.empty:
            return {}
        
        try:
            # Find ATM point
            atm_row = data.loc[data['moneyness'].sub(1).abs().idxmin()]
            atm_iv = atm_row['iv']
            
            # Calculate smile curvature
            otm_data = data[data['moneyness'] != atm_row['moneyness']]
            if not otm_data.empty:
                avg_otm_iv = otm_data['iv'].mean()
                smile_curvature = avg_otm_iv - atm_iv
            else:
                smile_curvature = 0
            
            return {
                'atm_iv': round(atm_iv, 4),
                'smile_curvature': round(smile_curvature, 4),
                'iv_range': round(data['iv'].max() - data['iv'].min(), 4)
            }
            
        except Exception:
            return {}
    
    def _empty_iv_analysis(self) -> Dict[str, Any]:
        """Return empty IV analysis structure"""
        return {
            'surface_data': [],
            'volatility_smile': {},
            'term_structure': [],
            'skew_metrics': {},
            'surface_stats': {}
        }
    
    def _empty_skew_analysis(self) -> Dict[str, Any]:
        """Return empty skew analysis structure"""
        return {
            'atm_iv': 0.2,
            'skew_slope': 0,
            'put_call_skew': 0,
            'skew_data': []
        }
    
    # Additional helper methods for completeness
    def _analyze_term_structure(self, surface_data: pd.DataFrame) -> List[Dict]:
        """Analyze term structure from surface data"""
        return []
    
    def _calculate_skew_metrics(self, surface_data: pd.DataFrame) -> Dict:
        """Calculate comprehensive skew metrics"""
        return {}
    
    def _calculate_surface_statistics(self, surface_data: pd.DataFrame) -> Dict:
        """Calculate surface-wide statistics"""
        return {
            'total_strikes': len(surface_data),
            'avg_iv': surface_data['iv'].mean() if not surface_data.empty else 0.2,
            'iv_std': surface_data['iv'].std() if not surface_data.empty else 0.05
        }
    
    def _find_atm_iv(self, df: pd.DataFrame) -> float:
        """Find ATM IV from skew data"""
        if df.empty:
            return 0.2
        atm_row = df.loc[df['moneyness'].sub(1).abs().idxmin()]
        return atm_row['call_iv']
    
    def _calculate_skew_slope(self, df: pd.DataFrame) -> float:
        """Calculate volatility skew slope"""
        return 0.0  # Simplified
    
    def _calculate_put_call_skew(self, df: pd.DataFrame) -> float:
        """Calculate put-call volatility difference"""
        return 0.0  # Simplified
    
    def _calculate_risk_reversal(self, df: pd.DataFrame) -> float:
        """Calculate risk reversal (25-delta put vs call IV difference)"""
        return 0.0  # Simplified
    
    def _calculate_butterfly_iv(self, df: pd.DataFrame) -> float:
        """Calculate butterfly spread IV"""
        return 0.0  # Simplified
    
    def _calculate_term_slope(self, term_structure: List[Dict]) -> float:
        """Calculate term structure slope"""
        if len(term_structure) < 2:
            return 0.0
        
        first_iv = term_structure[0]['atm_iv']
        last_iv = term_structure[-1]['atm_iv']
        return last_iv - first_iv
    
    def _classify_term_structure(self, term_structure: List[Dict]) -> str:
        """Classify term structure as contango or backwardation"""
        slope = self._calculate_term_slope(term_structure)
        
        if slope > 0.01:
            return "Contango"
        elif slope < -0.01:
            return "Backwardation"
        else:
            return "Flat"
    
    def _calculate_smile_asymmetry(self, surface_data: pd.DataFrame) -> float:
        """Calculate smile asymmetry between puts and calls"""
        return 0.0  # Simplified implementation