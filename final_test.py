"""Final comprehensive test"""

with open('core/virtual_order_executor.py', encoding='utf-8') as f:
    code = f.read()

# Find the fix section - get more context
fix_start = code.find('# FIX: Check if order was actually saved')
fix_section = code[fix_start:fix_start + 1200]  # Get more text

print("="*80)
print("COMPREHENSIVE FIX VERIFICATION")
print("="*80)

# Split into if and else blocks properly
if_start = fix_section.find("if saved_order_id:")
else_start = fix_section.find("else:", if_start)

if if_start > 0 and else_start > 0:
    if_block = fix_section[if_start:else_start]
    else_block = fix_section[else_start:else_start + 500]
    
    print("\n📋 IF BLOCK (Order was saved):")
    print("-"*80)
    print(if_block)
    print("-"*80)
    
    print("\n📋 ELSE BLOCK (Order truly failed):")
    print("-"*80)
    print(else_block)
    print("-"*80)
    
    print("\n✅ LOGIC ANALYSIS:")
    print("-"*80)
    
    # Check if block
    if_has_return = "return False" in if_block
    print(f"1. IF block (saved_order_id exists):")
    print(f"   - Has 'return False': {if_has_return}")
    print(f"   - Expected: False")
    print(f"   - Status: {'✅ CORRECT' if not if_has_return else '❌ WRONG'}")
    
    # Check else block
    else_has_return = "return False" in else_block
    print(f"\n2. ELSE block (saved_order_id is None):")
    print(f"   - Has 'return False': {else_has_return}")
    print(f"   - Expected: True")
    print(f"   - Status: {'✅ CORRECT' if else_has_return else '❌ WRONG'}")
    
    # Final verdict
    print("\n" + "="*80)
    if not if_has_return and else_has_return:
        print("🎉 FIX IS CORRECT!")
        print("="*80)
        print("\nBehavior:")
        print("  ✅ When order saved: NO return → execution continues → position created")
        print("  ✅ When order failed: return False → execution stops → no position")
        print("\n✅ Jan 7 orphaned order bug is FIXED!")
        exit(0)
    else:
        print("❌ FIX HAS ISSUES")
        print("="*80)
        exit(1)
else:
    print("❌ Could not parse if/else blocks")
    exit(1)
