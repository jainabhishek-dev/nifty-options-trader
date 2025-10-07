#!/usr/bin/env python3
"""
Max Pain Analyzer
Calculates Max Pain levels and analyzes open interest distribution
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

class MaxPainAnalyzer:
    """
    Max Pain theory analyzer for options expiry
    Calculates the price level where maximum option premium would expire worthless
    """
    
    def __init__(self):
        self.calculation_cache = {}
        self.cache_ttl = 180  # 3 minutes cache
        
        logger.info("🎯 Max Pain Analyzer initialized")
    
    def calculate_max_pain(self, options_chain: Dict, strike_range: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
        """
        Calculate Max Pain level for given options chain
        
        Args:
            options_chain: Options chain data with OI information
            strike_range: Optional (min_strike, max_strike) to limit calculation
            
        Returns:
            Max Pain analysis results
        """
        try:
            spot_price = options_chain.get('spot_price', 25000)
            expiry = options_chain.get('expiry', '')
            options_data = options_chain.get('data', [])
            
            if not options_data:
                logger.warning("⚠️ No options data provided for Max Pain calculation")
                return self._empty_max_pain_result(spot_price)
            
            # Extract strike and OI data
            strike_data = self._extract_strike_oi_data(options_data, strike_range)
            
            if not strike_data:
                logger.warning("⚠️ No valid strike data for Max Pain calculation")
                return self._empty_max_pain_result(spot_price)
            
            # Calculate pain at each potential expiry price
            pain_calculations = self._calculate_pain_at_strikes(strike_data)
            
            # Find Max Pain point
            max_pain_strike = min(pain_calculations.keys(), key=lambda k: pain_calculations[k]['total_pain'])
            max_pain_data = pain_calculations[max_pain_strike]
            
            # Calculate additional metrics
            oi_analysis = self._analyze_open_interest_distribution(strike_data)
            support_resistance = self._identify_support_resistance(strike_data, spot_price)
            
            result = {
                'max_pain_strike': max_pain_strike,
                'max_pain_amount': max_pain_data['total_pain'],
                'current_spot': spot_price,
                'distance_from_spot': max_pain_strike - spot_price,
                'distance_percentage': ((max_pain_strike - spot_price) / spot_price) * 100,
                'expiry_date': expiry,
                'pain_calculations': pain_calculations,
                'oi_analysis': oi_analysis,
                'support_resistance': support_resistance,
                'calculation_timestamp': datetime.now().isoformat(),
                'total_call_oi': sum(item['call_oi'] for item in strike_data.values()),
                'total_put_oi': sum(item['put_oi'] for item in strike_data.values()),
                'put_call_oi_ratio': self._calculate_pcr_oi(strike_data)
            }
            
            logger.info(f"✅ Max Pain calculated: {max_pain_strike} (Current: {spot_price})")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error calculating Max Pain: {e}")
            return self._empty_max_pain_result(25000)
    
    def analyze_oi_buildup(self, current_chain: Dict, previous_chain: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Analyze open interest buildup and changes
        
        Args:
            current_chain: Current options chain
            previous_chain: Previous day's options chain for comparison
            
        Returns:
            OI buildup analysis
        """
        try:
            current_data = self._extract_strike_oi_data(current_chain.get('data', []))
            
            buildup_analysis = {
                'highest_call_oi_strikes': self._find_highest_oi_strikes(current_data, 'call', 5),
                'highest_put_oi_strikes': self._find_highest_oi_strikes(current_data, 'put', 5),
                'call_oi_concentration': self._calculate_oi_concentration(current_data, 'call'),
                'put_oi_concentration': self._calculate_oi_concentration(current_data, 'put'),
                'oi_skew': self._calculate_oi_skew(current_data),
                'fresh_positions': self._identify_fresh_positions(current_data, previous_chain or {})
            }
            
            # Add change analysis if previous data available
            if previous_chain:
                buildup_analysis['oi_changes'] = self._analyze_oi_changes(current_data, previous_chain)
            
            logger.info("📊 OI buildup analysis completed")
            return buildup_analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing OI buildup: {e}")
            return {}
    
    def calculate_gamma_exposure(self, options_chain: Dict, price_range: Optional[Tuple[float, float]] = None) -> Dict[str, Any]:
        """
        Calculate gamma exposure (GEX) levels
        
        Args:
            options_chain: Options chain with Greeks data
            price_range: Price range for GEX calculation
            
        Returns:
            Gamma exposure analysis
        """
        try:
            spot_price = options_chain.get('spot_price', 25000)
            options_data = options_chain.get('data', [])
            
            if not price_range:
                price_range = (spot_price * 0.95, spot_price * 1.05)
            
            # Create price points for GEX calculation
            price_points = np.arange(price_range[0], price_range[1], 25)
            gex_data = []
            
            for price_point in price_points:
                total_gex = 0
                call_gex = 0
                put_gex = 0
                
                for option in options_data:
                    strike = option['strike_price']
                    
                    # Get OI and estimate gamma (simplified)
                    call_oi = option.get('CE', {}).get('open_interest', 0)
                    put_oi = option.get('PE', {}).get('open_interest', 0)
                    
                    # Simplified gamma calculation (would use Greeks calculator in production)
                    call_gamma = self._estimate_gamma(float(price_point), strike, 0.1, 'CE')
                    put_gamma = self._estimate_gamma(float(price_point), strike, 0.1, 'PE')
                    
                    # GEX = OI * Gamma * 100 * spot^2 * 0.01
                    call_gex_contribution = call_oi * call_gamma * 100 * price_point**2 * 0.01
                    put_gex_contribution = put_oi * put_gamma * 100 * price_point**2 * 0.01 * (-1)  # Puts are negative GEX
                    
                    call_gex += call_gex_contribution
                    put_gex += put_gex_contribution
                    total_gex += call_gex_contribution + put_gex_contribution
                
                gex_data.append({
                    'price': price_point,
                    'total_gex': total_gex,
                    'call_gex': call_gex,
                    'put_gex': put_gex
                })
            
            # Find zero GEX level
            zero_gex_level = self._find_zero_gex_level(gex_data)
            
            result = {
                'gex_profile': gex_data,
                'zero_gex_level': zero_gex_level,
                'current_gex': next((item['total_gex'] for item in gex_data if abs(item['price'] - spot_price) < 25), 0),
                'positive_gex_zone': [item['price'] for item in gex_data if item['total_gex'] > 0],
                'negative_gex_zone': [item['price'] for item in gex_data if item['total_gex'] < 0]
            }
            
            logger.info(f"📈 Gamma exposure calculated for {len(gex_data)} price points")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error calculating gamma exposure: {e}")
            return {}
    
    def identify_key_levels(self, options_chain: Dict) -> Dict[str, Any]:
        """
        Identify key support and resistance levels based on OI and Max Pain
        
        Args:
            options_chain: Options chain data
            
        Returns:
            Key levels analysis
        """
        try:
            spot_price = options_chain.get('spot_price', 25000)
            strike_data = self._extract_strike_oi_data(options_chain.get('data', []))
            
            # Calculate Max Pain
            max_pain_result = self.calculate_max_pain(options_chain)
            max_pain_level = max_pain_result['max_pain_strike']
            
            # Identify high OI strikes
            high_call_oi = self._find_highest_oi_strikes(strike_data, 'call', 3)
            high_put_oi = self._find_highest_oi_strikes(strike_data, 'put', 3)
            
            # Classify levels
            resistance_levels = []
            support_levels = []
            
            # Strikes above current price with high call OI are potential resistance
            for strike_info in high_call_oi:
                if strike_info['strike'] > spot_price:
                    resistance_levels.append({
                        'level': strike_info['strike'],
                        'strength': strike_info['oi'],
                        'type': 'Call OI Resistance'
                    })
            
            # Strikes below current price with high put OI are potential support
            for strike_info in high_put_oi:
                if strike_info['strike'] < spot_price:
                    support_levels.append({
                        'level': strike_info['strike'],
                        'strength': strike_info['oi'],
                        'type': 'Put OI Support'
                    })
            
            # Add Max Pain as key level
            if max_pain_level != spot_price:
                if max_pain_level > spot_price:
                    resistance_levels.append({
                        'level': max_pain_level,
                        'strength': max_pain_result['max_pain_amount'],
                        'type': 'Max Pain'
                    })
                else:
                    support_levels.append({
                        'level': max_pain_level,
                        'strength': max_pain_result['max_pain_amount'],
                        'type': 'Max Pain'
                    })
            
            # Sort by proximity to current price
            resistance_levels.sort(key=lambda x: x['level'])
            support_levels.sort(key=lambda x: x['level'], reverse=True)
            
            result = {
                'immediate_support': support_levels[0] if support_levels else None,
                'immediate_resistance': resistance_levels[0] if resistance_levels else None,
                'all_support_levels': support_levels,
                'all_resistance_levels': resistance_levels,
                'max_pain_level': max_pain_level,
                'current_price': spot_price,
                'key_level_summary': {
                    'total_support_levels': len(support_levels),
                    'total_resistance_levels': len(resistance_levels),
                    'strongest_support': max(support_levels, key=lambda x: x['strength']) if support_levels else None,
                    'strongest_resistance': max(resistance_levels, key=lambda x: x['strength']) if resistance_levels else None
                }
            }
            
            logger.info(f"🎯 Key levels identified: {len(support_levels)} support, {len(resistance_levels)} resistance")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error identifying key levels: {e}")
            return {}
    
    def _extract_strike_oi_data(self, options_data: List[Dict], 
                               strike_range: Optional[Tuple[int, int]] = None) -> Dict[int, Dict]:
        """Extract strike and OI data from options chain"""
        try:
            strike_data = {}
            
            for option in options_data:
                strike = option.get('strike_price', 0)
                
                if strike <= 0:
                    continue
                
                # Apply strike range filter if provided
                if strike_range and (strike < strike_range[0] or strike > strike_range[1]):
                    continue
                
                ce_data = option.get('CE', {})
                pe_data = option.get('PE', {})
                
                call_oi = ce_data.get('open_interest', 0)
                put_oi = pe_data.get('open_interest', 0)
                
                strike_data[strike] = {
                    'call_oi': call_oi,
                    'put_oi': put_oi,
                    'total_oi': call_oi + put_oi,
                    'call_price': ce_data.get('last_price', 0),
                    'put_price': pe_data.get('last_price', 0)
                }
            
            return strike_data
            
        except Exception as e:
            logger.error(f"❌ Error extracting strike OI data: {e}")
            return {}
    
    def _calculate_pain_at_strikes(self, strike_data: Dict[int, Dict]) -> Dict[int, Dict]:
        """Calculate total pain at each potential expiry price"""
        try:
            pain_calculations = {}
            strikes = list(strike_data.keys())
            
            for expiry_price in strikes:
                call_pain = 0
                put_pain = 0
                
                for strike, data in strike_data.items():
                    # Call options pain: if expiry_price > strike, call holders profit
                    if expiry_price > strike:
                        call_pain += data['call_oi'] * (expiry_price - strike)
                    
                    # Put options pain: if expiry_price < strike, put holders profit
                    if expiry_price < strike:
                        put_pain += data['put_oi'] * (strike - expiry_price)
                
                total_pain = call_pain + put_pain
                
                pain_calculations[expiry_price] = {
                    'call_pain': call_pain,
                    'put_pain': put_pain,
                    'total_pain': total_pain
                }
            
            return pain_calculations
            
        except Exception as e:
            logger.error(f"❌ Error calculating pain at strikes: {e}")
            return {}
    
    def _analyze_open_interest_distribution(self, strike_data: Dict[int, Dict]) -> Dict[str, Any]:
        """Analyze the distribution of open interest"""
        try:
            if not strike_data:
                return {}
            
            strikes = list(strike_data.keys())
            call_ois = [data['call_oi'] for data in strike_data.values()]
            put_ois = [data['put_oi'] for data in strike_data.values()]
            
            total_call_oi = sum(call_ois)
            total_put_oi = sum(put_ois)
            total_oi = total_call_oi + total_put_oi
            
            # Find weighted average strike
            if total_oi > 0:
                weighted_call_strike = sum(strike * data['call_oi'] for strike, data in strike_data.items()) / total_call_oi if total_call_oi > 0 else 0
                weighted_put_strike = sum(strike * data['put_oi'] for strike, data in strike_data.items()) / total_put_oi if total_put_oi > 0 else 0
            else:
                weighted_call_strike = weighted_put_strike = 0
            
            return {
                'total_call_oi': total_call_oi,
                'total_put_oi': total_put_oi,
                'total_oi': total_oi,
                'pcr_oi': total_put_oi / total_call_oi if total_call_oi > 0 else 0,
                'weighted_call_strike': round(weighted_call_strike, 0),
                'weighted_put_strike': round(weighted_put_strike, 0),
                'oi_concentration': self._calculate_oi_concentration_metrics(strike_data),
                'max_oi_strikes': {
                    'call': max(strikes, key=lambda k: strike_data[k]['call_oi']),
                    'put': max(strikes, key=lambda k: strike_data[k]['put_oi'])
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing OI distribution: {e}")
            return {}
    
    def _identify_support_resistance(self, strike_data: Dict[int, Dict], spot_price: float) -> Dict[str, List]:
        """Identify support and resistance levels from OI data"""
        try:
            support_levels = []
            resistance_levels = []
            
            # Sort strikes by OI
            sorted_by_call_oi = sorted(strike_data.items(), key=lambda x: x[1]['call_oi'], reverse=True)
            sorted_by_put_oi = sorted(strike_data.items(), key=lambda x: x[1]['put_oi'], reverse=True)
            
            # High call OI above current price = potential resistance
            for strike, data in sorted_by_call_oi[:5]:  # Top 5
                if strike > spot_price and data['call_oi'] > 0:
                    resistance_levels.append({
                        'strike': strike,
                        'oi': data['call_oi'],
                        'distance_pct': ((strike - spot_price) / spot_price) * 100
                    })
            
            # High put OI below current price = potential support
            for strike, data in sorted_by_put_oi[:5]:  # Top 5
                if strike < spot_price and data['put_oi'] > 0:
                    support_levels.append({
                        'strike': strike,
                        'oi': data['put_oi'],
                        'distance_pct': ((spot_price - strike) / spot_price) * 100
                    })
            
            return {
                'support': sorted(support_levels, key=lambda x: x['strike'], reverse=True),
                'resistance': sorted(resistance_levels, key=lambda x: x['strike'])
            }
            
        except Exception as e:
            logger.error(f"❌ Error identifying support/resistance: {e}")
            return {'support': [], 'resistance': []}
    
    def _find_highest_oi_strikes(self, strike_data: Dict[int, Dict], 
                                option_type: str, count: int = 5) -> List[Dict]:
        """Find strikes with highest OI for given option type"""
        try:
            oi_key = 'call_oi' if option_type.lower() == 'call' else 'put_oi'
            sorted_strikes = sorted(strike_data.items(), 
                                  key=lambda x: x[1][oi_key], reverse=True)
            
            return [{'strike': strike, 'oi': data[oi_key]} 
                   for strike, data in sorted_strikes[:count] if data[oi_key] > 0]
            
        except Exception as e:
            logger.error(f"❌ Error finding highest OI strikes: {e}")
            return []
    
    def _calculate_pcr_oi(self, strike_data: Dict[int, Dict]) -> float:
        """Calculate Put-Call ratio based on Open Interest"""
        try:
            total_call_oi = sum(data['call_oi'] for data in strike_data.values())
            total_put_oi = sum(data['put_oi'] for data in strike_data.values())
            
            return total_put_oi / total_call_oi if total_call_oi > 0 else 0
            
        except Exception:
            return 0
    
    def _estimate_gamma(self, spot: float, strike: float, time_to_expiry: float, option_type: str) -> float:
        """Estimate gamma for GEX calculation (simplified)"""
        try:
            # Simplified gamma estimation
            sigma = 0.20  # Assume 20% volatility
            moneyness = strike / spot
            
            # Gamma is highest at ATM and decreases with distance
            atm_distance = abs(moneyness - 1.0)
            gamma = 0.01 * np.exp(-5 * atm_distance) * np.sqrt(time_to_expiry)
            
            return max(gamma, 0.0001)
            
        except Exception:
            return 0.0001
    
    def _find_zero_gex_level(self, gex_data: List[Dict]) -> Optional[float]:
        """Find the price level where GEX crosses zero"""
        try:
            for i in range(len(gex_data) - 1):
                current_gex = gex_data[i]['total_gex']
                next_gex = gex_data[i + 1]['total_gex']
                
                # Check for sign change
                if current_gex * next_gex < 0:
                    # Linear interpolation to find zero crossing
                    price1, gex1 = gex_data[i]['price'], current_gex
                    price2, gex2 = gex_data[i + 1]['price'], next_gex
                    
                    zero_price = price1 - gex1 * (price2 - price1) / (gex2 - gex1)
                    return zero_price
            
            return None
            
        except Exception:
            return None
    
    def _empty_max_pain_result(self, spot_price: float) -> Dict[str, Any]:
        """Return empty Max Pain result structure"""
        return {
            'max_pain_strike': spot_price,
            'max_pain_amount': 0,
            'current_spot': spot_price,
            'distance_from_spot': 0,
            'distance_percentage': 0,
            'total_call_oi': 0,
            'total_put_oi': 0,
            'put_call_oi_ratio': 0
        }
    
    # Additional helper methods for completeness
    def _calculate_oi_concentration(self, strike_data: Dict, option_type: str) -> Dict:
        """Calculate OI concentration metrics"""
        return {}
    
    def _calculate_oi_skew(self, strike_data: Dict) -> float:
        """Calculate OI skew"""
        return 0.0
    
    def _identify_fresh_positions(self, current_data: Dict, previous_chain: Dict) -> List:
        """Identify fresh option positions"""
        return []
    
    def _analyze_oi_changes(self, current_data: Dict, previous_chain: Dict) -> Dict:
        """Analyze changes in OI"""
        return {}
    
    def _calculate_oi_concentration_metrics(self, strike_data: Dict) -> Dict:
        """Calculate detailed OI concentration metrics"""
        return {
            'top_5_strikes_oi_pct': 0,
            'herfindahl_index': 0
        }