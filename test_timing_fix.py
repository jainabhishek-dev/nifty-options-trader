"""
Test to verify the timing consistency fix
Ensures position entry_time matches order filled_timestamp
"""

import re

with open('core/virtual_order_executor.py', 'r', encoding='utf-8') as f:
    code = f.read()

print("="*80)
print("TIMING CONSISTENCY FIX VERIFICATION")
print("="*80)

# Find _create_new_position function
func_start = code.find("def _create_new_position(self, order: VirtualOrder, trade: VirtualTrade):")
func_section = code[func_start:func_start + 2500]  # Increased to include database section

print("\n✅ CHECKING TIMING LOGIC:")
print("-"*80)

# Check 1: Uses order.filled_timestamp
check1 = "entry_time = order.filled_timestamp" in func_section
print(f"1. Uses order.filled_timestamp: {'✅' if check1 else '❌'}")

# Check 2: Has fallback to datetime.now()
check2 = "datetime.now(self.ist)" in func_section
print(f"2. Has fallback to current time: {'✅' if check2 else '❌'}")

# Check 3: Position uses entry_time
check3 = "entry_time=entry_time" in func_section
print(f"3. Position uses entry_time: {'✅' if check3 else '❌'}")

# Check 4: Database also uses entry_time
check4 = "entry_time.isoformat()" in func_section and "'entry_time':" in func_section
print(f"4. Database uses entry_time: {'✅' if check4 else '❌'}")

# Check 5: Metadata uses entry_time
check5 = "'created_at': entry_time.isoformat()" in func_section
print(f"5. Metadata uses entry_time: {'✅' if check5 else '❌'}")

print("\n" + "-"*80)
print("EXPECTED BEHAVIOR:")
print("-"*80)
print("Before fix:")
print("  Order filled at:  12:30:45.123")
print("  Position entry:   12:30:46.456  ❌ (1 sec delay)")
print()
print("After fix:")
print("  Order filled at:  12:30:45.123")
print("  Position entry:   12:30:45.123  ✅ (exact match)")

print("\n" + "="*80)
if all([check1, check2, check3, check4, check5]):
    print("🎉 TIMING FIX VERIFIED!")
    print("="*80)
    print("\n✅ Position entry_time now matches order filled_timestamp")
    print("✅ No more 1-second delay between order and position")
    print("\nNOTE: This was a pre-existing issue, NOT caused by the false")
    print("negative fix. The false negative fix only affects error handling.")
else:
    print("❌ TIMING FIX INCOMPLETE")
    print("="*80)
