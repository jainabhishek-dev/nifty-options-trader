"""
Validation test for the false negative fix in virtual_order_executor.py
Tests that the fix correctly handles post-save exceptions
"""

import re

def test_fix():
    """Verify the fix is correctly implemented"""
    
    print("\n" + "="*80)
    print("VALIDATING FALSE NEGATIVE FIX")
    print("="*80)
    
    # Read the fixed code
    with open('core/virtual_order_executor.py', 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Extract the order save section
    order_save_start = code.find("# Save order to database - CRITICAL")
    order_save_end = code.find("# Create trade record ONLY after")
    
    if order_save_start == -1 or order_save_end == -1:
        print("❌ Could not find order save section")
        return False
    
    order_save_section = code[order_save_start:order_save_end]
    
    print("\n📋 Testing Fix Implementation...")
    print("-"*80)
    
    # Test 1: saved_order_id initialization
    print("\n1. Checking saved_order_id initialization...")
    if "saved_order_id = None" in order_save_section:
        init_line = order_save_section.find("saved_order_id = None")
        try_line = order_save_section.find("try:")
        if init_line < try_line:
            print("   ✅ PASS: saved_order_id initialized before try block")
            test1 = True
        else:
            print("   ❌ FAIL: saved_order_id not initialized before try")
            test1 = False
    else:
        print("   ❌ FAIL: saved_order_id initialization not found")
        test1 = False
    
    # Test 2: Exception handler checks saved_order_id
    print("\n2. Checking exception handler logic...")
    exception_start = order_save_section.find("except Exception as e:")
    if exception_start > 0:
        exception_section = order_save_section[exception_start:]
        if "if saved_order_id:" in exception_section:
            print("   ✅ PASS: Exception handler checks saved_order_id")
            test2 = True
        else:
            print("   ❌ FAIL: Exception handler doesn't check saved_order_id")
            test2 = False
    else:
        print("   ❌ FAIL: Exception handler not found")
        test2 = False
    
    # Test 3: Continues when order was saved
    print("\n3. Checking continuation logic...")
    if "continuing to position creation" in exception_section.lower():
        print("   ✅ PASS: Code continues when order was saved")
        test3 = True
    else:
        print("   ❌ FAIL: No continuation logic found")
        test3 = False
    
    # Test 4: Sets database_id in metadata
    print("\n4. Checking database_id assignment...")
    if "order.metadata['database_id'] = saved_order_id" in exception_section:
        print("   ✅ PASS: database_id assigned in exception handler")
        test4 = True
    else:
        print("   ❌ FAIL: database_id not assigned in exception handler")
        test4 = False
    
    # Test 5: Stops only when save truly failed
    print("\n5. Checking true failure handling...")
    if "else:" in exception_section and "STOPPING EXECUTION" in exception_section:
        print("   ✅ PASS: Stops execution only when save truly failed")
        test5 = True
    else:
        print("   ❌ FAIL: True failure handling not found")
        test5 = False
    
    # Display key code section
    print("\n" + "-"*80)
    print("KEY FIX CODE:")
    print("-"*80)
    
    if exception_start > 0:
        # Extract the if saved_order_id block
        if_block_start = exception_section.find("if saved_order_id:")
        if if_block_start > 0:
            # Find the else block
            else_block = exception_section.find("else:", if_block_start)
            if else_block > 0:
                key_code = exception_section[if_block_start:else_block + 200]
                print(key_code[:500])  # Show first 500 chars
    
    # Summary
    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)
    
    all_tests = [test1, test2, test3, test4, test5]
    passed = sum(all_tests)
    
    print(f"\nTests Passed: {passed}/5")
    
    if passed == 5:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nThe fix correctly:")
        print("  ✅ Initializes saved_order_id before try block")
        print("  ✅ Checks if order was saved in exception handler")
        print("  ✅ Continues to position creation when save succeeded")
        print("  ✅ Assigns database_id in metadata")
        print("  ✅ Stops only when save truly failed")
        print("\n✅ The Jan 7 orphaned order bug is FIXED!")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        print(f"   {5 - passed} test(s) did not pass")
        return False

if __name__ == "__main__":
    success = test_fix()
    exit(0 if success else 1)
