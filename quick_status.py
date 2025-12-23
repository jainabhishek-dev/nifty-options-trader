#!/usr/bin/env python3
"""
Quick status check
"""

from core.database_manager import DatabaseManager
from datetime import datetime
import pytz

db = DatabaseManager()
today = datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d')

orders = db.supabase.table('orders').select('*').gte('created_at', f'{today}T00:00:00').execute()
positions = db.supabase.table('positions').select('*').gte('created_at', f'{today}T00:00:00').execute()

print(f'📊 LIVE STATUS CHECK')
print(f'Orders today: {len(orders.data)}')
print(f'Positions today: {len(positions.data)}')

if orders.data:
    print('\n🔥 RECENT ORDERS:')
    for order in orders.data:
        order_type = order["order_type"]
        symbol = order["symbol"] 
        price = order["price"]
        time = order["created_at"]
        print(f'  {order_type} {symbol} @ ₹{price} ({time})')

if positions.data:
    print('\n🎯 RECENT POSITIONS:')
    for pos in positions.data:
        symbol = pos["symbol"]
        entry_price = pos["average_price"]
        buy_order_id = pos.get('buy_order_id', 'N/A')
        if buy_order_id != 'N/A':
            buy_order_short = buy_order_id[:8] + '...'
        else:
            buy_order_short = 'N/A'
        print(f'  {symbol} Entry:₹{entry_price} Order:{buy_order_short}')
else:
    print('\n❌ NO POSITIONS CREATED!')
    print('This violates 1 BUY order = 1 position requirement!')

if len(orders.data) > 0 and len(positions.data) == 0:
    print('\n🚨 CRITICAL ISSUE DETECTED:')
    print(f'- {len(orders.data)} BUY orders exist')
    print('- 0 positions created')
    print('- Position creation is failing in real-time!')