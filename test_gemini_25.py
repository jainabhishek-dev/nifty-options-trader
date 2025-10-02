#!/usr/bin/env python3
"""
Test Gemini 2.5 Flash Model Integration
Quick test to verify the new model works with our trading system
"""

import sys
import time
from intelligence.gemini_client import GeminiNewsAnalyzer

def test_gemini_25_flash():
    """Test Gemini 2.5 Flash model functionality"""
    
    print("🧠 Testing Gemini 2.5 Flash Model Integration")
    print("=" * 60)
    
    try:
        # Initialize the AI engine
        print("1️⃣ Initializing Gemini News Analyzer...")
        engine = GeminiNewsAnalyzer()
        print("✅ Engine initialized successfully")
        
        # Test with Nifty 50 news analysis
        print("\n2️⃣ Testing Nifty 50 news analysis...")
        
        start_time = time.time()
        result = engine.get_nifty50_news_analysis()
        response_time = time.time() - start_time
        
        print(f"✅ Analysis completed in {response_time:.2f} seconds")
        print(f"📊 Generated {len(result)} analysis points")
        
        if result:
            print("\n3️⃣ Sample Analysis Results:")
            for i, analysis in enumerate(result[:3], 1):  # Show first 3
                print(f"   {i}. {analysis.sentiment} - {analysis.action} {analysis.strike_type} (Confidence: {analysis.confidence})")
                print(f"      Reason: {analysis.reason[:80]}...")
        
        # Test model configuration
        print("\n4️⃣ Model Configuration Check:")
        from config.settings import TradingConfig
        print(f"✅ Current Model: {TradingConfig.GEMINI_MODEL}")
        print(f"✅ Temperature: {TradingConfig.TEMPERATURE}")
        
        print("\n" + "=" * 60)
        print("🎉 Gemini 2.5 Flash Model Test: SUCCESS!")
        print("🚀 Your trading system is ready with the latest AI model!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        print("\nDebugging Info:")
        print(f"Error Type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gemini_25_flash()
    sys.exit(0 if success else 1)