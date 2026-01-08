#!/usr/bin/env python3
"""
Check yesterday's orders and positions for data consistency
Verify that each position has corresponding BUY and SELL orders
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

print(f"=" * 80)
print(f"CHECKING DATA CONSISTENCY FOR: {yesterday_str}")
print(f"=" * 80)

# Fetch all orders from yesterday
print(f"\n📋 Fetching orders from {yesterday_str}...")
orders_result = supabase.table('orders').select('*').gte('created_at', f'{yesterday_str}T00:00:00').lt('created_at', f'{today}T00:00:00').eq('trading_mode', 'paper').order('created_at').execute()

orders = orders_result.data
print(f"   Total orders: {len(orders)}")

# Separate BUY and SELL orders
buy_orders = [o for o in orders if o['order_type'] == 'BUY']
sell_orders = [o for o in orders if o['order_type'] == 'SELL']

print(f"   - BUY orders: {len(buy_orders)}")
print(f"   - SELL orders: {len(sell_orders)}")

# Fetch all positions from yesterday
print(f"\n📊 Fetching positions from {yesterday_str}...")
positions_result = supabase.table('positions').select('*').gte('entry_time', f'{yesterday_str}T00:00:00').lt('entry_time', f'{today}T00:00:00').eq('trading_mode', 'paper').order('entry_time').execute()

positions = positions_result.data
print(f"   Total positions: {len(positions)}")

# Separate open and closed positions
open_positions = [p for p in positions if p['is_open']]
closed_positions = [p for p in positions if not p['is_open']]

print(f"   - Open positions: {len(open_positions)}")
print(f"   - Closed positions: {len(closed_positions)}")

# Check the relationship: Expected = 10 positions : 20 orders (1 BUY + 1 SELL per position)
print(f"\n" + "=" * 80)
print(f"CONSISTENCY CHECK")
print(f"=" * 80)

print(f"\n✓ Expected: {len(positions)} positions should have {len(positions) * 2} orders (1 BUY + 1 SELL each)")
print(f"✓ Actual: {len(positions)} positions with {len(orders)} total orders")

if len(orders) == len(positions) * 2:
    print(f"   ✅ ORDER COUNT MATCHES EXPECTED!")
else:
    print(f"   ❌ ORDER COUNT MISMATCH!")
    print(f"      Expected: {len(positions) * 2} orders")
    print(f"      Actual: {len(orders)} orders")
    print(f"      Difference: {len(orders) - (len(positions) * 2)}")

# Check if BUY and SELL counts match
print(f"\n✓ BUY vs SELL balance:")
if len(buy_orders) == len(sell_orders):
    print(f"   ✅ BALANCED: {len(buy_orders)} BUY = {len(sell_orders)} SELL")
else:
    print(f"   ❌ IMBALANCED!")
    print(f"      BUY orders: {len(buy_orders)}")
    print(f"      SELL orders: {len(sell_orders)}")
    print(f"      Difference: {abs(len(buy_orders) - len(sell_orders))}")

# Check if closed positions match SELL orders
print(f"\n✓ Closed positions vs SELL orders:")
if len(closed_positions) == len(sell_orders):
    print(f"   ✅ MATCHED: {len(closed_positions)} closed positions = {len(sell_orders)} SELL orders")
else:
    print(f"   ⚠️  MISMATCH!")
    print(f"      Closed positions: {len(closed_positions)}")
    print(f"      SELL orders: {len(sell_orders)}")

# Detailed position-order relationship check
print(f"\n" + "=" * 80)
print(f"DETAILED POSITION-ORDER LINKING")
print(f"=" * 80)

issues_found = 0
positions_with_buy_order = 0
positions_with_sell_order = 0
positions_missing_buy = []
positions_missing_sell = []

for i, pos in enumerate(positions, 1):
    print(f"\n[Position {i}] {pos['symbol']}")
    print(f"   Entry: ₹{pos['average_price']} at {pos['entry_time'][:19]}")
    print(f"   Status: {'OPEN' if pos['is_open'] else 'CLOSED'}")
    print(f"   Quantity: {pos['quantity']}")
    
    # Check for BUY order (using buy_order_id)
    buy_order_id = pos.get('buy_order_id')
    if buy_order_id:
        # Verify BUY order exists
        matching_buy = [o for o in buy_orders if o['id'] == buy_order_id]
        if matching_buy:
            positions_with_buy_order += 1
            print(f"   ✅ BUY order linked: {buy_order_id[:8]}... (₹{matching_buy[0]['price']})")
        else:
            print(f"   ❌ BUY order ID exists but order NOT FOUND: {buy_order_id}")
            positions_missing_buy.append(pos['symbol'])
            issues_found += 1
    else:
        print(f"   ❌ NO BUY ORDER ID!")
        positions_missing_buy.append(pos['symbol'])
        issues_found += 1
    
    # Check for SELL order (if position is closed)
    if not pos['is_open']:
        sell_order_id = pos.get('sell_order_id')
        if sell_order_id:
            matching_sell = [o for o in sell_orders if o['id'] == sell_order_id]
            if matching_sell:
                positions_with_sell_order += 1
                print(f"   ✅ SELL order linked: {sell_order_id[:8]}... (₹{matching_sell[0]['price']})")
            else:
                print(f"   ❌ SELL order ID exists but order NOT FOUND: {sell_order_id}")
                positions_missing_sell.append(pos['symbol'])
                issues_found += 1
        else:
            # Try to find SELL order by symbol match
            matching_sells = [o for o in sell_orders if o['symbol'] == pos['symbol']]
            if matching_sells:
                print(f"   ⚠️  SELL order exists but NOT LINKED (found by symbol match)")
                print(f"      Found {len(matching_sells)} SELL order(s) for {pos['symbol']}")
                issues_found += 1
            else:
                print(f"   ❌ NO SELL ORDER FOUND for closed position!")
                positions_missing_sell.append(pos['symbol'])
                issues_found += 1

# Summary
print(f"\n" + "=" * 80)
print(f"SUMMARY")
print(f"=" * 80)

print(f"\n📊 Positions with linked orders:")
print(f"   - With BUY order: {positions_with_buy_order}/{len(positions)} ({positions_with_buy_order/len(positions)*100:.1f}%)")
print(f"   - With SELL order: {positions_with_sell_order}/{len(closed_positions)} closed positions")

print(f"\n🔍 Data Quality:")
if issues_found == 0:
    print(f"   ✅ PERFECT! All positions have proper order linkage")
else:
    print(f"   ❌ Issues found: {issues_found}")
    if positions_missing_buy:
        print(f"\n   Positions missing BUY orders:")
        for sym in positions_missing_buy:
            print(f"      - {sym}")
    if positions_missing_sell:
        print(f"\n   Closed positions missing SELL orders:")
        for sym in positions_missing_sell:
            print(f"      - {sym}")

print(f"\n✓ Expected relationship: {len(positions)} positions = {len(buy_orders)} BUY + {len(sell_orders)} SELL orders")
print(f"✓ Verification: {len(positions)} positions × 2 = {len(positions) * 2} expected orders")
print(f"✓ Actual: {len(orders)} orders found")

if len(orders) == len(positions) * 2 and len(buy_orders) == len(sell_orders) and issues_found == 0:
    print(f"\n🎉 DATA INTEGRITY: EXCELLENT!")
elif issues_found == 0 and len(buy_orders) == len(closed_positions):
    print(f"\n✅ DATA INTEGRITY: GOOD (some positions still open)")
else:
    print(f"\n⚠️  DATA INTEGRITY: NEEDS ATTENTION")

print(f"\n" + "=" * 80)
