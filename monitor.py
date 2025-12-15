import sys
import json
sys.path.append('.')
from core.database_manager import DatabaseManager

print("=== SYSTEM MONITORING ===")
print(f"Time: {__import__('datetime').datetime.now().strftime('%H:%M:%S')}")

# Check database
db = DatabaseManager()
orders = db.get_orders(limit=10)
positions = db.get_positions()

print(f"\nORDERS: {len(orders) if orders else 0}")
if orders:
    for o in orders[-5:]:
        action = o.get('order_type', 'Unknown')
        symbol = o.get('symbol', 'Unknown')
        qty = o.get('quantity', 0)
        price = o.get('price', 0)
        status = o.get('status', 'Unknown')
        print(f"  {action} {symbol} Qty:{qty} Price:{price} Status:{status}")
        print(f"    ID: {o.get('id', 'N/A')[:8]}... Time: {str(o.get('created_at', 'N/A'))[:19]}")

print(f"\nPOSITIONS: {len(positions) if positions else 0}")
if positions:
    for p in positions[-3:]:
        status = "OPEN" if p['is_open'] else "CLOSED"
        print(f"  {p['symbol']} Qty:{p['quantity']} Entry:{p['average_price']} Status:{status}")
        if not p['is_open']:
            print(f"    Exit:{p.get('exit_price', 'N/A')} Reason:{p.get('exit_reason', 'N/A')}")

# Check actual strategies (not the outdated JSON file)
print(f"\nSTRATEGIES STATUS:")
try:
    import web_ui.app as web_app
    if hasattr(web_app, 'trading_manager') and web_app.trading_manager:
        tm = web_app.trading_manager
        available_strategies = list(tm.strategies.keys()) if hasattr(tm, 'strategies') else []
        active_strategies = tm.active_strategies if hasattr(tm, 'active_strategies') else []
        
        print(f"  Available: {available_strategies}")
        print(f"  Active: {active_strategies if active_strategies else 'NONE'}")
        
        if not active_strategies:
            print(f"  ❌ No strategies are active!")
            print(f"  💡 To activate: Use web UI or call trading_manager.start_strategies(['scalping', 'supertrend'])")
    else:
        print(f"  ❌ Trading manager not initialized")
except Exception as e:
    print(f"  Error checking strategies: {e}")

# Check if market is open (basic check)
from datetime import datetime, time
now = datetime.now().time()
market_open = time(9, 15)
market_close = time(15, 30)
is_market_time = market_open <= now <= market_close
print(f"\nMARKET STATUS: {'OPEN' if is_market_time else 'CLOSED'} (Basic check)")

print("\n" + "="*50)