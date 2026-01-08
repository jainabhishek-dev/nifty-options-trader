"""
Test order save retry logic
Simulates network failures and verifies retry mechanism works correctly
"""
import os
import sys
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import httpx

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database_manager import DatabaseManager

def test_order_save_with_retry():
    """Test that order save retries on transient network errors"""
    
    print("=" * 80)
    print("TEST 1: Order Save with Transient Network Error (Should Retry & Succeed)")
    print("=" * 80)
    
    db = DatabaseManager()
    
    # Mock the supabase table insert to fail once, then succeed
    call_count = 0
    
    def mock_execute_side_effect():
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # First attempt: simulate ConnectionTerminated error
            print(f"\n📍 Attempt {call_count}: Simulating ConnectionTerminated error...")
            raise httpx.RemoteProtocolError("Connection terminated")
        else:
            # Second attempt: succeed
            print(f"\n📍 Attempt {call_count}: Connection restored, insert succeeds...")
            mock_result = Mock()
            mock_result.data = [{'id': 'test-order-id-123'}]
            return mock_result
    
    mock_execute = Mock(side_effect=mock_execute_side_effect)
    mock_insert = Mock()
    mock_insert.return_value.execute = mock_execute
    
    order_data = {
        'strategy_name': 'scalping',
        'trading_mode': 'paper',
        'symbol': 'NIFTY2610626300CE',
        'order_type': 'BUY',
        'quantity': 65,
        'price': 65.25
    }
    
    start_time = time.time()
    
    with patch.object(db.supabase, 'table') as mock_table:
        mock_table.return_value.insert = mock_insert
        
        result = db.save_order(order_data)
        elapsed = time.time() - start_time
    
    print(f"\n✅ Result: {'SUCCESS' if result else 'FAILED'}")
    print(f"📊 Order ID returned: {result}")
    print(f"🔄 Total attempts: {call_count}")
    print(f"⏱️  Time elapsed: {elapsed:.2f}s (should be ~0.5s for 1 retry)")
    
    if result and call_count == 2 and elapsed >= 0.4:
        print("✅ TEST PASSED: Order saved after retry with proper delay")
    else:
        print("❌ TEST FAILED")
    
    print("\n" + "=" * 80)
    return result is not None and call_count == 2


def test_order_save_exhausted_retries():
    """Test that order save returns None after all retries exhausted"""
    
    print("\nTEST 2: Order Save with Persistent Error (Should Fail After 3 Retries)")
    print("=" * 80)
    
    db = DatabaseManager()
    
    call_count = 0
    
    def mock_insert_persistent_error(data):
        nonlocal call_count
        call_count += 1
        print(f"\n📍 Attempt {call_count}: Simulating persistent network error...")
        raise httpx.NetworkError("Network unreachable")
    
    mock_insert = Mock(side_effect=mock_insert_persistent_error)
    
    order_data = {
        'strategy_name': 'scalping',
        'trading_mode': 'paper',
        'symbol': 'NIFTY2610626300CE',
        'order_type': 'SELL',
        'quantity': 65,
        'price': 65.25
    }
    
    # Mock position check to pass validation
    mock_position_result = Mock()
    mock_position_result.data = [{'quantity': 65}]
    
    start_time = time.time()
    
    with patch.object(db.supabase, 'table') as mock_table:
        def table_side_effect(table_name):
            if table_name == 'positions':
                mock_pos = Mock()
                mock_pos.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = mock_position_result
                return mock_pos
            else:  # orders table
                mock_orders = Mock()
                mock_orders.insert = mock_insert
                return mock_orders
        
        mock_table.side_effect = table_side_effect
        
        result = db.save_order(order_data)
        elapsed = time.time() - start_time
    
    print(f"\n✅ Result: {'SUCCESS' if result else 'FAILED (Expected)'}")
    print(f"📊 Order ID returned: {result}")
    print(f"🔄 Total attempts: {call_count}")
    print(f"⏱️  Time elapsed: {elapsed:.2f}s (should be ~1.5s for retries with 0.5s + 1.0s delays)")
    
    if result is None and call_count == 3 and elapsed >= 1.4:
        print("✅ TEST PASSED: Order save failed after 3 retries with proper delays")
    else:
        print("❌ TEST FAILED")
    
    print("\n" + "=" * 80)
    return result is None and call_count == 3


def test_order_save_non_retryable_error():
    """Test that non-retryable errors don't trigger retry"""
    
    print("\nTEST 3: Order Save with Non-Retryable Error (Should Fail Immediately)")
    print("=" * 80)
    
    db = DatabaseManager()
    
    call_count = 0
    
    def mock_insert_data_error(data):
        nonlocal call_count
        call_count += 1
        print(f"\n📍 Attempt {call_count}: Simulating data validation error...")
        raise ValueError("Invalid data format")
    
    mock_insert = Mock(side_effect=mock_insert_data_error)
    
    order_data = {
        'strategy_name': 'scalping',
        'trading_mode': 'paper',
        'symbol': 'NIFTY2610626300CE',
        'order_type': 'BUY',
        'quantity': 65,
        'price': 65.25
    }
    
    start_time = time.time()
    
    with patch.object(db.supabase, 'table') as mock_table:
        mock_table.return_value.insert = mock_insert
        
        result = db.save_order(order_data)
        elapsed = time.time() - start_time
    
    print(f"\n✅ Result: {'SUCCESS' if result else 'FAILED (Expected)'}")
    print(f"📊 Order ID returned: {result}")
    print(f"🔄 Total attempts: {call_count}")
    print(f"⏱️  Time elapsed: {elapsed:.2f}s (should be <0.1s, no retry)")
    
    if result is None and call_count == 1 and elapsed < 0.5:
        print("✅ TEST PASSED: Non-retryable error failed immediately without retry")
    else:
        print("❌ TEST FAILED")
    
    print("\n" + "=" * 80)
    return result is None and call_count == 1


def test_order_save_validation_failure():
    """Test that validation failures return None without attempting save"""
    
    print("\nTEST 4: Order Save with Missing Required Fields (Should Fail Validation)")
    print("=" * 80)
    
    db = DatabaseManager()
    
    # Missing 'symbol' field
    order_data = {
        'strategy_name': 'scalping',
        'trading_mode': 'paper',
        'order_type': 'BUY',
        'quantity': 65,
        'price': 65.25
    }
    
    print("\n📍 Testing order with missing 'symbol' field...")
    
    result = db.save_order(order_data)
    
    print(f"\n✅ Result: {'SUCCESS' if result else 'FAILED (Expected)'}")
    print(f"📊 Order ID returned: {result}")
    
    if result is None:
        print("✅ TEST PASSED: Validation caught missing field")
    else:
        print("❌ TEST FAILED: Validation should have failed")
    
    print("\n" + "=" * 80)
    return result is None


def test_exponential_backoff():
    """Test that retry delays follow exponential backoff pattern"""
    
    print("\nTEST 5: Verify Exponential Backoff Timing")
    print("=" * 80)
    
    db = DatabaseManager()
    
    attempt_times = []
    
    def mock_insert_with_timing(data):
        attempt_times.append(time.time())
        print(f"\n📍 Attempt {len(attempt_times)}: {time.time():.2f}")
        raise httpx.ConnectError("Connection refused")
    
    mock_insert = Mock(side_effect=mock_insert_with_timing)
    
    order_data = {
        'strategy_name': 'scalping',
        'trading_mode': 'paper',
        'symbol': 'NIFTY2610626300CE',
        'order_type': 'BUY',
        'quantity': 65,
        'price': 65.25
    }
    
    with patch.object(db.supabase, 'table') as mock_table:
        mock_table.return_value.insert = mock_insert
        
        result = db.save_order(order_data)
    
    # Verify delays
    if len(attempt_times) >= 3:
        delay1 = attempt_times[1] - attempt_times[0]
        delay2 = attempt_times[2] - attempt_times[1]
        
        print(f"\n📊 Delay between attempt 1 and 2: {delay1:.2f}s (expected ~0.5s)")
        print(f"📊 Delay between attempt 2 and 3: {delay2:.2f}s (expected ~1.0s)")
        
        if 0.4 <= delay1 <= 0.7 and 0.9 <= delay2 <= 1.3:
            print("✅ TEST PASSED: Exponential backoff working correctly")
            return True
        else:
            print("❌ TEST FAILED: Delays don't match expected pattern")
            return False
    else:
        print("❌ TEST FAILED: Not enough attempts recorded")
        return False


def run_all_tests():
    """Run all tests and report results"""
    
    print("\n" + "=" * 80)
    print("ORDER SAVE RETRY LOGIC - COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    tests = [
        ("Retry on Transient Error", test_order_save_with_retry),
        ("Exhaust All Retries", test_order_save_exhausted_retries),
        ("Non-Retryable Error", test_order_save_non_retryable_error),
        ("Validation Failure", test_order_save_validation_failure),
        ("Exponential Backoff", test_exponential_backoff),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ TEST EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 80)
    print(f"TOTAL: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("🎉 ALL TESTS PASSED - Retry logic working correctly!")
    else:
        print("⚠️ SOME TESTS FAILED - Review implementation")
    
    print("=" * 80)
    
    return passed_count == total_count


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
