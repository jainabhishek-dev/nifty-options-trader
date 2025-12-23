#!/usr/bin/env python3
"""
Simple database monitoring for live testing
"""

from core.database_manager import DatabaseManager
from datetime import datetime, timedelta
import pytz
import time

def simple_monitor():
    db = DatabaseManager()
    ist = pytz.timezone('Asia/Kolkata')
    start_time = datetime.now(ist)
    
    print(f'📊 LIVE TESTING MONITOR')
    print(f'Start Time: {start_time.strftime("%H:%M:%S")} IST')
    print('Monitoring database for trading activity...')
    print('Press Ctrl+C to stop')
    print('=' * 50)
    
    last_orders = 0
    last_positions = 0
    check_count = 0
    
    try:
        while True:
            check_count += 1
            current_time = datetime.now(ist)
            today = current_time.strftime('%Y-%m-%d')
            
            # Check database
            orders = db.supabase.table('orders').select('*').gte('created_at', f'{today}T00:00:00').execute()
            positions = db.supabase.table('positions').select('*').gte('created_at', f'{today}T00:00:00').execute()
            open_pos = db.supabase.table('positions').select('*').eq('is_open', True).execute()
            
            current_orders = len(orders.data)
            current_positions = len(positions.data)
            current_open = len(open_pos.data)
            
            # Check for changes
            new_orders = current_orders - last_orders
            new_positions = current_positions - last_positions
            
            status_line = f'[{current_time.strftime("%H:%M:%S")}] Orders: {current_orders} | Positions: {current_positions} | Open: {current_open}'
            
            if new_orders > 0 or new_positions > 0:
                print(f'🔥 {status_line} (+{new_orders} orders, +{new_positions} positions)')
                
                # Show details of new activity
                if new_orders > 0:
                    latest_orders = sorted(orders.data, key=lambda x: x['created_at'], reverse=True)[:new_orders]
                    for order in latest_orders:
                        print(f'   📋 {order["order_type"]} {order["symbol"]} @ ₹{order["price"]} (Strategy: {order["strategy_name"]})')
                        
                if new_positions > 0:
                    latest_positions = sorted(positions.data, key=lambda x: x['created_at'], reverse=True)[:new_positions]
                    for pos in latest_positions:
                        buy_order_id = pos.get('buy_order_id', 'N/A')[:8] if pos.get('buy_order_id') else 'N/A'
                        print(f'   🎯 Position: {pos["symbol"]} Entry:₹{pos["average_price"]} (Buy Order: {buy_order_id}...)')
                        
            elif check_count % 10 == 0:  # Show status every 10 checks (5 minutes)
                elapsed = current_time - start_time
                print(f'⏱️ {status_line} (Elapsed: {str(elapsed).split(".")[0]})')
            
            last_orders = current_orders
            last_positions = current_positions
            
            time.sleep(30)  # Check every 30 seconds
            
    except KeyboardInterrupt:
        end_time = datetime.now(ist)
        duration = end_time - start_time
        print(f'\n📊 TESTING SUMMARY:')
        print(f'Duration: {str(duration).split(".")[0]}')
        print(f'Final: {current_orders} orders, {current_positions} positions, {current_open} open')
        
        if current_orders > 0:
            print('✅ Trading activity detected!')
        else:
            print('⚠️ No trading activity observed')

if __name__ == "__main__":
    simple_monitor()