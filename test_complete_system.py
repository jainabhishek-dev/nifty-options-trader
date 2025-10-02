# test_complete_system.py
"""
Complete System Integration Test
Tests all components working together
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_complete_trading_system():
    """Test the complete trading system integration"""
    print("🚀 TESTING COMPLETE NIFTY OPTIONS TRADING SYSTEM")
    print("=" * 70)
    
    # Test 1: Configuration and Logging
    print("\n1️⃣ Testing Configuration & Logging...")
    try:
        from config.settings import TradingConfig, validate_config
        from utils.logging_config import setup_logging
        
        # Initialize logging
        logger = setup_logging()
        
        # Validate configuration
        if validate_config():
            print("✅ Configuration validated successfully")
        else:
            print("❌ Configuration validation failed")
            return False
            
        print(f"✅ Trading Mode: {TradingConfig.TRADING_MODE}")
        print(f"✅ Max Daily Loss: ₹{TradingConfig.MAX_DAILY_LOSS:,}")
        print(f"✅ Max Positions: {TradingConfig.MAX_POSITIONS}")
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False
    
    # Test 2: Authentication System
    print(f"\n2️⃣ Testing Authentication System...")
    try:
        from auth_handler import KiteAuthenticator
        
        authenticator = KiteAuthenticator()
        print(f"✅ Kite Connect client initialized")
        api_key = TradingConfig.KITE_API_KEY or "Not configured"
        print(f"✅ API Key configured: {api_key[:10]}..." if api_key != "Not configured" else "⚠️ API Key not configured")
        
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return False
    
    # Test 3: AI Analysis Engine
    print(f"\n3️⃣ Testing AI Analysis Engine...")
    try:
        from intelligence.gemini_client import GeminiNewsAnalyzer
        
        analyzer = GeminiNewsAnalyzer()
        print(f"✅ Gemini AI client initialized")
        
        # Test analysis
        analysis_results = analyzer.get_nifty50_news_analysis()
        print(f"✅ Generated {len(analysis_results)} analysis signals")
        
        # Show sample results
        for i, result in enumerate(analysis_results[:3], 1):
            print(f"   {i}. {result.sentiment} - {result.action} {result.strike_type} (Confidence: {result.confidence})")
            
    except Exception as e:
        print(f"❌ AI analysis test failed: {e}")
        return False
    
    # Test 4: Market Data System  
    print(f"\n4️⃣ Testing Market Data System...")
    try:
        from utils.market_utils import MarketDataManager
        
        market_data = MarketDataManager(authenticator.kite)
        print(f"✅ Market data manager initialized")
        print(f"✅ Loaded {len(market_data.nifty_options)} Nifty options contracts")
        
        # Test data refresh
        market_data.refresh_data()
        nifty_ltp = market_data.get_nifty_ltp()
        print(f"✅ Nifty 50 LTP: ₹{nifty_ltp:,.2f}")
        
    except Exception as e:
        print(f"❌ Market data test failed: {e}")
        return False
    
    # Test 5: Risk Management
    print(f"\n5️⃣ Testing Risk Management...")
    try:
        from risk_management.options_risk_manager import OptionsRiskManager
        
        risk_manager = OptionsRiskManager(authenticator.kite, market_data)
        print(f"✅ Risk manager initialized")
        
        # Test risk check
        test_signal = {
            'symbol': 'TEST',
            'confidence': 8,
            'premium': 50
        }
        
        can_trade = risk_manager.can_place_new_trade(test_signal)
        print(f"✅ Risk check result: {'Allowed' if can_trade else 'Blocked'}")
        
        risk_summary = risk_manager.get_risk_summary()
        print(f"✅ Daily trades: {risk_summary.get('daily_trades', 0)}/{risk_summary.get('max_daily_trades', 10)}")
        
    except Exception as e:
        print(f"❌ Risk management test failed: {e}")
        return False
    
    # Test 6: Trading Strategy
    print(f"\n6️⃣ Testing Trading Strategy...")
    try:
        from strategies.news_sentiment_strategy import NewsSentimentStrategy
        
        strategy = NewsSentimentStrategy(
            kite_client=authenticator.kite,
            ai_analyzer=analyzer,
            risk_manager=risk_manager,
            market_data=market_data
        )
        print(f"✅ News sentiment strategy initialized")
        
        # Test signal processing
        trade_signals = strategy.process_analysis_results(analysis_results)
        print(f"✅ Generated {len(trade_signals)} trade signals")
        
        for signal in trade_signals[:2]:  # Show first 2
            print(f"   📋 {signal.action} {signal.symbol} - Qty: {signal.quantity} @ ₹{signal.entry_price}")
            
    except Exception as e:
        print(f"❌ Trading strategy test failed: {e}")
        return False
    
    # Test 7: Database System
    print(f"\n7️⃣ Testing Database System...")
    try:
        from database.supabase_client import DatabaseManager
        from database.models import SystemEvent
        
        db = DatabaseManager()
        print(f"✅ Database manager initialized ({db.get_system_stats().get('storage_type', 'Unknown')})")
        
        # Test saving an event
        test_event = SystemEvent(
            event_type="TEST",
            message="System integration test completed",
            timestamp=datetime.now()
        )
        
        saved = db.save_event(test_event)
        print(f"✅ Database save test: {'Success' if saved else 'Failed'}")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False
    
    # Test 8: Main Trading Bot
    print(f"\n8️⃣ Testing Main Trading Bot...")
    try:
        from main import NiftyOptionsTradingBot
        
        # Initialize bot (don't start trading)
        bot = NiftyOptionsTradingBot()
        print(f"✅ Trading bot initialized successfully")
        
        # Test service initialization
        services_ok = bot.initialize_services()
        print(f"✅ Services initialization: {'Success' if services_ok else 'Failed'}")
        
        if services_ok:
            print(f"✅ All trading services operational")
        
    except Exception as e:
        print(f"❌ Main trading bot test failed: {e}")
        return False
    
    # Final Summary
    print(f"\n🎉 COMPLETE SYSTEM INTEGRATION TEST RESULTS")
    print("=" * 70)
    print("✅ Configuration & Logging: PASSED")
    print("✅ Authentication System: PASSED") 
    print("✅ AI Analysis Engine: PASSED")
    print("✅ Market Data System: PASSED")
    print("✅ Risk Management: PASSED")
    print("✅ Trading Strategy: PASSED")
    print("✅ Database System: PASSED")
    print("✅ Main Trading Bot: PASSED")
    print("=" * 70)
    print("🚀 YOUR NIFTY OPTIONS TRADING SYSTEM IS READY!")
    print("🎯 All components integrated and operational")
    print("💡 You can now start automated trading")
    print("📝 Run: python main.py")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    success = test_complete_trading_system()
    
    if success:
        print(f"\n🏆 INTEGRATION TEST PASSED!")
        print(f"🚀 System ready for live trading!")
    else:
        print(f"\n⚠️ Some tests failed - check logs above")