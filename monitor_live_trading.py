#!/usr/bin/env python3
"""
30-Minute Live Market Testing - Comprehensive Monitoring
"""

import time
from datetime import datetime, timedelta
import pytz
from core.database_manager import DatabaseManager

def monitor_trading_activity():
    """Monitor trading activity for 30 minutes"""
    
    db = DatabaseManager()
    ist = pytz.timezone('Asia/Kolkata')
    
    start_time = datetime.now(ist)
    end_time = start_time + timedelta(minutes=30)
    today = start_time.strftime('%Y-%m-%d')
    
    print(f'🚀 LIVE MARKET MONITORING STARTED')
    print(f'Start: {start_time.strftime("%H:%M:%S")} IST')
    print(f'End:   {end_time.strftime("%H:%M:%S")} IST')
    print('=' * 60)
    
    last_order_count = 0
    last_position_count = 0
    check_interval = 30  # Check every 30 seconds
    check_count = 0
    
    while datetime.now(ist) < end_time:
        check_count += 1
        current_time = datetime.now(ist)
        remaining = end_time - current_time
        
        # Get current database state
        orders_today = db.supabase.table('orders').select('*').gte('created_at', f'{today}T00:00:00').execute()
        positions_today = db.supabase.table('positions').select('*').gte('created_at', f'{today}T00:00:00').execute()
        open_positions = db.supabase.table('positions').select('*').eq('is_open', True).execute()
        
        current_order_count = len(orders_today.data)
        current_position_count = len(positions_today.data)
        current_open_count = len(open_positions.data)
        
        # Check for new activity
        new_orders = current_order_count - last_order_count
        new_positions = current_position_count - last_position_count
        
        print(f'⏰ Check #{check_count} - {current_time.strftime("%H:%M:%S")} IST (Remaining: {str(remaining).split(".")[0]})')
        print(f'   📊 Orders: {current_order_count} (+{new_orders}) | Positions: {current_position_count} (+{new_positions}) | Open: {current_open_count}')
        
        # Report any new activity
        if new_orders > 0:
            print(f'   🔥 NEW ORDERS DETECTED: {new_orders}')
            # Get the latest orders
            latest_orders = sorted(orders_today.data, key=lambda x: x['created_at'], reverse=True)[:new_orders]
            for order in latest_orders:
                order_type = order['order_type']
                symbol = order['symbol']
                price = order['price']
                qty = order['quantity']
                strategy = order['strategy_name']
                order_id = order['id'][:8] + '...'
                print(f'      • {order_type} {symbol} @ ₹{price} (Qty:{qty}) | Strategy:{strategy} | ID:{order_id}')
        
        if new_positions > 0:
            print(f'   🎯 NEW POSITIONS CREATED: {new_positions}')
            # Get the latest positions
            latest_positions = sorted(positions_today.data, key=lambda x: x['created_at'], reverse=True)[:new_positions]
            for pos in latest_positions:
                symbol = pos['symbol']
                entry_price = pos['average_price'] 
                qty = pos['quantity']
                strategy = pos['strategy_name']
                buy_order = pos.get('buy_order_id', 'N/A')
                pos_id = pos['id'][:8] + '...'
                buy_order_short = buy_order[:8] + '...' if buy_order != 'N/A' else 'N/A'
                print(f'      • {symbol} Entry:₹{entry_price} (Qty:{qty}) | Strategy:{strategy} | Pos:{pos_id} | Order:{buy_order_short}')
        
        # Check for position closures
        if current_open_count < len([p for p in positions_today.data if p['is_open']]):
            print(f'   💰 POSITION CLOSURE DETECTED')
            
        # Validate data integrity 
        buy_orders = [o for o in orders_today.data if o['order_type'] == 'BUY']
        sell_orders = [o for o in orders_today.data if o['order_type'] == 'SELL']
        
        if len(buy_orders) > 0 or len(sell_orders) > 0:
            print(f'   🔍 Integrity: BUY({len(buy_orders)}) | SELL({len(sell_orders)}) | Pos({current_position_count})')
            
            # Check 1:1 relationship
            positions_with_buy_order = [p for p in positions_today.data if p.get('buy_order_id')]
            if len(positions_with_buy_order) == len(buy_orders):
                print(f'   ✅ 1 BUY order = 1 position relationship maintained')
            elif len(buy_orders) > 0:
                print(f'   ⚠️ Relationship check: {len(buy_orders)} BUY orders, {len(positions_with_buy_order)} positions with buy_order_id')
        
        last_order_count = current_order_count
        last_position_count = current_position_count
        
        print()  # Empty line for readability
        
        # Wait for next check
        time.sleep(check_interval)
    
    # Final summary
    final_time = datetime.now(ist)
    print('🏁 TESTING COMPLETE')
    print(f'Duration: {final_time - start_time}')
    print(f'Final State: {current_order_count} orders, {current_position_count} positions, {current_open_count} open')
    
    return {
        'orders': current_order_count,
        'positions': current_position_count, 
        'open_positions': current_open_count,
        'duration': final_time - start_time
    }

if __name__ == "__main__":
    try:
        results = monitor_trading_activity()
        print(f'\n📊 TEST RESULTS: {results}')
    except KeyboardInterrupt:
        print('\n⏹️ Monitoring stopped by user')
    except Exception as e:
        print(f'\n❌ Monitoring error: {e}')