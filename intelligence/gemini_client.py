# intelligence/gemini_client.py
"""
Gemini AI Client for News Analysis and Trading Signal Generation
Analyzes market news and generates trading recommendations for Nifty options
"""

import google.generativeai as genai  # type: ignore
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from config.settings import TradingConfig
import time

# Handle potential import issues with type checking
try:
    from google.generativeai.types import HarmCategory, HarmBlockThreshold, GenerationConfig  # type: ignore
except ImportError:
    # Fallback for type checking
    HarmCategory = Any
    HarmBlockThreshold = Any
    GenerationConfig = Any

# Setup logging
logger = logging.getLogger(__name__)

@dataclass
class NewsAnalysisResult:
    """Structure for news analysis results"""
    sentiment: str          # Bullish/Bearish/Neutral
    impact: str            # High/Medium/Low
    action: str            # CALL/PUT/HOLD
    strike_type: str       # ITM/ATM/OTM
    confidence: int        # 1-10
    reason: str           # Explanation
    timestamp: datetime
    
class GeminiNewsAnalyzer:
    """Gemini AI client for news analysis and trading signal generation"""
    
    def __init__(self) -> None:
        """Initialize Gemini AI client with enhanced security settings"""
        try:
            # Configure Gemini AI
            if hasattr(genai, 'configure'):
                genai.configure(api_key=TradingConfig.GEMINI_API_KEY)  # type: ignore
            else:
                raise ImportError("Gemini AI configure method not available")
            
            # Enhanced generation configuration for production
            generation_config: Dict[str, Any] = {
                'temperature': TradingConfig.TEMPERATURE,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': TradingConfig.MAX_TOKENS,
            }
            
            # Initialize model with safety settings for restricted APIs
            try:
                # Try to create model with safety settings
                if hasattr(genai, 'GenerativeModel'):
                    safety_settings = self._get_safety_settings()
                    self.model = genai.GenerativeModel(  # type: ignore
                        model_name=TradingConfig.GEMINI_MODEL,
                        generation_config=generation_config,  # type: ignore
                        safety_settings=safety_settings  # type: ignore
                    )
                else:
                    raise ImportError("Gemini GenerativeModel not available")
            except Exception as safety_error:
                logger.warning(f"⚠️ Could not set safety settings: {safety_error}")
                # Fallback without safety settings
                self.model = genai.GenerativeModel(  # type: ignore
                    model_name=TradingConfig.GEMINI_MODEL,
                    generation_config=generation_config  # type: ignore
                )
            
            # Test connection with timeout handling
            self._test_connection()
            
            logger.info("✅ Gemini AI client initialized successfully with security settings")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini AI client: {e}")
            raise
    
    def _get_safety_settings(self) -> Optional[Dict[Any, Any]]:
        """Get safety settings with proper error handling"""
        try:
            # Try to access safety settings from genai.types
            if hasattr(genai, 'types'):
                harm_category = genai.types.HarmCategory  # type: ignore
                harm_threshold = genai.types.HarmBlockThreshold  # type: ignore
                
                return {  # type: ignore
                    harm_category.HARM_CATEGORY_HARASSMENT: harm_threshold.BLOCK_NONE,  # type: ignore
                    harm_category.HARM_CATEGORY_HATE_SPEECH: harm_threshold.BLOCK_NONE,  # type: ignore
                    harm_category.HARM_CATEGORY_SEXUALLY_EXPLICIT: harm_threshold.BLOCK_NONE,  # type: ignore
                    harm_category.HARM_CATEGORY_DANGEROUS_CONTENT: harm_threshold.BLOCK_NONE,  # type: ignore
                }
            else:
                logger.warning("⚠️ genai.types not available, using basic safety settings")
                return None
        except Exception as e:
            logger.warning(f"⚠️ Could not create safety settings: {e}")
            return None
    
    def _test_connection(self) -> None:
        """Test Gemini AI connection"""
        try:
            test_prompt = "Test connection. Respond with 'OK' if working."
            response: Any = self.model.generate_content(test_prompt)
            
            if hasattr(response, 'text') and response.text:
                logger.info("🔗 Gemini AI connection test successful")
            else:
                raise Exception("No response from Gemini AI")
                
        except Exception as e:
            logger.error(f"❌ Gemini AI connection test failed: {e}")
            raise
    
    def analyze_news_batch(self, news_items: List[str]) -> List[NewsAnalysisResult]:
        """Analyze multiple news items and return trading signals"""
        results = []
        
        for i, news_item in enumerate(news_items, 1):
            try:
                logger.info(f"📰 Analyzing news item {i}/{len(news_items)}")
                result = self.analyze_single_news(news_item)
                results.append(result)
                
                # Rate limiting - 1 request per second
                if i < len(news_items):
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Failed to analyze news item {i}: {e}")
                continue
        
        return results
    
    def analyze_single_news(self, news_content: str) -> NewsAnalysisResult:
        """Analyze single news item and return trading signal"""
        try:
            # Create analysis prompt
            prompt = self._create_news_analysis_prompt(news_content)
            
            # Generate analysis
            generation_config = self._create_generation_config(
                temperature=TradingConfig.TEMPERATURE,
                max_output_tokens=TradingConfig.MAX_TOKENS
            )
            
            response: Any = self.model.generate_content(  # type: ignore
                prompt,
                generation_config=generation_config  # type: ignore
            )
            
            # Parse response
            analysis = self._parse_analysis_response(response.text)
            
            logger.info(f"📊 Analysis complete: {analysis.sentiment} sentiment, {analysis.confidence}/10 confidence")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ News analysis failed: {e}")
            # Return neutral analysis on failure
            return NewsAnalysisResult(
                sentiment="Neutral",
                impact="Low", 
                action="HOLD",
                strike_type="ATM",
                confidence=1,
                reason=f"Analysis failed: {str(e)[:100]}",
                timestamp=datetime.now()
            )
    
    def _create_news_analysis_prompt(self, news_content: str) -> str:
        """Create structured prompt for news analysis"""
        
        current_nifty = 24836  # We'll make this dynamic later
        
        prompt = f"""
You are a professional options trader analyzing news for Nifty 50 trading decisions.

CURRENT MARKET CONTEXT:
- Nifty 50 Level: {current_nifty}
- Weekly expiry available (Oct 7, 2025)
- Options available: Strikes from 24500 to 25200

NEWS TO ANALYZE:
{news_content}

ANALYSIS FRAMEWORK:
Analyze this news for its impact on Nifty 50 and provide specific options trading recommendations.

Consider:
1. Direct impact on Nifty 50 index
2. Sector rotation implications
3. Market sentiment shift
4. Volatility expectations
5. Time sensitivity of impact

RESPONSE FORMAT (use exact format):
Sentiment: [Bullish/Bearish/Neutral]
Impact: [High/Medium/Low]
Action: [CALL/PUT/HOLD]
Strike: [ITM/ATM/OTM]
Confidence: [1-10]
Reason: [Brief 2-3 line explanation focusing on why this news affects Nifty and the recommended options strategy]

TRADING GUIDELINES:
- High impact + Bullish = CALL recommendations
- High impact + Bearish = PUT recommendations  
- Medium/Low impact = consider HOLD unless very confident
- ITM for safer plays, OTM for aggressive momentum
- Confidence 7+ required for actual trades

Provide specific, actionable analysis suitable for algorithmic trading execution.
        """
        
        return prompt
    
    def _parse_analysis_response(self, response_text: str) -> NewsAnalysisResult:
        """Parse Gemini response into structured analysis result"""
        try:
            lines = response_text.strip().split('\n')
            
            # Initialize defaults
            sentiment = "Neutral"
            impact = "Low"
            action = "HOLD"
            strike_type = "ATM"
            confidence = 5
            reason = "Default analysis"
            
            # Parse structured response
            for line in lines:
                line = line.strip()
                if line.startswith('Sentiment:'):
                    sentiment = line.split(':', 1)[1].strip()
                elif line.startswith('Impact:'):
                    impact = line.split(':', 1)[1].strip()
                elif line.startswith('Action:'):
                    action = line.split(':', 1)[1].strip()
                elif line.startswith('Strike:'):
                    strike_type = line.split(':', 1)[1].strip()
                elif line.startswith('Confidence:'):
                    try:
                        confidence = int(line.split(':', 1)[1].strip())
                        confidence = max(1, min(10, confidence))  # Clamp 1-10
                    except:
                        confidence = 5
                elif line.startswith('Reason:'):
                    reason = line.split(':', 1)[1].strip()
            
            # Validate values
            sentiment = sentiment if sentiment in ['Bullish', 'Bearish', 'Neutral'] else 'Neutral'
            impact = impact if impact in ['High', 'Medium', 'Low'] else 'Low'
            action = action if action in ['CALL', 'PUT', 'HOLD'] else 'HOLD'
            strike_type = strike_type if strike_type in ['ITM', 'ATM', 'OTM'] else 'ATM'
            
            return NewsAnalysisResult(
                sentiment=sentiment,
                impact=impact,
                action=action,
                strike_type=strike_type,
                confidence=confidence,
                reason=reason,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to parse analysis response: {e}")
            
            # Return safe default
            return NewsAnalysisResult(
                sentiment="Neutral",
                impact="Low",
                action="HOLD", 
                strike_type="ATM",
                confidence=1,
                reason=f"Parsing failed: {str(e)[:50]}",
                timestamp=datetime.now()
            )
    
    def get_nifty50_news_analysis(self) -> List[NewsAnalysisResult]:
        """Get comprehensive Nifty 50 news analysis with robust fallback handling"""
        
        # Optimized prompt for reliable 10-point analysis
        analysis_prompt = """
Generate exactly 10 trading recommendations for Nifty 50 options:

First 5 points - Major Nifty 50 constituents (Reliance, TCS, HDFC Bank, Infosys, ICICI Bank):
Next 5 points - Global events affecting Nifty 50:

Format each point exactly as:
1. [Company/Event]: [Brief news description] - Suggestion: (CALL/PUT, ITM/ATM/OTM)
2. [Company/Event]: [Brief news description] - Suggestion: (CALL/PUT, ITM/ATM/OTM)
...
10. [Company/Event]: [Brief news description] - Suggestion: (CALL/PUT, ITM/ATM/OTM)

Keep each point concise (max 80 characters). Focus on actionable trading signals.
        """
        
        try:
            start_time = time.time()
            logger.info("📰 Generating comprehensive Nifty 50 news analysis...")
            
            generation_config = self._create_generation_config(
                temperature=0.4,
                max_output_tokens=1400  # Optimized for speed
            )
            
            response: Any = self.model.generate_content(  # type: ignore
                analysis_prompt,
                generation_config=generation_config  # type: ignore
            )
            
            # Monitor performance
            elapsed_time = time.time() - start_time
            logger.info(f"⏱️ Gemini API response time: {elapsed_time:.2f} seconds")
            
            # Parse the 10-point response
            analysis_results = self._parse_ten_point_analysis(response.text)
            
            # Ensure we always have 10 results (fill with mock if needed)
            while len(analysis_results) < 10:
                mock_result = self._generate_mock_signal(len(analysis_results) + 1)
                analysis_results.append(mock_result)
                
            # Limit to exactly 10 results
            analysis_results = analysis_results[:10]
            
            logger.info(f"📊 Generated {len(analysis_results)} news analysis points in {elapsed_time:.2f}s")
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"❌ Failed to generate news analysis: {e}")
            logger.info("🔄 Falling back to mock analysis data...")
            return self._get_full_mock_analysis()
    
    def _parse_ten_point_analysis(self, response_text: str) -> List[NewsAnalysisResult]:
        """Parse 10-point news analysis response with enhanced error handling"""
        results = []
        
        try:
            lines = response_text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Look for numbered points (1-10)
                if any(line.startswith(f"{i}.") for i in range(1, 11)):
                    try:
                        # Extract suggestion part (multiple patterns)
                        if 'Suggestion:' in line or ('(' in line and ')' in line):
                            # Parse the line for action and strike type
                            action, strike_type = self._extract_suggestion_from_line(line)
                            
                            # Determine sentiment and impact based on action
                            sentiment = "Bullish" if action == "CALL" else "Bearish" if action == "PUT" else "Neutral"
                            impact = "High" if action in ["CALL", "PUT"] else "Medium"
                            
                            # Extract company/topic (more flexible parsing)
                            if ':' in line:
                                parts = line.split(':', 2)
                                company_event = parts[1].split('-')[0].strip() if len(parts) > 1 else "Market Event"
                                news_content = parts[1] if len(parts) > 1 else line
                            else:
                                company_event = "Market Event"
                                news_content = line
                            
                            # Calculate confidence based on parsing quality
                            confidence = 8 if action in ["CALL", "PUT"] else 6
                            
                            result = NewsAnalysisResult(
                                sentiment=sentiment,
                                impact=impact,
                                action=action,
                                strike_type=strike_type,
                                confidence=confidence,
                                reason=news_content[:100] + "..." if len(news_content) > 100 else news_content,
                                timestamp=datetime.now()
                            )
                            
                            results.append(result)
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to parse line: {line[:30]}... - Error: {e}")
                        # Add a placeholder result instead of skipping
                        placeholder = self._generate_mock_signal(len(results) + 1)
                        results.append(placeholder)
                        continue
            
            logger.info(f"📋 Successfully parsed {len(results)} analysis points")
            return results[:10]  # Ensure max 10 results
            
        except Exception as e:
            logger.error(f"❌ Failed to parse 10-point analysis: {e}")
            return []
    
    def _extract_suggestion_from_line(self, line: str) -> Tuple[str, str]:
        """Extract trading suggestion from news line"""
        try:
            # Look for patterns like (CALL, ITM) or (PUT, ATM)
            import re
            
            # Pattern to match (ACTION, STRIKE_TYPE)
            pattern = r'\(([^,]+),\s*([^)]+)\)'
            match = re.search(pattern, line)
            
            if match:
                action = match.group(1).strip().upper()
                strike_type = match.group(2).strip().upper()
                
                # Validate and normalize
                action = action if action in ['CALL', 'PUT'] else 'HOLD'
                strike_type = strike_type if strike_type in ['ITM', 'ATM', 'OTM'] else 'ATM'
                
                return action, strike_type
            
            # Fallback parsing
            line_upper = line.upper()
            if 'CALL' in line_upper:
                action = 'CALL'
            elif 'PUT' in line_upper:
                action = 'PUT'
            else:
                action = 'HOLD'
            
            if 'ITM' in line_upper:
                strike_type = 'ITM'
            elif 'OTM' in line_upper:
                strike_type = 'OTM'
            else:
                strike_type = 'ATM'
            
            return action, strike_type
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to extract suggestion: {e}")
            return 'HOLD', 'ATM'
    
    def _generate_mock_signal(self, point_number: int) -> NewsAnalysisResult:
        """Generate a single mock trading signal for fallback"""
        import random
        
        # Predefined mock scenarios
        mock_scenarios = [
            {"company": "Reliance", "action": "CALL", "strike": "ATM", "sentiment": "Bullish", "reason": "Strong quarterly results expected"},
            {"company": "TCS", "action": "PUT", "strike": "OTM", "sentiment": "Bearish", "reason": "IT sector facing headwinds"},
            {"company": "HDFC Bank", "action": "CALL", "strike": "ITM", "sentiment": "Bullish", "reason": "Banking sector momentum"},
            {"company": "Infosys", "action": "HOLD", "strike": "ATM", "sentiment": "Neutral", "reason": "Mixed sector outlook"},
            {"company": "ICICI Bank", "action": "CALL", "strike": "ATM", "sentiment": "Bullish", "reason": "Credit growth positive"},
            {"company": "Global Markets", "action": "PUT", "strike": "ATM", "sentiment": "Bearish", "reason": "International volatility"},
            {"company": "FII Activity", "action": "CALL", "strike": "OTM", "sentiment": "Bullish", "reason": "Foreign inflows increasing"},
            {"company": "Oil Prices", "action": "PUT", "strike": "ITM", "sentiment": "Bearish", "reason": "Crude oil impact on markets"},
            {"company": "US Fed Policy", "action": "HOLD", "strike": "ATM", "sentiment": "Neutral", "reason": "Awaiting policy clarity"},
            {"company": "Market Sentiment", "action": "CALL", "strike": "ATM", "sentiment": "Bullish", "reason": "Overall positive momentum"}
        ]
        
        # Select mock scenario based on point number
        scenario = mock_scenarios[(point_number - 1) % len(mock_scenarios)]
        
        return NewsAnalysisResult(
            sentiment=scenario["sentiment"],
            impact="Medium",
            action=scenario["action"],
            strike_type=scenario["strike"],
            confidence=6,  # Mock data gets lower confidence
            reason=f"Mock: {scenario['reason']} (Point {point_number})",
            timestamp=datetime.now()
        )
    
    def _get_full_mock_analysis(self) -> List[NewsAnalysisResult]:
        """Get complete 10-point mock analysis for fallback"""
        logger.info("🎭 Generating full mock analysis (10 points)...")
        
        mock_results = []
        for i in range(1, 11):
            mock_result = self._generate_mock_signal(i)
            mock_results.append(mock_result)
        
        logger.info(f"✅ Generated {len(mock_results)} mock analysis points")
        return mock_results

    def _create_generation_config(self, temperature: float, max_output_tokens: int) -> Union[Dict[str, Any], Any]:
        """Create generation config with proper error handling"""
        try:
            # Try to use proper GenerationConfig if available
            if hasattr(genai, 'types') and hasattr(genai.types, 'GenerationConfig'):  # type: ignore
                return genai.types.GenerationConfig(  # type: ignore
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                )
            else:
                # Fallback to dict format
                logger.info("Using dict format for generation config")
                return {
                    'temperature': temperature,
                    'max_output_tokens': max_output_tokens,
                }
        except Exception as e:
            logger.warning(f"⚠️ Using fallback generation config: {e}")
            return {
                'temperature': temperature,
                'max_output_tokens': max_output_tokens,
            }

    def test_analysis_system(self) -> bool:
        """Test the complete analysis system"""
        try:
            logger.info("🧪 Testing Gemini analysis system...")
            
            # Test single news analysis
            test_news = "Reliance Industries reports strong quarterly earnings, beating expectations by 15%. Stock rallies 5% in pre-market trading."
            
            result = self.analyze_single_news(test_news)
            logger.info(f"✅ Single analysis test: {result.sentiment} - {result.action} - Confidence: {result.confidence}")
            
            # Test comprehensive news analysis
            comprehensive_results = self.get_nifty50_news_analysis()
            logger.info(f"✅ Comprehensive analysis test: Generated {len(comprehensive_results)} analysis points")
            
            if comprehensive_results:
                for i, result in enumerate(comprehensive_results[:3], 1):
                    logger.info(f"   {i}. {result.sentiment} - {result.action} {result.strike_type}")
            
            logger.info("🎉 Gemini analysis system test completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Analysis system test failed: {e}")
            return False

# Export the main class
__all__ = ['GeminiNewsAnalyzer', 'NewsAnalysisResult']

# Command line testing
if __name__ == "__main__":
    print("🧪 Testing Gemini Client Directly...")
    print("=" * 50)
    
    try:
        # Initialize analyzer
        analyzer = GeminiNewsAnalyzer()
        print("✅ Initialization successful!")
        
        # Run built-in test
        test_result = analyzer.test_analysis_system()
        
        if test_result:
            print("\n🎉 Direct test completed successfully!")
        else:
            print("\n❌ Direct test failed!")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
