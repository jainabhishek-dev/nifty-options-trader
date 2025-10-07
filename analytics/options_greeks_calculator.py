#!/usr/bin/env python3
"""
Options Greeks Calculator
Calculates Delta, Gamma, Theta, Vega, and Rho for options using Black-Scholes model
"""

import logging
import numpy as np
import pandas as pd
from scipy.stats import norm
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import math

logger = logging.getLogger(__name__)

class OptionsGreeksCalculator:
    """
    Professional-grade Greeks calculator using Black-Scholes and enhanced models
    Supports European options with dividend adjustments
    """
    
    def __init__(self):
        self.risk_free_rate = 0.06  # Default 6% risk-free rate
        self.dividend_yield = 0.01  # Default 1% dividend yield for indices
        
        logger.info("📊 Options Greeks Calculator initialized")
    
    def calculate_all_greeks(self, spot_price: float, strike_price: float, 
                           time_to_expiry: float, volatility: float,
                           option_type: str = 'CE', risk_free_rate: Optional[float] = None,
                           dividend_yield: Optional[float] = None) -> Dict[str, float]:
        """
        Calculate all Greeks for an option
        
        Args:
            spot_price: Current price of underlying
            strike_price: Strike price of option
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility (annual)
            option_type: 'CE' for Call, 'PE' for Put
            risk_free_rate: Risk-free rate (override default)
            dividend_yield: Dividend yield (override default)
            
        Returns:
            Dictionary containing all Greeks
        """
        try:
            # Use provided rates or defaults
            rf_rate = risk_free_rate if risk_free_rate is not None else self.risk_free_rate
            div_yield = dividend_yield if dividend_yield is not None else self.dividend_yield
            
            # Validate inputs
            if not self._validate_inputs(spot_price, strike_price, time_to_expiry, volatility):
                return self._empty_greeks()
            
            # Calculate d1 and d2 for Black-Scholes
            d1, d2 = self._calculate_d1_d2(spot_price, strike_price, time_to_expiry, 
                                         volatility, rf_rate, div_yield)
            
            # Calculate all Greeks
            greeks = {}
            
            if option_type.upper() in ['CE', 'CALL']:
                greeks = self._calculate_call_greeks(spot_price, strike_price, time_to_expiry,
                                                   volatility, rf_rate, div_yield, d1, d2)
            else:
                greeks = self._calculate_put_greeks(spot_price, strike_price, time_to_expiry,
                                                  volatility, rf_rate, div_yield, d1, d2)
            
            # Add additional metrics
            greeks.update(self._calculate_additional_metrics(spot_price, strike_price, 
                                                           time_to_expiry, volatility, 
                                                           option_type, rf_rate, div_yield))
            
            logger.debug(f"✅ Greeks calculated for {option_type} {strike_price} strike")
            return greeks
            
        except Exception as e:
            logger.error(f"❌ Error calculating Greeks: {e}")
            return self._empty_greeks()
    
    def calculate_portfolio_greeks(self, positions: List[Dict]) -> Dict[str, float]:
        """
        Calculate net Greeks for a portfolio of options
        
        Args:
            positions: List of position dictionaries with option details and quantities
            
        Returns:
            Portfolio Greeks summary
        """
        try:
            portfolio_greeks = {
                'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0, 'rho': 0.0,
                'total_positions': len(positions), 'net_premium': 0.0
            }
            
            for position in positions:
                try:
                    # Extract position details
                    quantity = position.get('quantity', 0)
                    option_data = position.get('option_data', {})
                    
                    if quantity == 0:
                        continue
                    
                    # Calculate Greeks for this position
                    pos_greeks = self.calculate_all_greeks(
                        spot_price=option_data.get('spot_price', 0),
                        strike_price=option_data.get('strike_price', 0),
                        time_to_expiry=option_data.get('time_to_expiry', 0),
                        volatility=option_data.get('volatility', 0.2),
                        option_type=option_data.get('option_type', 'CE')
                    )
                    
                    # Add weighted Greeks to portfolio
                    for greek in ['delta', 'gamma', 'theta', 'vega', 'rho']:
                        portfolio_greeks[greek] += pos_greeks.get(greek, 0) * quantity
                    
                    # Add premium
                    premium = option_data.get('premium', 0) * quantity
                    portfolio_greeks['net_premium'] += premium
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error processing position: {e}")
                    continue
            
            logger.info(f"📊 Portfolio Greeks calculated for {len(positions)} positions")
            return portfolio_greeks
            
        except Exception as e:
            logger.error(f"❌ Error calculating portfolio Greeks: {e}")
            return {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0, 'rho': 0.0}
    
    def calculate_greeks_surface(self, spot_price: float, strikes: List[float], 
                               expiries: List[float], volatility: float = 0.2) -> pd.DataFrame:
        """
        Calculate Greeks surface across multiple strikes and expiries
        
        Args:
            spot_price: Current spot price
            strikes: List of strike prices
            expiries: List of times to expiry (in years)
            volatility: Implied volatility
            
        Returns:
            DataFrame with Greeks surface data
        """
        try:
            surface_data = []
            
            for expiry in expiries:
                for strike in strikes:
                    # Calculate Greeks for both calls and puts
                    call_greeks = self.calculate_all_greeks(spot_price, strike, expiry, 
                                                          volatility, 'CE')
                    put_greeks = self.calculate_all_greeks(spot_price, strike, expiry, 
                                                         volatility, 'PE')
                    
                    surface_data.append({
                        'strike': strike,
                        'expiry': expiry,
                        'moneyness': strike / spot_price,
                        'call_delta': call_greeks['delta'],
                        'call_gamma': call_greeks['gamma'],
                        'call_theta': call_greeks['theta'],
                        'call_vega': call_greeks['vega'],
                        'put_delta': put_greeks['delta'],
                        'put_gamma': put_greeks['gamma'],
                        'put_theta': put_greeks['theta'],
                        'put_vega': put_greeks['vega']
                    })
            
            df = pd.DataFrame(surface_data)
            logger.info(f"📈 Greeks surface calculated: {len(strikes)} strikes × {len(expiries)} expiries")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error calculating Greeks surface: {e}")
            return pd.DataFrame()
    
    def _calculate_d1_d2(self, S: float, K: float, T: float, sigma: float, 
                        r: float, q: float) -> Tuple[float, float]:
        """Calculate d1 and d2 parameters for Black-Scholes"""
        try:
            d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
            d2 = d1 - sigma * np.sqrt(T)
            return d1, d2
        except Exception as e:
            logger.error(f"❌ Error calculating d1, d2: {e}")
            return 0.0, 0.0
    
    def _calculate_call_greeks(self, S: float, K: float, T: float, sigma: float, 
                             r: float, q: float, d1: float, d2: float) -> Dict[str, float]:
        """Calculate Greeks for call options"""
        try:
            # Standard normal CDF and PDF
            N_d1 = norm.cdf(d1)
            N_d2 = norm.cdf(d2)
            n_d1 = norm.pdf(d1)
            
            # Calculate Greeks
            delta = np.exp(-q * T) * N_d1
            gamma = np.exp(-q * T) * n_d1 / (S * sigma * np.sqrt(T))
            theta = ((-S * n_d1 * sigma * np.exp(-q * T)) / (2 * np.sqrt(T)) 
                    - r * K * np.exp(-r * T) * N_d2 + q * S * np.exp(-q * T) * N_d1) / 365
            vega = S * np.exp(-q * T) * n_d1 * np.sqrt(T) / 100
            rho = K * T * np.exp(-r * T) * N_d2 / 100
            
            return {
                'delta': round(delta, 4),
                'gamma': round(gamma, 6),
                'theta': round(theta, 4),
                'vega': round(vega, 4),
                'rho': round(rho, 4)
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating call Greeks: {e}")
            return self._empty_greeks()
    
    def _calculate_put_greeks(self, S: float, K: float, T: float, sigma: float, 
                            r: float, q: float, d1: float, d2: float) -> Dict[str, float]:
        """Calculate Greeks for put options"""
        try:
            # Standard normal CDF and PDF
            N_minus_d1 = norm.cdf(-d1)
            N_minus_d2 = norm.cdf(-d2)
            n_d1 = norm.pdf(d1)
            
            # Calculate Greeks
            delta = -np.exp(-q * T) * N_minus_d1
            gamma = np.exp(-q * T) * n_d1 / (S * sigma * np.sqrt(T))
            theta = ((-S * n_d1 * sigma * np.exp(-q * T)) / (2 * np.sqrt(T)) 
                    + r * K * np.exp(-r * T) * N_minus_d2 - q * S * np.exp(-q * T) * N_minus_d1) / 365
            vega = S * np.exp(-q * T) * n_d1 * np.sqrt(T) / 100
            rho = -K * T * np.exp(-r * T) * N_minus_d2 / 100
            
            return {
                'delta': round(delta, 4),
                'gamma': round(gamma, 6),
                'theta': round(theta, 4),
                'vega': round(vega, 4),
                'rho': round(rho, 4)
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating put Greeks: {e}")
            return self._empty_greeks()
    
    def _calculate_additional_metrics(self, S: float, K: float, T: float, sigma: float, 
                                    option_type: str, r: float, q: float) -> Dict[str, float]:
        """Calculate additional option metrics"""
        try:
            additional = {}
            
            # Intrinsic value
            if option_type.upper() in ['CE', 'CALL']:
                additional['intrinsic_value'] = max(S - K, 0)
            else:
                additional['intrinsic_value'] = max(K - S, 0)
            
            # Moneyness
            additional['moneyness'] = S / K
            
            # Time value (would need actual option price for accurate calculation)
            # For now, we'll use theoretical price
            theoretical_price = self._calculate_theoretical_price(S, K, T, sigma, option_type, r, q)
            additional['time_value'] = max(theoretical_price - additional['intrinsic_value'], 0)
            additional['theoretical_price'] = theoretical_price
            
            return additional
            
        except Exception as e:
            logger.error(f"❌ Error calculating additional metrics: {e}")
            return {}
    
    def _calculate_theoretical_price(self, S: float, K: float, T: float, sigma: float, 
                                   option_type: str, r: float, q: float) -> float:
        """Calculate theoretical option price using Black-Scholes"""
        try:
            d1, d2 = self._calculate_d1_d2(S, K, T, sigma, r, q)
            
            if option_type.upper() in ['CE', 'CALL']:
                price = (S * np.exp(-q * T) * norm.cdf(d1) - 
                        K * np.exp(-r * T) * norm.cdf(d2))
            else:
                price = (K * np.exp(-r * T) * norm.cdf(-d2) - 
                        S * np.exp(-q * T) * norm.cdf(-d1))
            
            return max(price, 0.01)  # Minimum price of 0.01
            
        except Exception as e:
            logger.error(f"❌ Error calculating theoretical price: {e}")
            return 0.01
    
    def _validate_inputs(self, spot_price: float, strike_price: float, 
                        time_to_expiry: float, volatility: float) -> bool:
        """Validate input parameters"""
        try:
            if spot_price <= 0:
                logger.error("❌ Spot price must be positive")
                return False
            
            if strike_price <= 0:
                logger.error("❌ Strike price must be positive")
                return False
            
            if time_to_expiry <= 0:
                logger.error("❌ Time to expiry must be positive")
                return False
            
            if volatility <= 0 or volatility > 5:  # 500% max volatility
                logger.error("❌ Volatility must be between 0 and 5")
                return False
            
            return True
            
        except Exception:
            return False
    
    def _empty_greeks(self) -> Dict[str, float]:
        """Return empty Greeks structure"""
        return {
            'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0, 'rho': 0.0,
            'intrinsic_value': 0.0, 'time_value': 0.0, 'moneyness': 1.0, 
            'theoretical_price': 0.0
        }
    
    def set_risk_free_rate(self, rate: float):
        """Update the default risk-free rate"""
        if 0 <= rate <= 1:  # Rate between 0% and 100%
            self.risk_free_rate = rate
            logger.info(f"📊 Risk-free rate updated to {rate:.2%}")
        else:
            logger.warning(f"⚠️ Invalid risk-free rate: {rate}")
    
    def set_dividend_yield(self, yield_rate: float):
        """Update the default dividend yield"""
        if 0 <= yield_rate <= 1:  # Yield between 0% and 100%
            self.dividend_yield = yield_rate
            logger.info(f"💰 Dividend yield updated to {yield_rate:.2%}")
        else:
            logger.warning(f"⚠️ Invalid dividend yield: {yield_rate}")
    
    def get_greek_interpretation(self, greek_name: str, value: float) -> str:
        """Get human-readable interpretation of Greek values"""
        interpretations = {
            'delta': {
                'description': 'Price sensitivity to underlying movement',
                'ranges': [
                    ((-1, -0.5), 'Deep ITM Put'),
                    ((-0.5, -0.3), 'ITM Put'),
                    ((-0.3, 0.3), 'ATM'),
                    ((0.3, 0.5), 'ITM Call'),
                    ((0.5, 1), 'Deep ITM Call')
                ]
            },
            'gamma': {
                'description': 'Rate of change of Delta',
                'ranges': [
                    ((0, 0.001), 'Low Gamma'),
                    ((0.001, 0.005), 'Moderate Gamma'),
                    ((0.005, float('inf')), 'High Gamma')
                ]
            },
            'theta': {
                'description': 'Time decay (daily)',
                'ranges': [
                    ((-float('inf'), -10), 'High Time Decay'),
                    ((-10, -2), 'Moderate Time Decay'),
                    ((-2, 0), 'Low Time Decay')
                ]
            },
            'vega': {
                'description': 'Volatility sensitivity',
                'ranges': [
                    ((0, 5), 'Low Vol Sensitivity'),
                    ((5, 15), 'Moderate Vol Sensitivity'),
                    ((15, float('inf')), 'High Vol Sensitivity')
                ]
            }
        }
        
        if greek_name.lower() not in interpretations:
            return f"{greek_name}: {value}"
        
        greek_info = interpretations[greek_name.lower()]
        
        # Find appropriate range
        for (min_val, max_val), description in greek_info['ranges']:
            if min_val <= value < max_val:
                return f"{description} ({value})"
        
        return f"{greek_name}: {value}"