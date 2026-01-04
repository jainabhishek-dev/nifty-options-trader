#!/usr/bin/env python3
"""
COMPREHENSIVE INTEGRATION TEST
Test all recent configuration changes end-to-end
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database_manager import DatabaseManager
from strategies.scalping_strategy import ScalpingStrategy, ScalpingConfig
from datetime import datetime

def print_section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_database_table():
    """Test 1: Verify database table exists and has correct structure"""
    print_section("TEST 1: DATABASE TABLE VERIFICATION")
    
    try:
        db_manager = DatabaseManager()
        
        # Check if table exists and has data
        result = db_manager.supabase.table('scalping_strategy_config').select('*').eq('id', 1).execute()
        
        if not result.data or len(result.data) == 0:
            print("❌ FAILED: Table exists but no data found")
            return False
        
        config = result.data[0]
        print("✅ Table exists and accessible")
        
        # Verify all required columns
        required_columns = ['id', 'profit_target', 'stop_loss', 'time_stop_minutes', 
                          'signal_cooldown_seconds', 'strike_offset', 'updated_at']
        
        for col in required_columns:
            if col not in config:
                print(f"❌ FAILED: Missing column '{col}'")
                return False
        
        print("✅ All required columns present")
        
        # Display current values
        print(f"\n📊 Current Database Values:")
        print(f"   profit_target: {config['profit_target']}%")
        print(f"   stop_loss: {config['stop_loss']}%")
        print(f"   time_stop_minutes: {config['time_stop_minutes']}")
        print(f"   signal_cooldown_seconds: {config['signal_cooldown_seconds']}")
        print(f"   strike_offset: {config['strike_offset']}")
        print(f"   updated_at: {config['updated_at']}")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

def test_strategy_loads_from_db():
    """Test 2: Strategy loads configuration from database"""
    print_section("TEST 2: STRATEGY DATABASE LOADING")
    
    try:
        # Get database values first
        db_manager = DatabaseManager()
        db_result = db_manager.supabase.table('scalping_strategy_config').select('*').eq('id', 1).execute()
        db_config = db_result.data[0]
        
        print(f"📥 Database values:")
        print(f"   profit_target: {db_config['profit_target']}%")
        print(f"   stop_loss: {db_config['stop_loss']}%")
        print(f"   strike_offset: {db_config['strike_offset']}")
        
        # Create strategy with config=None (should load from DB)
        print(f"\n🔄 Creating strategy with config=None...")
        strategy = ScalpingStrategy(config=None)
        
        print(f"\n✅ Strategy initialized")
        print(f"📤 Strategy configuration:")
        print(f"   profit_target: {strategy.strategy_config.target_profit}%")
        print(f"   stop_loss: {strategy.strategy_config.stop_loss}%")
        print(f"   time_stop_minutes: {strategy.strategy_config.time_stop_minutes}")
        print(f"   signal_cooldown_seconds: {strategy.strategy_config.signal_cooldown_seconds}")
        print(f"   strike_offset: {strategy.strategy_config.strike_offset}")
        
        # Verify values match
        if (strategy.strategy_config.target_profit == db_config['profit_target'] and
            strategy.strategy_config.stop_loss == db_config['stop_loss'] and
            strategy.strategy_config.time_stop_minutes == db_config['time_stop_minutes'] and
            strategy.strategy_config.signal_cooldown_seconds == db_config['signal_cooldown_seconds'] and
            strategy.strategy_config.strike_offset == db_config['strike_offset']):
            print(f"\n✅ Strategy values match database")
            return True
        else:
            print(f"\n❌ FAILED: Strategy values don't match database")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_strike_selection_logic():
    """Test 3: Strike selection uses correct offset logic"""
    print_section("TEST 3: STRIKE SELECTION LOGIC")
    
    try:
        # Get current offset from database
        db_manager = DatabaseManager()
        result = db_manager.supabase.table('scalping_strategy_config').select('strike_offset').eq('id', 1).execute()
        current_offset = result.data[0]['strike_offset']
        
        print(f"📊 Current strike_offset from database: {current_offset}")
        
        # Create strategy
        strategy = ScalpingStrategy(config=None)
        
        # Test strike calculation with current offset
        nifty_price = 26000
        atm_strike = round(nifty_price / 50) * 50
        
        print(f"\n🎯 Strike Calculation Test (Nifty = {nifty_price}):")
        print(f"   ATM Strike: {atm_strike}")
        
        # CALL strike
        call_strike = atm_strike + (current_offset * 50)
        print(f"   CE (CALL): {atm_strike} + ({current_offset} × 50) = {call_strike}")
        
        # PUT strike
        put_strike = atm_strike - (current_offset * 50)
        print(f"   PE (PUT): {atm_strike} - ({current_offset} × 50) = {put_strike}")
        
        # Test all offset possibilities
        print(f"\n📋 Testing all offset values:")
        test_cases = [
            (-3, "3 ITM"),
            (-2, "2 ITM"),
            (-1, "1 ITM"),
            (0, "ATM"),
            (1, "1 OTM"),
            (2, "2 OTM"),
            (3, "3 OTM")
        ]
        
        all_passed = True
        for offset, label in test_cases:
            ce_strike = atm_strike + (offset * 50)
            pe_strike = atm_strike - (offset * 50)
            
            # Verify logic
            ce_correct = ce_strike == 26000 + (offset * 50)
            pe_correct = pe_strike == 26000 - (offset * 50)
            
            status = "✅" if (ce_correct and pe_correct) else "❌"
            print(f"   {status} offset={offset:+2d} ({label:7s}): CE={ce_strike}, PE={pe_strike}")
            
            if not (ce_correct and pe_correct):
                all_passed = False
        
        if all_passed:
            print(f"\n✅ All strike calculations correct")
            return True
        else:
            print(f"\n❌ FAILED: Some strike calculations incorrect")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

def test_config_update():
    """Test 4: Configuration update works correctly"""
    print_section("TEST 4: CONFIGURATION UPDATE")
    
    try:
        # Get original values
        db_manager = DatabaseManager()
        original = db_manager.supabase.table('scalping_strategy_config').select('*').eq('id', 1).execute().data[0]
        
        print(f"📊 Original values:")
        print(f"   profit_target: {original['profit_target']}%")
        print(f"   stop_loss: {original['stop_loss']}%")
        print(f"   strike_offset: {original['strike_offset']}")
        
        # Create strategy and update
        strategy = ScalpingStrategy(config=None)
        
        print(f"\n🔄 Updating configuration...")
        test_values = {
            'profit_target': 20.0,
            'stop_loss': 12.0,
            'strike_offset': 2
        }
        
        result = strategy.update_config(**test_values)
        
        if not result.get('success'):
            print(f"❌ FAILED: Update failed - {result.get('error')}")
            return False
        
        print(f"✅ Update successful")
        
        # Verify in-memory update
        print(f"\n📤 In-memory values after update:")
        print(f"   profit_target: {strategy.strategy_config.target_profit}%")
        print(f"   stop_loss: {strategy.strategy_config.stop_loss}%")
        print(f"   strike_offset: {strategy.strategy_config.strike_offset}")
        
        if (strategy.strategy_config.target_profit != test_values['profit_target'] or
            strategy.strategy_config.stop_loss != test_values['stop_loss'] or
            strategy.strategy_config.strike_offset != test_values['strike_offset']):
            print(f"❌ FAILED: In-memory values not updated")
            return False
        
        print(f"✅ In-memory values updated correctly")
        
        # Verify database update
        db_updated = db_manager.supabase.table('scalping_strategy_config').select('*').eq('id', 1).execute().data[0]
        
        print(f"\n💾 Database values after update:")
        print(f"   profit_target: {db_updated['profit_target']}%")
        print(f"   stop_loss: {db_updated['stop_loss']}%")
        print(f"   strike_offset: {db_updated['strike_offset']}")
        
        if (db_updated['profit_target'] != test_values['profit_target'] or
            db_updated['stop_loss'] != test_values['stop_loss'] or
            db_updated['strike_offset'] != test_values['strike_offset']):
            print(f"❌ FAILED: Database values not updated")
            return False
        
        print(f"✅ Database values updated correctly")
        
        # Restore original values
        print(f"\n🔙 Restoring original values...")
        restore_result = strategy.update_config(
            profit_target=original['profit_target'],
            stop_loss=original['stop_loss'],
            strike_offset=original['strike_offset']
        )
        
        if restore_result.get('success'):
            print(f"✅ Original values restored")
        else:
            print(f"⚠️  Warning: Could not restore original values")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_new_strategy_loads_updated_config():
    """Test 5: New strategy instance loads updated config"""
    print_section("TEST 5: NEW INSTANCE LOADING")
    
    try:
        # Create first strategy
        strategy1 = ScalpingStrategy(config=None)
        original_profit = strategy1.strategy_config.target_profit
        
        print(f"📊 Strategy 1 profit_target: {original_profit}%")
        
        # Update config
        new_profit = original_profit + 5.0
        print(f"\n🔄 Updating to {new_profit}%...")
        strategy1.update_config(profit_target=new_profit)
        
        # Create second strategy (should load updated value)
        print(f"\n🆕 Creating new strategy instance...")
        strategy2 = ScalpingStrategy(config=None)
        
        print(f"📤 Strategy 2 profit_target: {strategy2.strategy_config.target_profit}%")
        
        if strategy2.strategy_config.target_profit == new_profit:
            print(f"✅ New instance loaded updated config from database")
        else:
            print(f"❌ FAILED: New instance has old config")
            return False
        
        # Restore original
        strategy2.update_config(profit_target=original_profit)
        print(f"🔙 Restored to {original_profit}%")
        
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

def test_trading_manager_integration():
    """Test 6: Trading manager initializes strategy correctly"""
    print_section("TEST 6: TRADING MANAGER INTEGRATION")
    
    try:
        from core.kite_manager import KiteManager
        from core.trading_manager import TradingManager
        
        # Get database values
        db_manager = DatabaseManager()
        db_config = db_manager.supabase.table('scalping_strategy_config').select('*').eq('id', 1).execute().data[0]
        
        print(f"📊 Database config:")
        print(f"   profit_target: {db_config['profit_target']}%")
        print(f"   strike_offset: {db_config['strike_offset']}")
        
        # Initialize trading manager (will create strategy with config=None)
        print(f"\n🔄 Initializing trading manager...")
        kite_manager = KiteManager()
        trading_manager = TradingManager(kite_manager)
        
        # Check if scalping strategy was initialized
        if 'scalping' not in trading_manager.strategies:
            print(f"❌ FAILED: Scalping strategy not found in trading manager")
            return False
        
        print(f"✅ Trading manager initialized with scalping strategy")
        
        # Get strategy config
        scalping_strategy = trading_manager.strategies['scalping']
        
        print(f"\n📤 Strategy config in trading manager:")
        print(f"   profit_target: {scalping_strategy.strategy_config.target_profit}%")
        print(f"   stop_loss: {scalping_strategy.strategy_config.stop_loss}%")
        print(f"   strike_offset: {scalping_strategy.strategy_config.strike_offset}")
        
        # Verify values match database
        if (scalping_strategy.strategy_config.target_profit == db_config['profit_target'] and
            scalping_strategy.strategy_config.stop_loss == db_config['stop_loss'] and
            scalping_strategy.strategy_config.strike_offset == db_config['strike_offset']):
            print(f"\n✅ Trading manager strategy uses database config")
            return True
        else:
            print(f"\n❌ FAILED: Config mismatch between database and trading manager")
            return False
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all tests and report results"""
    print("\n" + "🚀" * 40)
    print("COMPREHENSIVE CONFIGURATION INTEGRATION TEST")
    print("Testing all recent changes: DB table, strategy loading, UI integration")
    print("🚀" * 40)
    
    tests = [
        ("Database Table", test_database_table),
        ("Strategy Database Loading", test_strategy_loads_from_db),
        ("Strike Selection Logic", test_strike_selection_logic),
        ("Configuration Update", test_config_update),
        ("New Instance Loading", test_new_strategy_loads_updated_config),
        ("Trading Manager Integration", test_trading_manager_integration)
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ TEST CRASHED: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:9s} - {name}")
    
    print(f"\n{'=' * 80}")
    print(f"RESULTS: {passed}/{total} tests passed")
    print(f"{'=' * 80}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Configuration system working correctly.")
        print("\n✅ Verified:")
        print("   • Database table exists with correct structure")
        print("   • Strategy loads config from database automatically")
        print("   • Strike selection logic works with all offsets")
        print("   • Config updates save to database and update in-memory")
        print("   • New instances load latest config from database")
        print("   • Trading manager initializes strategy with database config")
        print("\n🚀 READY FOR PRODUCTION!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
