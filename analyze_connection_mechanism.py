#!/usr/bin/env python3
"""
Analyze how orders and positions are connected in the current system
Understand why we have a BUY order without a position
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client
import json

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY')
supabase = create_client(supabase_url, supabase_key)

# Get yesterday's date
today = datetime.now().date()
yesterday = today - timedelta(days=1)
yesterday_str = yesterday.strftime('%Y-%m-%d')

print("=" * 80)
print(f"HOW ORDERS AND POSITIONS ARE CONNECTED - Analysis for {yesterday_str}")
print("=" * 80)

# Fetch all orders and positions from yesterday
orders = supabase.table('orders').select('*').gte('created_at', f'{yesterday_str}T00:00:00').lt('created_at', f'{today}T00:00:00').eq('trading_mode', 'paper').order('created_at').execute()

positions = supabase.table('positions').select('*').gte('entry_time', f'{yesterday_str}T00:00:00').lt('entry_time', f'{today}T00:00:00').eq('trading_mode', 'paper').order('entry_time').execute()

buy_orders = [o for o in orders.data if o['order_type'] == 'BUY']
sell_orders = [o for o in orders.data if o['order_type'] == 'SELL']

print(f"\n📊 DATA SUMMARY:")
print(f"   Total orders: {len(orders.data)} (BUY: {len(buy_orders)}, SELL: {len(sell_orders)})")
print(f"   Total positions: {len(positions.data)}")

# CRITICAL ANALYSIS: How are they connected?
print(f"\n" + "=" * 80)
print(f"🔗 CONNECTION MECHANISM ANALYSIS")
print(f"=" * 80)

print(f"\n1. POSITIONS → ORDERS (via buy_order_id and sell_order_id):")
print(f"   -----------------------------------------------------------")

# Check each position's order links
for i, pos in enumerate(positions.data[:5], 1):  # Show first 5 for brevity
    print(f"\n   Position {i}: {pos['symbol']}")
    print(f"   - Position ID: {pos['id']}")
    print(f"   - Entry: ₹{pos['average_price']} at {pos['entry_time'][:19]}")
    
    # Check BUY order link
    buy_order_id = pos.get('buy_order_id')
    if buy_order_id:
        buy_order = next((o for o in buy_orders if o['id'] == buy_order_id), None)
        if buy_order:
            print(f"   ✅ BUY order linked: {buy_order_id[:8]}... (₹{buy_order['price']})")
        else:
            print(f"   ❌ BUY order ID exists but order NOT FOUND: {buy_order_id}")
    else:
        print(f"   ❌ NO buy_order_id!")
    
    # Check SELL order link
    if not pos['is_open']:
        sell_order_id = pos.get('sell_order_id')
        if sell_order_id:
            sell_order = next((o for o in sell_orders if o['id'] == sell_order_id), None)
            if sell_order:
                print(f"   ✅ SELL order linked: {sell_order_id[:8]}... (₹{sell_order['price']})")
            else:
                print(f"   ❌ SELL order ID exists but order NOT FOUND: {sell_order_id}")

# REVERSE CHECK: Orders → Positions
print(f"\n\n2. ORDERS → POSITIONS (reverse lookup):")
print(f"   ---------------------------------------")

# For each BUY order, check if there's a position
buy_orders_with_positions = 0
buy_orders_without_positions = []

for order in buy_orders:
    order_id = order['id']
    # Find position with this buy_order_id
    linked_position = next((p for p in positions.data if p.get('buy_order_id') == order_id), None)
    
    if linked_position:
        buy_orders_with_positions += 1
    else:
        buy_orders_without_positions.append(order)

print(f"\n   BUY orders with positions: {buy_orders_with_positions}/{len(buy_orders)}")
print(f"   BUY orders WITHOUT positions: {len(buy_orders_without_positions)}")

if buy_orders_without_positions:
    print(f"\n   ⚠️  ORPHANED BUY ORDERS (no position):")
    for order in buy_orders_without_positions:
        print(f"\n   Order ID: {order['id']}")
        print(f"   Symbol: {order['symbol']}")
        print(f"   Price: ₹{order['price']}")
        print(f"   Time: {order['created_at']}")
        print(f"   Internal order_id: {order.get('order_id', 'N/A')}")

# CODE ANALYSIS: How position.buy_order_id gets set
print(f"\n" + "=" * 80)
print(f"📝 CODE MECHANISM FOR LINKING")
print(f"=" * 80)

print(f"""
CURRENT CODE FLOW (virtual_order_executor.py):
-----------------------------------------------

STEP 1: BUY Order Created and Saved
   Line 300-340: place_order() creates VirtualOrder with order_id
   Line 485:     order_data['order_id'] = order_id  # Internal UUID
   Line 500:     saved_order_id = save_order(order_data)
                 # Returns database PRIMARY KEY (orders.id)
   Line 514:     order.metadata['database_id'] = saved_order_id
                 # ⚠️  Stored in MEMORY only!

STEP 2: Position Created
   Line 568:     _update_position(order, trade)
   Line 596:     _create_new_position(order, trade)
   Line 632:     database_order_id = order.metadata.get('database_id')
                 # ⚠️  Reads from MEMORY - can be None!
   Line 633-634: if not database_order_id:
                     raise Exception("Cannot create position...")
   
   Line 647:     position_data = {{
                     'buy_order_id': database_order_id  # ← CRITICAL!
                 }}
   Line 653:     position_id = save_position(position_data)

THE CONNECTION:
---------------
positions.buy_order_id = orders.id (PRIMARY KEY)

This is set at line 647 using order.metadata['database_id']
If metadata['database_id'] is None, position creation fails!

WHY ORPHANED ORDER EXISTS:
--------------------------
1. Order saved successfully → orders.id = "659e74cc-..."
2. order.metadata['database_id'] set in memory
3. BUT something caused metadata to be None when read at line 632
4. Exception raised: "Cannot create position without database order ID"
5. Exception caught at line 664: print(f"Error creating new position: {{e}}")
6. Execution continues without creating position
7. Result: BUY order exists, but NO position created

EXPECTED FLOW (when working correctly):
---------------------------------------
1. BUY order created → orders.id = "659e74cc-..."
2. Position created with buy_order_id = "659e74cc-..."
3. SELL order created → orders.id = "a003a444-..."
4. Position updated with sell_order_id = "a003a444-..."
5. Result: 1 position linked to 2 orders (BUY + SELL)

WHAT WENT WRONG:
---------------
Step 2 failed → No position created
Step 3-4 never happened → No SELL order
Result: 1 orphaned BUY order, no position
""")

print("=" * 80)
print("RECOMMENDATION FOR DEPLOY LOGS:")
print("=" * 80)
print(f"""
Look for these specific log messages around 2026-01-07T07:24:46 IST:

✓ Success messages (should be present):
   - "🔄 Attempting to save order: BUY NIFTY2611326100CE"
   - "✅ Order SUCCESSFULLY saved to DB"
   - "🔄 Proceeding to position management for verified order"

❌ Failure messages (what we're looking for):
   - "❌ CRITICAL ERROR: No database ID found for order"
   - "Cannot create position without database order ID"
   - "Error creating new position: [exception message]"
   - "Error updating position: [exception message]"

These messages will tell us EXACTLY why position creation failed.
""")

print("=" * 80)
