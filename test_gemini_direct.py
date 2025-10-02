# test_gemini_direct.py
"""
Direct test of gemini_client.py using its built-in test method
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_gemini_client_direct():
    """Test gemini_client.py directly using its built-in test method"""
    print("🧪 Testing gemini_client.py directly...")
    print("=" * 60)
    
    try:
        from intelligence.gemini_client import GeminiNewsAnalyzer
        
        # Initialize the analyzer
        print("\n📡 Initializing Gemini client...")
        analyzer = GeminiNewsAnalyzer()
        
        # Use the built-in test method
        print("\n🔄 Running built-in test_analysis_system()...")
        test_result = analyzer.test_analysis_system()
        
        if test_result:
            print("\n🎉 Direct test completed successfully!")
            print("✅ gemini_client.py is working properly")
        else:
            print("\n❌ Direct test failed!")
            print("⚠️ Check the logs above for details")
            
        return test_result
        
    except Exception as e:
        print(f"\n❌ Failed to test gemini_client.py: {e}")
        return False

if __name__ == "__main__":
    success = test_gemini_client_direct()
    
    if success:
        print(f"\n🚀 gemini_client.py is ready for production use!")
    else:
        print(f"\n🔧 gemini_client.py needs attention before use")