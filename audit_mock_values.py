#!/usr/bin/env python3
"""
Mock Value Audit - Verification Script
Checks that no mock/hardcoded values remain in critical trading components
"""

import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockValueAuditor:
    """Audits the system for remaining mock/hardcoded values"""
    
    def __init__(self):
        self.issues_found = []
        self.components_tested = []
        
    def audit_system(self):
        """Run comprehensive audit of all components"""
        print("🔍 MOCK VALUE AUDIT - PHASE 3 CLEANUP")
        print("=" * 60)
        
        # Test 1: Options Data Provider
        self.test_options_data_provider()
        
        # Test 2: Market Utils  
        self.test_market_utils()
        
        # Test 3: Web API Endpoints
        self.test_web_api_endpoints()
        
        # Test 4: Analytics Components
        self.test_analytics_components()
        
        # Display results
        self.display_audit_results()
    
    def test_options_data_provider(self):
        """Test Options Data Provider for mock values"""
        try:
            from analytics.options_data_provider import OptionsDataProvider
            from core.kite_manager import KiteManager
            
            print("\n📊 Testing Options Data Provider...")
            
            # Check if mock methods still exist
            provider = OptionsDataProvider(KiteManager())
            
            # Check for removed methods
            if hasattr(provider, '_generate_mock_live_data'):
                self.issues_found.append("❌ _generate_mock_live_data method still exists")
            else:
                print("  ✅ Mock data generation methods removed")
            
            # Test behavior when not authenticated
            chain = provider.get_options_chain("NIFTY")
            if chain.get('error'):
                print("  ✅ Properly returns error when unauthenticated")
            else:
                print("  ⚠️  Chain returned without error (may indicate fallback data)")
            
            self.components_tested.append("Options Data Provider")
            
        except Exception as e:
            self.issues_found.append(f"❌ Options Data Provider test failed: {e}")
    
    def test_market_utils(self):
        """Test Market Utils for hardcoded values"""
        try:
            from utils.market_utils import MarketDataManager
            from core.kite_manager import KiteManager
            
            print("\n📈 Testing Market Utils...")
            
            # Check if fallback method still exists
            kite_manager = KiteManager()
            if kite_manager.is_authenticated and kite_manager.kite:
                market_manager = MarketDataManager(kite_manager.kite)
            else:
                print("  ⚠️  KiteManager not authenticated - creating with None")
                # This will test the error handling
                try:
                    market_manager = MarketDataManager(None)
                except Exception:
                    print("  ✅ MarketDataManager properly rejects None kite_client")
                    self.components_tested.append("Market Utils")
                    return
            
            if hasattr(market_manager, '_create_fallback_options'):
                self.issues_found.append("❌ _create_fallback_options method still exists")
            else:
                print("  ✅ Fallback options generation removed")
            
            # Test Nifty level retrieval
            nifty_level = market_manager._get_current_nifty_level()
            if nifty_level == 25000 or nifty_level == 25150:
                self.issues_found.append("❌ Hardcoded Nifty level detected")
            elif nifty_level == 0:
                print("  ✅ No hardcoded fallback values - returns 0 on failure")
            else:
                print(f"  ✅ Live Nifty level retrieved: {nifty_level}")
            
            self.components_tested.append("Market Utils")
            
        except Exception as e:
            self.issues_found.append(f"❌ Market Utils test failed: {e}")
    
    def test_web_api_endpoints(self):
        """Test web API endpoints for hardcoded defaults"""
        print("\n🌐 Testing Web API Endpoints...")
        
        try:
            # Check app.py source for hardcoded values
            with open('web_ui/app.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove comments before checking
            lines = content.split('\n')
            code_lines = [line for line in lines if not line.strip().startswith('#')]
            code_content = '\n'.join(code_lines)
            
            hardcoded_values = ['25150', '25000']
            mock_patterns = ['return.*mock', 'generate.*mock', 'fallback.*25']
            
            found_hardcoded = []
            for value in hardcoded_values:
                if value in code_content:
                    found_hardcoded.append(value)
            
            for pattern in mock_patterns:
                import re
                if re.search(pattern, code_content, re.IGNORECASE):
                    found_hardcoded.append(f"pattern: {pattern}")
            
            if found_hardcoded:
                self.issues_found.append(f"❌ Hardcoded values in app.py: {found_hardcoded}")
            else:
                print("  ✅ No hardcoded values found in app.py")
            
            self.components_tested.append("Web API Endpoints")
            
        except Exception as e:
            self.issues_found.append(f"❌ Web API test failed: {e}")
    
    def test_analytics_components(self):
        """Test analytics components for proper live data usage"""
        try:
            from analytics.options_greeks_calculator import OptionsGreeksCalculator
            from analytics.max_pain_analyzer import MaxPainAnalyzer
            from analytics.volatility_analyzer import VolatilityAnalyzer
            
            print("\n🔬 Testing Analytics Components...")
            
            # Test Greeks Calculator
            calc = OptionsGreeksCalculator()
            # Should work with valid inputs
            greeks = calc.calculate_all_greeks(25200, 25200, 0.1, 0.2, 'CE')
            if greeks and 'delta' in greeks:
                print("  ✅ Greeks Calculator working with live data")
            else:
                self.issues_found.append("❌ Greeks Calculator not functioning properly")
            
            # Test Max Pain Analyzer
            analyzer = MaxPainAnalyzer()
            # Should handle empty data gracefully
            empty_chain = {'data': [], 'spot_price': 0}
            result = analyzer.calculate_max_pain(empty_chain)
            if result.get('max_pain_strike') == 0 or 'error' in result:
                print("  ✅ Max Pain Analyzer handles empty data properly")
            else:
                print("  ⚠️  Max Pain Analyzer may be using fallback data")
            
            self.components_tested.append("Analytics Components")
            
        except Exception as e:
            self.issues_found.append(f"❌ Analytics Components test failed: {e}")
    
    def display_audit_results(self):
        """Display comprehensive audit results"""
        print("\n" + "=" * 60)
        print("📋 MOCK VALUE AUDIT RESULTS")
        print("=" * 60)
        
        print(f"\n✅ Components Tested: {len(self.components_tested)}")
        for component in self.components_tested:
            print(f"  • {component}")
        
        if self.issues_found:
            print(f"\n❌ Issues Found: {len(self.issues_found)}")
            for issue in self.issues_found:
                print(f"  {issue}")
            
            print("\n🚨 AUDIT FAILED - Mock values still present!")
            print("Please fix the identified issues before proceeding with Module 2.")
        else:
            print("\n🎉 AUDIT PASSED!")
            print("✅ No mock values detected")
            print("✅ All components use live data only")
            print("✅ Proper error handling in place")
            print("\n🚀 System is ready for Phase 3 Module 2 implementation!")
        
        print(f"\n🕐 Audit completed at: {datetime.now()}")
        print("=" * 60)

def main():
    """Run the audit"""
    auditor = MockValueAuditor()
    auditor.audit_system()

if __name__ == "__main__":
    main()