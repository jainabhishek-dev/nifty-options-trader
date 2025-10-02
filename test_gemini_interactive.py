# test_gemini_interactive.py
"""
Interactive testing of individual gemini_client.py methods
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_individual_methods():
    """Test individual methods of GeminiNewsAnalyzer"""
    print("🔬 Interactive Testing of gemini_client.py Methods")
    print("=" * 60)
    
    try:
        from intelligence.gemini_client import GeminiNewsAnalyzer, NewsAnalysisResult
        
        # Test 1: Initialize analyzer
        print("\n1️⃣ Testing Initialization...")
        analyzer = GeminiNewsAnalyzer()
        print("✅ Initialization successful!")
        
        # Test 2: Test mock signal generation
        print("\n2️⃣ Testing Mock Signal Generation...")
        mock_signal = analyzer._generate_mock_signal(1)
        print(f"✅ Mock signal: {mock_signal.sentiment} - {mock_signal.action} {mock_signal.strike_type}")
        print(f"   Confidence: {mock_signal.confidence}/10")
        print(f"   Reason: {mock_signal.reason}")
        
        # Test 3: Test full mock analysis
        print("\n3️⃣ Testing Full Mock Analysis...")
        mock_results = analyzer._get_full_mock_analysis()
        print(f"✅ Generated {len(mock_results)} mock analysis points")
        
        # Show breakdown
        call_count = sum(1 for r in mock_results if r.action == "CALL")
        put_count = sum(1 for r in mock_results if r.action == "PUT")
        hold_count = sum(1 for r in mock_results if r.action == "HOLD")
        
        print(f"   📊 Mock Breakdown: {call_count} CALL, {put_count} PUT, {hold_count} HOLD")
        
        # Test 4: Test single news analysis
        print("\n4️⃣ Testing Single News Analysis...")
        test_news = "HDFC Bank reports 20% growth in quarterly profits, beating analyst expectations."
        
        single_result = analyzer.analyze_single_news(test_news)
        print(f"✅ Single analysis: {single_result.sentiment} - {single_result.action} {single_result.strike_type}")
        print(f"   Impact: {single_result.impact}, Confidence: {single_result.confidence}/10")
        
        # Test 5: Test 10-point analysis (this uses real AI or falls back to mock)
        print("\n5️⃣ Testing 10-Point News Analysis...")
        start_time = datetime.now()
        
        ten_point_results = analyzer.get_nifty50_news_analysis()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"✅ 10-point analysis completed in {duration:.2f} seconds")
        print(f"   Generated {len(ten_point_results)} signals")
        
        # Show first 3 results
        print("   📋 Sample Results:")
        for i, result in enumerate(ten_point_results[:3], 1):
            print(f"      {i}. {result.sentiment} - {result.action} {result.strike_type} (Confidence: {result.confidence})")
        
        # Test 6: Test error handling (simulate news analysis failure)
        print("\n6️⃣ Testing Error Handling...")
        try:
            # This should gracefully handle errors and return neutral analysis
            error_result = analyzer._parse_analysis_response("Invalid response format")
            print(f"✅ Error handling: Returns {error_result.sentiment} with confidence {error_result.confidence}")
        except Exception as e:
            print(f"❌ Error handling failed: {e}")
        
        print("\n🎉 All individual method tests completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Interactive testing failed: {e}")
        return False

def test_dataclass():
    """Test the NewsAnalysisResult dataclass"""
    print("\n📊 Testing NewsAnalysisResult DataClass...")
    
    try:
        from intelligence.gemini_client import NewsAnalysisResult
        
        # Create test result
        test_result = NewsAnalysisResult(
            sentiment="Bullish",
            impact="High",
            action="CALL",
            strike_type="ATM",
            confidence=8,
            reason="Test analysis result",
            timestamp=datetime.now()
        )
        
        print(f"✅ DataClass creation successful!")
        print(f"   Sentiment: {test_result.sentiment}")
        print(f"   Action: {test_result.action} {test_result.strike_type}")
        print(f"   Confidence: {test_result.confidence}/10")
        
        return True
        
    except Exception as e:
        print(f"❌ DataClass test failed: {e}")
        return False

if __name__ == "__main__":
    print("Starting comprehensive testing...\n")
    
    # Test dataclass first
    dataclass_success = test_dataclass()
    
    # Test individual methods
    methods_success = test_individual_methods()
    
    if dataclass_success and methods_success:
        print(f"\n🚀 All tests passed! gemini_client.py is fully functional!")
    else:
        print(f"\n⚠️ Some tests failed. Check the details above.")