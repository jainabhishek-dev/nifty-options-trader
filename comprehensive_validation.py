import sys
sys.path.insert(0, 'c:/Users/Archi/Projects/nifty_options_trader')

from core.database_manager import DatabaseManager
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
db = DatabaseManager()

print("=" * 80)
print("COMPREHENSIVE POST-FIX VALIDATION")
print("=" * 80)

# Get today's date
today = datetime.now(IST).date()

# Get all orders from today
all_orders = db.supabase.table('orders').select('*').order('created_at', desc=False).execute()
today_orders = []

for order in all_orders.data:
    created_at = datetime.fromisoformat(order['created_at'].replace('Z', '+00:00')).astimezone(IST)
    if created_at.date() == today:
        order['created_at_ist'] = created_at
        today_orders.append(order)

print(f"\n📝 TODAY'S ORDERS: {len(today_orders)} total")
print("-" * 80)

buy_orders = [o for o in today_orders if o.get('side') == 'BUY']
sell_orders = [o for o in today_orders if o.get('side') == 'SELL']

print(f"BUY orders: {len(buy_orders)}")
print(f"SELL orders: {len(sell_orders)}")

if len(buy_orders) != len(sell_orders):
    print(f"⚠️  WARNING: Mismatch! {len(buy_orders) - len(sell_orders)} positions may be open")

# Get all positions from today
all_positions = db.supabase.table('positions').select('*').order('entry_time', desc=False).execute()
today_positions = []

for pos in all_positions.data:
    entry_time = datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00')).astimezone(IST)
    if entry_time.date() == today:
        pos['entry_time_ist'] = entry_time
        if not pos['is_open'] and pos.get('exit_time'):
            exit_time = datetime.fromisoformat(pos['exit_time'].replace('Z', '+00:00')).astimezone(IST)
            pos['exit_time_ist'] = exit_time
        today_positions.append(pos)

print(f"\n📊 TODAY'S POSITIONS: {len(today_positions)} total")
print("-" * 80)

open_positions = [p for p in today_positions if p['is_open']]
closed_positions = [p for p in today_positions if not p['is_open']]

print(f"OPEN positions: {len(open_positions)}")
print(f"CLOSED positions: {len(closed_positions)}")

# Detailed validation
print("\n" + "=" * 80)
print("DETAILED VALIDATION")
print("=" * 80)

issues_found = 0
total_tests = 0

# Test 1: Check each position has correct order links
print("\n🔍 TEST 1: Position-Order Linking")
print("-" * 80)
for pos in today_positions:
    total_tests += 1
    symbol = pos['symbol']
    buy_order_id = pos.get('buy_order_id')
    sell_order_id = pos.get('sell_order_id')
    is_open = pos['is_open']
    
    if not buy_order_id:
        print(f"❌ {symbol}: Missing buy_order_id")
        issues_found += 1
    
    if not is_open and not sell_order_id:
        print(f"❌ {symbol}: CLOSED but missing sell_order_id")
        issues_found += 1
    
    if is_open and sell_order_id:
        print(f"❌ {symbol}: OPEN but has sell_order_id (should be closed)")
        issues_found += 1

if issues_found == 0:
    print(f"✅ All {len(today_positions)} positions have correct order links")

# Test 2: Check closed positions have quantity=0
print("\n🔍 TEST 2: Closed Positions Quantity")
print("-" * 80)
qty_issues = 0
for pos in closed_positions:
    total_tests += 1
    if pos.get('quantity', 0) != 0:
        print(f"❌ {pos['symbol']}: Closed but quantity = {pos['quantity']} (should be 0)")
        qty_issues += 1
        issues_found += 1

if qty_issues == 0:
    print(f"✅ All {len(closed_positions)} closed positions have quantity=0")

# Test 3: Check P&L calculations
print("\n🔍 TEST 3: P&L Calculations")
print("-" * 80)
pnl_issues = 0
for pos in closed_positions:
    total_tests += 1
    entry = pos.get('average_price', 0)
    exit_p = pos.get('exit_price', 0)
    qty = pos.get('original_quantity', 75)  # Default to 75 if not stored
    
    # Find the original quantity from orders if needed
    if 'original_quantity' not in pos:
        buy_order = next((o for o in buy_orders if o['id'] == pos.get('buy_order_id')), None)
        if buy_order:
            qty = buy_order.get('filled_quantity', 75)
    
    expected_pnl = (exit_p - entry) * qty
    stored_pnl = pos.get('realized_pnl', 0)
    
    if abs(expected_pnl - stored_pnl) > 0.01:
        print(f"❌ {pos['symbol']}: P&L mismatch")
        print(f"   Expected: ₹{expected_pnl:.2f}, Stored: ₹{stored_pnl:.2f}")
        pnl_issues += 1
        issues_found += 1

if pnl_issues == 0:
    print(f"✅ All {len(closed_positions)} closed positions have correct P&L")

# Test 4: Check P&L% format (should be decimal, not percentage)
print("\n🔍 TEST 4: P&L% Storage Format")
print("-" * 80)
pnl_pct_issues = 0
for pos in closed_positions:
    total_tests += 1
    pnl_percent = pos.get('pnl_percent', 0)
    
    # P&L% should be stored as decimal (between -1 and 1 typically)
    # If it's > 10 or < -10, it's likely stored as percentage instead of decimal
    if abs(pnl_percent) > 10:
        print(f"❌ {pos['symbol']}: P&L% = {pnl_percent} (should be decimal, not percentage)")
        pnl_pct_issues += 1
        issues_found += 1
    else:
        # Verify it matches calculated value
        entry = pos.get('average_price', 0)
        exit_p = pos.get('exit_price', 0)
        if entry > 0:
            expected_pct = (exit_p - entry) / entry
            if abs(expected_pct - pnl_percent) > 0.001:
                print(f"❌ {pos['symbol']}: P&L% mismatch")
                print(f"   Expected: {expected_pct:.4f}, Stored: {pnl_percent:.4f}")
                pnl_pct_issues += 1
                issues_found += 1

if pnl_pct_issues == 0:
    print(f"✅ All {len(closed_positions)} closed positions have correct P&L% format")

# Test 5: Check no orphaned positions (open with SELL orders)
print("\n🔍 TEST 5: Orphaned Positions Check")
print("-" * 80)
orphaned = 0
for pos in open_positions:
    total_tests += 1
    # Check if there's a SELL order for this symbol
    symbol_sell_orders = [o for o in sell_orders if o['symbol'] == pos['symbol']]
    if symbol_sell_orders:
        print(f"❌ {pos['symbol']}: OPEN but has SELL order(s)")
        for so in symbol_sell_orders:
            print(f"   SELL at ₹{so['price']:.2f} - {so['created_at_ist'].strftime('%H:%M:%S')}")
        orphaned += 1
        issues_found += 1

if orphaned == 0:
    print(f"✅ No orphaned positions (all with SELL orders are closed)")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total Tests: {total_tests}")
print(f"Issues Found: {issues_found}")
print(f"Success Rate: {((total_tests - issues_found) / total_tests * 100) if total_tests > 0 else 0:.1f}%")

# Trading statistics
print(f"\n📊 TRADING STATISTICS:")
print("-" * 80)
total_pnl = sum(p.get('realized_pnl', 0) for p in closed_positions)
winning_trades = len([p for p in closed_positions if p.get('realized_pnl', 0) > 0])
losing_trades = len([p for p in closed_positions if p.get('realized_pnl', 0) < 0])

print(f"Total Closed Positions: {len(closed_positions)}")
print(f"Open Positions: {len(open_positions)}")
print(f"Winning Trades: {winning_trades}")
print(f"Losing Trades: {losing_trades}")
print(f"Win Rate: {(winning_trades / len(closed_positions) * 100) if closed_positions else 0:.1f}%")
print(f"Total P&L: ₹{total_pnl:.2f}")

# Show recent activity timeline
print(f"\n⏱️  RECENT ACTIVITY TIMELINE:")
print("-" * 80)
for pos in today_positions[-5:]:  # Last 5 positions
    entry_time = pos['entry_time_ist'].strftime('%H:%M:%S')
    status = "OPEN" if pos['is_open'] else "CLOSED"
    symbol = pos['symbol']
    
    if pos['is_open']:
        pnl = pos.get('unrealized_pnl', 0)
        print(f"{entry_time} - {status:6s} - {symbol:20s} - P&L: ₹{pnl:+.2f}")
    else:
        exit_time = pos['exit_time_ist'].strftime('%H:%M:%S')
        pnl = pos.get('realized_pnl', 0)
        duration = (pos['exit_time_ist'] - pos['entry_time_ist']).total_seconds() / 60
        print(f"{entry_time} → {exit_time} ({duration:.1f}m) - {status:6s} - {symbol:20s} - P&L: ₹{pnl:+.2f}")

print("\n" + "=" * 80)
if issues_found == 0:
    print("✅ ALL VALIDATIONS PASSED - System working correctly!")
else:
    print(f"⚠️  {issues_found} ISSUES FOUND - Review above for details")
print("=" * 80)
