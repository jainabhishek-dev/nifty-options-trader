#!/usr/bin/env python3
"""
Check if the orphaned BUY order has the database_id in signal_data
This is CRITICAL for position creation
"""

import os
from dotenv import load_dotenv
from supabase import create_client
import json

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY')
supabase = create_client(supabase_url, supabase_key)

# The orphaned order ID
orphaned_order_id = '659e74cc-610f-4bb6-ab0c-6e5b7f09d1ee'

print("=" * 80)
print("CHECKING ORPHANED ORDER METADATA")
print("=" * 80)

# Fetch the orphaned order
result = supabase.table('orders').select('*').eq('id', orphaned_order_id).execute()

if result.data:
    order = result.data[0]
    print(f"\n✓ Found order: {order['symbol']}")
    print(f"  Order Type: {order['order_type']}")
    print(f"  Price: ₹{order['price']}")
    print(f"  Created: {order['created_at']}")
    print(f"  Status: {order['status']}")
    
    # Check signal_data for database_id
    signal_data = order.get('signal_data')
    
    print(f"\n🔍 Signal Data Analysis:")
    if signal_data:
        print(f"  Signal data exists: YES")
        print(f"  Full signal_data: {json.dumps(signal_data, indent=2)}")
        
        # Check for database_id (this is what position creation needs!)
        if 'database_id' in signal_data:
            print(f"\n  ✅ database_id found: {signal_data['database_id']}")
            print(f"     This should have been used to create position!")
        else:
            print(f"\n  ❌ CRITICAL: database_id is MISSING!")
            print(f"     This explains why position creation failed!")
            print(f"     Code at line 632: order.metadata.get('database_id')")
            print(f"     Would have returned None, causing position creation to fail")
    else:
        print(f"  Signal data exists: NO")
        print(f"  ❌ This is suspicious - signal_data should always exist")
    
    # Check if order_id field exists
    print(f"\n  Order ID (internal): {order.get('order_id', 'N/A')}")
    print(f"  Order ID (database): {order['id']}")
    
    print(f"\n" + "=" * 80)
    print("ROOT CAUSE HYPOTHESIS:")
    print("=" * 80)
    
    if signal_data and 'database_id' not in signal_data:
        print("""
❌ CONFIRMED ROOT CAUSE:
   
   The order was saved to database successfully, but the database_id was
   NOT stored in order.metadata['database_id'] before position creation.
   
   CODE FLOW:
   1. Order saved: Line 500 - save_order() returns saved_order_id ✅
   2. Database ID stored: Line 514 - order.metadata['database_id'] = saved_order_id ✅
   3. BUT: This metadata is NOT saved back to database! ❌
   4. Position creation: Line 632 - order.metadata.get('database_id') returns None ❌
   5. Exception raised: "Cannot create position without database order ID" ❌
   6. Exception caught and swallowed: Line 664 ❌
   7. Result: Order exists, but no position created ❌
   
   SOLUTION NEEDED:
   - Store database_id in signal_data when order is saved
   - OR: Use order['id'] directly instead of metadata['database_id']
   - AND: Don't swallow exceptions silently!
        """)
    else:
        print("""
✓ Database ID exists in signal_data.
  Need Railway logs to determine why position creation still failed.
        """)
    
else:
    print(f"\n❌ Order not found: {orphaned_order_id}")

print("\n" + "=" * 80)
