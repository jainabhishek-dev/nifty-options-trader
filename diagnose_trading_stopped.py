"""
Diagnostic script to check why trading stopped after 16 positions (32 orders)
Date: January 9, 2026

This analyzes the CODE to find limits, not the database.
"""

from datetime import datetime
import pytz

ist = pytz.timezone('Asia/Kolkata')
today = datetime.now(ist).date()

print("="*80)
print(f"TRADING LIMITS DIAGNOSTIC - {today}")
print("="*80)

# User reported data
print("\n📊 REPORTED DATA:")
print("-"*80)
print(f"Positions created: 16")
print(f"Total orders: 32 (16 BUY + 16 SELL assumed)")
print(f"Trading stopped: YES")
print(f"No more orders coming in: YES")

print("\n" + "="*80)
print("CHECKING LIMITS IN CODE")
print("="*80)

# Check virtual_order_executor.py
print("\n1. virtual_order_executor.py:")
print("-"*80)
with open('core/virtual_order_executor.py', 'r', encoding='utf-8') as f:
    voe_code = f.read()
    
    # Find max_positions
    for line in voe_code.split('\n'):
        if 'self.max_positions' in line and '=' in line and not line.strip().startswith('#'):
            print(f"   {line.strip()}")
            
    # Check if position limit check exists
    if 'len(self.positions) >= self.max_positions' in voe_code:
        print("   ✅ Position limit check EXISTS")
        print("   Location: In place_order() method")
        
        # Find the exact check
        for i, line in enumerate(voe_code.split('\n')):
            if 'len(self.positions) >= self.max_positions' in line:
                print(f"   Line: {line.strip()}")
                # Get context
                lines = voe_code.split('\n')
                if i > 0:
                    print(f"   Previous: {lines[i-1].strip()}")
                if i < len(lines) - 1:
                    print(f"   Next: {lines[i+1].strip()}")
                break

# Check trading_manager.py
print("\n2. trading_manager.py:")
print("-"*80)
with open('core/trading_manager.py', 'r', encoding='utf-8') as f:
    tm_code = f.read()
    
    # Find max_daily_trades
    for line in tm_code.split('\n'):
        if 'self.max_daily_trades' in line and '=' in line and not line.strip().startswith('#'):
            print(f"   {line.strip()}")
            
    # Check if daily trade limit check exists
    if 'daily_trade_count >= self.max_daily_trades' in tm_code:
        print("   ✅ Daily trade limit check EXISTS")
        print("   Location: In signal processing")
        
        # Find the exact check
        for i, line in enumerate(tm_code.split('\n')):
            if 'daily_trade_count >= self.max_daily_trades' in line:
                print(f"   Line: {line.strip()}")
                lines = tm_code.split('\n')
                if i > 0:
                    print(f"   Previous: {lines[i-1].strip()}")
                if i < len(lines) - 2:
                    print(f"   Next: {lines[i+1].strip()}")
                    print(f"   Next+1: {lines[i+2].strip()}")
                break
                
    # Check what increments daily_trade_count
    print("\n   Daily trade count incremented when:")
    for i, line in enumerate(tm_code.split('\n')):
        if 'self.daily_trade_count += 1' in line:
            lines = tm_code.split('\n')
            print(f"   - {line.strip()}")
            if i > 2:
                print(f"     Context (3 lines before):")
                for j in range(i-3, i):
                    if j >= 0:
                        print(f"       {lines[j].strip()}")

print("\n" + "="*80)
print("ANALYSIS")
print("="*80)

print("\n🔍 CHECKING WHICH LIMIT WAS HIT:")
print("-"*80)

# Check Position Limit
max_positions = 50  # From code
reported_positions = 16
print(f"\n1. Position Limit:")
print(f"   Max positions allowed: {max_positions}")
print(f"   Reported positions created: {reported_positions}")
print(f"   Status: ✅ WELL WITHIN LIMIT ({reported_positions}/{max_positions})")

# Check Daily Trade Limit  
max_daily_trades = 100  # From code
reported_orders = 32
print(f"\n2. Daily Trade Limit:")
print(f"   Max daily trades: {max_daily_trades}")
print(f"   Reported orders: {reported_orders}")
print(f"   Status: ✅ WELL WITHIN LIMIT ({reported_orders}/{max_daily_trades})")

print(f"\n3. Open Positions Limit:")
print(f"   - The check is: len(self.positions) >= self.max_positions")
print(f"   - This checks OPEN positions in MEMORY")
print(f"   - If 16 positions created, and all are CLOSED, memory should have 0")
print(f"   - If 16 positions created, and all are OPEN, memory should have 16")
print(f"   - QUESTION: How many positions are STILL OPEN?")

print("\n" + "="*80)
print("KEY FINDINGS")
print("="*80)

print("\n1. There are TWO separate limits:")
print("   a) max_positions = 50 (checks open positions in memory)")
print("   b) max_daily_trades = 100 (checks total trade count)")

print("\n2. How limits work:")
print("   - Position limit: Blocks NEW BUY orders when open positions >= 50")
print("   - Trade limit: Blocks ALL orders when trade count >= 100")

print("\n3. Trade count increment:")
print("   - Incremented ONCE per successful place_order() call")
print("   - So 16 positions = 16 BUY orders = 16 trade count increments")
print("   - SELL orders also increment (if 16 closed, +16 more = 32 total)")

print("\n4. Critical distinction:")
print("   - Position limit checks: len(self.positions) in MEMORY")
print("   - NOT checking database open positions")
print("   - If memory state has 50+ positions, limit triggers")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

print("\n📋 To identify exact cause, check these:")
print("\n1. APPLICATION LOGS:")
print("   Look for these messages:")
print("   - 'Maximum positions limit reached' → Position limit hit")
print("   - 'Daily trade limit (100) reached' → Trade limit hit")
print("   - Any ERROR messages around the time trading stopped")

print("\n2. OPEN POSITIONS:")
print("   - Run: python -c \"from core.database_manager import DatabaseManager; import os; from dotenv import load_dotenv; load_dotenv(); dm = DatabaseManager(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_KEY')); result = dm.supabase.table('positions').select('*').eq('is_open', True).eq('trading_mode', 'paper').execute(); print(f'Open positions: {len(result.data)}')\"")
print("   - If open positions >= 50, that's the issue")

print("\n3. MEMORY vs DATABASE:")
print("   - Position limit checks self.positions dict in MEMORY")
print("   - NOT the database")
print("   - If positions aren't removed from memory on close, limit triggers")

print("\n" + "="*80)
print("LIKELY CAUSES (RANKED)")
print("="*80)

print("\n🎯 MOST LIKELY: Position memory cleanup issue")
print("   - Closed positions not removed from self.positions dict")
print("   - Memory has 50+ positions even though DB shows fewer open")
print("   - Check: _close_matching_position() method")
print("   - Line ~688: Should remove position from self.positions")

print("\n🎯 POSSIBLE: Strategy-specific limits")
print("   - Some strategies may have their own max position limits")
print("   - Check strategy configuration")

print("\n🎯 UNLIKELY: Daily trade or position limits")
print("   - 16 positions << 50 max positions")
print("   - 32 orders << 100 max daily trades")
print("   - These hard limits not reached")

print("\n" + "="*80)
print("NEXT STEPS")
print("="*80)

print("\n✅ IMMEDIATE ACTIONS:")
print("   1. Share application logs from today")
print("   2. Check how many positions are currently OPEN")
print("   3. Count positions in memory: len(self.positions)")

print("\n🔧 AFTER DIAGNOSIS (awaiting your approval):")
print("   1. If memory cleanup issue:")
print("      - Fix _close_matching_position() to remove from dict")
print("   2. If legitimately need more positions:")
print("      - Increase max_positions from 50 to desired value")
print("   3. If strategy limit:")
print("      - Adjust strategy-specific configuration")

print("\n" + "="*80)
