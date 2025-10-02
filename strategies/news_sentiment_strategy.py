# strategies/news_sentiment_strategy.py
"""
News Sentiment Based Options Trading Strategy
Uses AI-powered news analysis to make CALL/PUT decisions for Nifty options
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from kiteconnect import KiteConnect

from strategies.base_strategy import BaseStrategy, TradeSignal
from intelligence.gemini_client import GeminiNewsAnalyzer, NewsAnalysisResult
from risk_management.options_risk_manager import OptionsRiskManager
from utils.market_utils import MarketDataManager
from config.settings import TradingConfig

logger = logging.getLogger(__name__)

class NewsSentimentStrategy(BaseStrategy):
    """News sentiment-based options trading strategy"""
    
    def __init__(self, 
                 kite_client: KiteConnect,
                 ai_analyzer: GeminiNewsAnalyzer,
                 risk_manager: OptionsRiskManager,
                 market_data: MarketDataManager):
        """Initialize news sentiment strategy"""
        super().__init__(kite_client, risk_manager, market_data)
        
        self.ai_analyzer = ai_analyzer
        
        # Strategy parameters
        self.min_confidence = 7  # Minimum confidence for high-conviction trades
        self.position_size_multiplier = 1.0
        
        # Signal filtering
        self.last_analysis_time = datetime.now()
        self.processed_signals: Dict[str, datetime] = {}
        
        logger.info("📰 News Sentiment Strategy initialized")
    
    def get_strategy_name(self) -> str:
        """Get strategy name"""
        return "News Sentiment Strategy"
    
    def process_analysis_results(self, analysis_results: List[NewsAnalysisResult]) -> List[TradeSignal]:
        """Process AI analysis and generate trading signals"""
        try:
            logger.info(f"📊 Processing {len(analysis_results)} analysis results...")
            
            # Filter and prioritize signals
            high_confidence_signals = self._filter_high_confidence_signals(analysis_results)
            
            if not high_confidence_signals:
                logger.info("ℹ️ No high confidence signals found")
                return []
            
            # Convert to trade signals
            trade_signals = []
            
            for result in high_confidence_signals:
                signal = self._create_trade_signal(result)
                if signal:
                    trade_signals.append(signal)
                    self.total_signals += 1
            
            # Rank signals by confidence and market conditions
            ranked_signals = self._rank_signals(trade_signals)
            
            # Apply position limits (max 3 signals per cycle)
            final_signals = ranked_signals[:3]
            
            logger.info(f"📋 Generated {len(final_signals)} actionable trade signals")
            
            return final_signals
            
        except Exception as e:
            logger.error(f"❌ Failed to process analysis results: {e}")
            return []
    
    def _filter_high_confidence_signals(self, analysis_results: List[NewsAnalysisResult]) -> List[NewsAnalysisResult]:
        """Filter for high confidence trading signals"""
        try:
            filtered_signals = []
            
            for result in analysis_results:
                # Check confidence threshold
                if result.confidence < self.min_confidence:
                    continue
                
                # Check if action is actionable (not HOLD)
                if result.action == 'HOLD':
                    continue
                
                # Check if we haven't processed similar signal recently
                signal_key = f"{result.action}_{result.strike_type}"
                if signal_key in self.processed_signals:
                    time_diff = datetime.now() - self.processed_signals[signal_key]
                    if time_diff.total_seconds() < 900:  # 15 minutes cooldown
                        continue
                
                # Check market impact
                if result.impact not in ['High', 'Medium']:
                    continue
                
                filtered_signals.append(result)
                
                # Mark as processed
                self.processed_signals[signal_key] = datetime.now()
            
            logger.info(f"🔍 Filtered {len(filtered_signals)} high-confidence signals from {len(analysis_results)}")
            
            return filtered_signals
            
        except Exception as e:
            logger.error(f"❌ Signal filtering failed: {e}")
            return []
    
    def _create_trade_signal(self, analysis_result: NewsAnalysisResult) -> Optional[TradeSignal]:
        """Create trade signal from analysis result"""
        try:
            # Get current Nifty level
            nifty_ltp = self.market_data.get_nifty_ltp()
            if nifty_ltp == 0:
                logger.warning("⚠️ Could not get Nifty LTP")
                return None
            
            # Find appropriate strike and option contract
            strike_info = self._select_optimal_strike(analysis_result, nifty_ltp)
            if not strike_info:
                logger.warning(f"⚠️ No suitable strike found for {analysis_result.action}")
                return None
            
            strike_price, option_type, premium = strike_info
            
            # Generate trading symbol
            symbol = self._generate_trading_symbol(strike_price, option_type)
            if not symbol:
                logger.warning(f"⚠️ Could not generate trading symbol for strike {strike_price}")
                return None
            
            # Calculate position size
            quantity = self._calculate_position_size(analysis_result, premium)
            if quantity == 0:
                logger.warning("⚠️ Position size calculation returned 0")
                return None
            
            # Calculate stop loss and target
            stop_loss = premium * 0.8  # 20% stop loss
            target = premium * 1.5     # 50% target
            
            # Create trade signal
            signal = TradeSignal(
                symbol=symbol,
                action=analysis_result.action,
                strike_price=strike_price,
                option_type=option_type,
                quantity=quantity,
                confidence=analysis_result.confidence,
                entry_price=premium,
                stop_loss=stop_loss,
                target=target,
                reason=f"{analysis_result.sentiment} sentiment: {analysis_result.reason[:100]}"
            )
            
            logger.info(f"✅ Created signal: {symbol} {analysis_result.action} {quantity} @ ₹{premium} (Confidence: {analysis_result.confidence})")
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Failed to create trade signal: {e}")
            return None
    
    def _select_optimal_strike(self, analysis_result: NewsAnalysisResult, nifty_ltp: float) -> Optional[Tuple[float, str, float]]:
        """Select optimal strike price and get premium"""
        try:
            # Get tradeable strikes from market data
            tradeable_strikes = self.market_data.find_tradeable_strikes(
                analysis_result.action,
                analysis_result.strike_type
            )
            
            if not tradeable_strikes:
                logger.warning(f"⚠️ No tradeable strikes found for {analysis_result.action} {analysis_result.strike_type}")
                return None
            
            # Select best strike based on confidence
            best_strike = tradeable_strikes[0] if tradeable_strikes else None
            
            if best_strike:
                logger.debug(f"📍 Selected strike: {best_strike[0]} {best_strike[1]} @ ₹{best_strike[2]}")
            
            return best_strike
            
        except Exception as e:
            logger.error(f"❌ Strike selection failed: {e}")
            return None
    
    def _generate_trading_symbol(self, strike_price: float, option_type: str) -> Optional[str]:
        """Generate trading symbol for the option"""
        try:
            import datetime as dt
            today = dt.datetime.now()
            
            # Find next Thursday (weekly expiry)
            days_ahead = 3 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            
            expiry_date = today + dt.timedelta(days_ahead)
            expiry_str = expiry_date.strftime("%y%m%d")
            
            # Generate symbol: NIFTY[YYMMDD][STRIKE][CE/PE]
            symbol = f"NIFTY{expiry_str}{int(strike_price)}{option_type}"
            
            return symbol
            
        except Exception as e:
            logger.error(f"❌ Symbol generation failed: {e}")
            return None
    
    def _calculate_position_size(self, analysis_result: NewsAnalysisResult, premium: float) -> int:
        """Calculate position size based on confidence and risk"""
        try:
            # Base calculation
            confidence_multiplier = analysis_result.confidence / 10.0
            impact_multiplier = {'High': 1.0, 'Medium': 0.8, 'Low': 0.6}.get(analysis_result.impact, 0.6)
            
            # Simplified position sizing
            base_lots = 2  # 2 lots base
            final_lots = int(base_lots * confidence_multiplier * impact_multiplier)
            final_quantity = max(1, final_lots) * 50  # Nifty lot size is 50
            
            logger.debug(f"📏 Position size: {final_quantity}")
            
            return final_quantity
            
        except Exception as e:
            logger.error(f"❌ Position size calculation failed: {e}")
            return 50  # Default 1 lot
    
    def _rank_signals(self, signals: List[TradeSignal]) -> List[TradeSignal]:
        """Rank signals by priority"""
        try:
            # Sort by confidence (high to low)
            ranked = sorted(signals, key=lambda s: -s.confidence)
            
            logger.debug(f"📊 Ranked {len(ranked)} signals by priority")
            
            return ranked
            
        except Exception as e:
            logger.error(f"❌ Signal ranking failed: {e}")
            return signals

# Export main class
__all__ = ['NewsSentimentStrategy']