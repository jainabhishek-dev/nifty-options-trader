#!/usr/bin/env python3
"""
Find the orphaned BUY order that doesn't have a corresponding position
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_ANON_KEY')
supabase = create_client(supabase_url, supabase_key)

# Get yesterday's date (January 7, 2026)
today = datetime.now().date()
yesterday = today - timedelta(days=1)
yesterday_str = yesterday.strftime('%Y-%m-%d')

print(f"🔍 Finding orphaned BUY order from {yesterday_str}...")
print(f"=" * 80)

# Fetch all BUY orders from yesterday
buy_orders = supabase.table('orders').select('*').gte('created_at', f'{yesterday_str}T00:00:00').lt('created_at', f'{today}T00:00:00').eq('trading_mode', 'paper').eq('order_type', 'BUY').order('created_at').execute()

# Fetch all positions from yesterday
positions = supabase.table('positions').select('*').gte('entry_time', f'{yesterday_str}T00:00:00').lt('entry_time', f'{today}T00:00:00').eq('trading_mode', 'paper').execute()

print(f"\n📊 Total BUY orders: {len(buy_orders.data)}")
print(f"📊 Total positions: {len(positions.data)}")
print(f"📊 Extra BUY orders: {len(buy_orders.data) - len(positions.data)}")

# Get all buy_order_ids from positions
position_buy_order_ids = set()
for pos in positions.data:
    buy_order_id = pos.get('buy_order_id')
    if buy_order_id:
        position_buy_order_ids.add(buy_order_id)

print(f"\n✓ Positions with buy_order_id: {len(position_buy_order_ids)}")

# Find BUY orders without corresponding positions
orphaned_buy_orders = []
for order in buy_orders.data:
    order_id = order['id']
    if order_id not in position_buy_order_ids:
        orphaned_buy_orders.append(order)

print(f"\n❌ Orphaned BUY orders (no position): {len(orphaned_buy_orders)}")
print(f"=" * 80)

if orphaned_buy_orders:
    print(f"\n🔍 ORPHANED BUY ORDER DETAILS:")
    for order in orphaned_buy_orders:
        print(f"\n   Order ID: {order['id']}")
        print(f"   Symbol: {order['symbol']}")
        print(f"   Price: ₹{order['price']}")
        print(f"   Quantity: {order['quantity']}")
        print(f"   Created: {order['created_at']}")
        print(f"   Strategy: {order.get('strategy_name', 'N/A')}")
        print(f"   Status: {order.get('status', 'N/A')}")
        
        # Check if there's any position with this symbol but different buy_order_id
        matching_symbol_positions = [p for p in positions.data if p['symbol'] == order['symbol']]
        if matching_symbol_positions:
            print(f"   ⚠️  Found {len(matching_symbol_positions)} position(s) with same symbol but different buy_order_id:")
            for pos in matching_symbol_positions:
                print(f"      - Position buy_order_id: {pos.get('buy_order_id', 'None')}")
                print(f"        Entry: ₹{pos['average_price']} at {pos['entry_time'][:19]}")
else:
    print(f"\n✅ No orphaned BUY orders found")

# Also check the reverse: positions without matching BUY orders
print(f"\n" + "=" * 80)
print(f"🔍 Checking positions without matching BUY orders...")

buy_order_ids = {o['id'] for o in buy_orders.data}
positions_without_buy = []

for pos in positions.data:
    buy_order_id = pos.get('buy_order_id')
    if buy_order_id and buy_order_id not in buy_order_ids:
        positions_without_buy.append(pos)

if positions_without_buy:
    print(f"\n❌ Positions with invalid buy_order_id: {len(positions_without_buy)}")
    for pos in positions_without_buy:
        print(f"\n   Position: {pos['symbol']}")
        print(f"   Buy Order ID: {pos.get('buy_order_id', 'None')}")
        print(f"   Entry: ₹{pos['average_price']} at {pos['entry_time']}")
else:
    print(f"✅ All positions have valid buy_order_id references")

print(f"\n" + "=" * 80)
