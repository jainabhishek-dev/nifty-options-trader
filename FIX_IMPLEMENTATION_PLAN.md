# Capital Leak Fix - Implementation Plan
**Date:** January 9, 2026  
**Objective:** Fix capital depletion bug without introducing new errors

---

## 🎯 Root Cause Analysis

### Current Flow (BROKEN):

```
BUY Order Executed (Line 583-584):
├─ available_capital -= total_cost     (e.g., 200,000 - 6,000 = 194,000)
└─ used_margin += total_cost           (e.g., 0 + 6,000 = 6,000)

Position Created (Line 607-682):
└─ Position stored in memory: self.positions[unique_key] = position

SELL Order Executed (Line 581):
└─ _update_position() → _close_matching_position()

_close_matching_position() (Line 685-764):
├─ Marks position as closed: position.is_closed = True
├─ Updates database: is_open = False, realized_pnl = xxx
└─ ❌ MISSING: Capital never released!

Result:
├─ available_capital stays at 194,000 (should return to 200,000 + profit/loss)
├─ used_margin stays at 6,000 (should return to 0)
└─ Memory leak: Closed position still in self.positions dict
```

### After 16 Positions:
```
available_capital = 92  (should be ~198,000)
used_margin = ~120,000  (should be ~12,000 for 2 open positions)
len(self.positions) = 16 (includes 14 closed + 2 open, should be 2)
```

---

## 📋 Required Changes

### Change #1: Release Capital in `_close_matching_position()` ⭐ CRITICAL
**File:** `core/virtual_order_executor.py`  
**Line:** After line 721 (after database update)  
**Action:** Add capital release logic

#### Current Code (Line 706-764):
```python
# Calculate P&L correctly - use ORIGINAL quantity before it was set to 0
original_quantity = target_position.metadata.get('original_quantity', trade.quantity)
pnl = (trade.price - target_position.entry_price) * original_quantity
pnl_percent = ((trade.price - target_position.entry_price) / target_position.entry_price) if target_position.entry_price > 0 else 0

position_update_data = {
    'quantity': 0,
    'current_price': trade.price,
    'unrealized_pnl': 0.0,
    'realized_pnl': pnl,
    # ... other fields ...
}

# Update database
result = self.db_manager.supabase.table('positions').update(position_update_data).eq('id', position_id).execute()

if result.data:
    print(f"✅ Position closed in database: {order.symbol} (P&L: {pnl_percent*100:+.2f}%)")
else:
    print(f"⚠️ Failed to update position closure in database")
    
except Exception as e:
    print(f"Warning: Failed to update closed position in database: {e}")
    
# ❌ MISSING: Capital release code should be here!
```

#### New Code to Add (After line 721):
```python
# 🚀 CRITICAL FIX: Release capital when position closes
# This restores the capital that was locked when the position was opened
try:
    # Calculate locked capital (original investment + fees on entry)
    locked_capital = target_position.entry_price * original_quantity
    
    # Calculate realized P&L (already calculated above)
    realized_pnl = pnl  # Use the pnl variable already calculated
    
    # Release capital: Return locked amount + profit/loss
    self.available_capital += locked_capital + realized_pnl
    self.used_margin -= locked_capital
    
    print(f"💰 Capital released: Locked=₹{locked_capital:,.0f}, P&L={realized_pnl:+,.0f}, Available=₹{self.available_capital:,.0f}")
    
except Exception as e:
    print(f"⚠️  Error releasing capital: {e}")
```

**Why this works:**
- `locked_capital` = exact amount that was deducted on BUY (line 583)
- `realized_pnl` = profit or loss from the trade
- Total return = investment + profit/loss
- Example: Bought at ₹100×75 = ₹7,500, sold at ₹110×75 = ₹8,250
  - locked_capital = ₹7,500
  - realized_pnl = ₹750
  - available_capital += ₹7,500 + ₹750 = ₹8,250 increase ✅

---

### Change #2: Remove Closed Positions from Memory ⭐ CRITICAL
**File:** `core/virtual_order_executor.py`  
**Line:** After capital release (after Change #1)  
**Action:** Delete closed position from dict

#### Code to Add:
```python
# 🚀 MEMORY LEAK FIX: Remove closed position from memory
# Closed positions should only exist in database, not in active memory
try:
    if target_position_key in self.positions:
        del self.positions[target_position_key]
        print(f"🗑️  Removed closed position from memory: {target_position_key}")
        print(f"📊 Active positions in memory: {len(self.positions)}")
    
except Exception as e:
    print(f"⚠️  Error removing closed position from memory: {e}")
```

**Why this works:**
- Prevents position count from including closed positions
- Keeps memory clean (only track active positions)
- Matches database behavior (closed positions have is_open=False)

---

### Change #3: Use Configuration Instead of Hardcoded Values
**Files:** Multiple  
**Action:** Replace hardcoded 200000 with TradingConfig.PAPER_TRADING_CAPITAL

#### File 1: `core/virtual_order_executor.py` (Line 99)
```python
# Current:
def __init__(self, initial_capital: float = 200000.0, db_manager=None, kite_manager=None):

# Change to:
def __init__(self, initial_capital: float = None, db_manager=None, kite_manager=None):
    from config.settings import TradingConfig
    if initial_capital is None:
        initial_capital = TradingConfig.PAPER_TRADING_CAPITAL
    self.initial_capital = initial_capital
```

#### File 2: `core/trading_manager.py` (Line 44)
```python
# Current:
def __init__(self, kite_manager, initial_capital: float = 200000.0):

# Change to:
def __init__(self, kite_manager, initial_capital: float = None):
    from config.settings import TradingConfig
    if initial_capital is None:
        initial_capital = TradingConfig.PAPER_TRADING_CAPITAL
```

#### File 3: `web_ui/app.py` (Line 142)
```python
# Current:
trading_manager = TradingManager(kite_manager, initial_capital=200000.0)

# Change to:
from config.settings import TradingConfig
trading_manager = TradingManager(kite_manager, initial_capital=TradingConfig.PAPER_TRADING_CAPITAL)
```

**Why this works:**
- Respects user configuration from .env file
- Single source of truth for capital amount
- User sets PAPER_TRADING_CAPITAL=100000 → system uses 100,000

---

### Change #4: Add Capital Validation (OPTIONAL but Recommended)
**File:** `core/virtual_order_executor.py`  
**Location:** Add new method after `__init__`  
**Purpose:** Detect discrepancies early

#### New Method:
```python
def validate_capital_with_database(self) -> dict:
    """
    Validate in-memory capital against database calculation
    Returns dict with comparison results
    """
    if not self.db_manager:
        return {'validated': False, 'reason': 'No database manager'}
    
    try:
        # Get all positions from database (same logic as dashboard)
        all_positions = self.db_manager.get_positions(trading_mode='paper')
        
        # Calculate margin used (only OPEN positions)
        db_margin_used = 0.0
        for pos in all_positions:
            if pos.get('is_open', False):
                quantity = pos.get('quantity', 0)
                entry_price = pos.get('entry_price', 0.0) or pos.get('average_price', 0.0)
                db_margin_used += abs(quantity * entry_price)
        
        # Calculate total P&L (all positions)
        db_total_pnl = 0.0
        for pos in all_positions:
            db_total_pnl += pos.get('unrealized_pnl', 0.0) + pos.get('realized_pnl', 0.0)
        
        # Calculate expected available capital (same as dashboard)
        db_available_capital = self.initial_capital - db_margin_used + db_total_pnl
        
        # Compare with in-memory values
        capital_diff = abs(self.available_capital - db_available_capital)
        margin_diff = abs(self.used_margin - db_margin_used)
        
        return {
            'validated': True,
            'in_memory': {
                'available_capital': self.available_capital,
                'used_margin': self.used_margin
            },
            'from_database': {
                'available_capital': db_available_capital,
                'used_margin': db_margin_used,
                'total_pnl': db_total_pnl
            },
            'differences': {
                'capital_diff': capital_diff,
                'margin_diff': margin_diff
            },
            'status': 'OK' if capital_diff < 100 and margin_diff < 100 else 'MISMATCH'
        }
        
    except Exception as e:
        return {'validated': False, 'reason': str(e)}
```

#### Call this validation periodically:
```python
# In place_order() method, before validation (around line 395)
if len(self.orders) % 10 == 0:  # Every 10 orders
    validation = self.validate_capital_with_database()
    if validation.get('status') == 'MISMATCH':
        print(f"⚠️  Capital mismatch detected!")
        print(f"   In-memory: ₹{validation['in_memory']['available_capital']:,.0f}")
        print(f"   Database: ₹{validation['from_database']['available_capital']:,.0f}")
        print(f"   Difference: ₹{validation['differences']['capital_diff']:,.0f}")
```

**Why this works:**
- Early detection of capital tracking errors
- Alerts if bugs reappear
- Helps with debugging

---

## 🧪 Testing Strategy

### Step 1: Unit Test - Capital Release
```python
# Test script: test_capital_release.py
executor = VirtualOrderExecutor(initial_capital=100000.0)

# BUY order
buy_signal = TradingSignal(symbol="NIFTY24200CE", signal_type=SignalType.BUY_CALL, quantity=75, price=100)
executor.place_order(buy_signal)
assert executor.available_capital == 92500  # 100,000 - 7,500

# SELL order
sell_signal = TradingSignal(symbol="NIFTY24200CE", signal_type=SignalType.SELL_CALL, quantity=75, price=110)
executor.place_order(sell_signal)
# Should release: 7,500 (locked) + 750 (profit) = 8,250
assert executor.available_capital == 100750  # 92,500 + 8,250 ✅
assert executor.used_margin == 0  # Should be back to 0 ✅
assert len(executor.positions) == 0  # Closed position removed ✅
```

### Step 2: Integration Test - Multiple Positions
```python
# 20 positions (BUY → SELL)
for i in range(20):
    buy_signal = TradingSignal(...)
    executor.place_order(buy_signal)
    
    sell_signal = TradingSignal(...)
    executor.place_order(sell_signal)

# After 20 complete trades:
assert executor.available_capital > 99000  # Should be close to 100,000 ✅
assert executor.used_margin == 0  # No open positions ✅
assert len(executor.positions) == 0  # All removed ✅
```

### Step 3: Real Trading Test
1. Start trading with fixes
2. Monitor logs for "Capital released" messages
3. Check dashboard shows same value as VirtualOrderExecutor
4. Run validation every 10 orders
5. After 30+ trades, verify no depletion

---

## 📊 Expected Results After Fix

### Before Fix (Current):
```
After 16 positions:
├─ VirtualOrderExecutor.available_capital = ₹92
├─ VirtualOrderExecutor.used_margin = ~₹120,000
├─ len(self.positions) = 16 (includes closed)
└─ Trading: BLOCKED ❌

Dashboard shows:
├─ Margin Available = ₹91,500
├─ Margin Used = ₹12,000
└─ Display: CORRECT ✅
```

### After Fix:
```
After 16 positions (with 2 open):
├─ VirtualOrderExecutor.available_capital = ₹91,500
├─ VirtualOrderExecutor.used_margin = ₹12,000
├─ len(self.positions) = 2 (only open)
└─ Trading: CONTINUES ✅

Dashboard shows:
├─ Margin Available = ₹91,500
├─ Margin Used = ₹12,000
└─ MATCHES VirtualOrderExecutor ✅
```

---

## ⚠️ Critical Safeguards

### 1. Transaction-like Logic
```python
# In _close_matching_position(), wrap capital release:
try:
    # Release capital
    self.available_capital += locked_capital + realized_pnl
    self.used_margin -= locked_capital
    
    # Remove from memory
    del self.positions[target_position_key]
    
    print("✅ Capital released and position removed")
    
except Exception as e:
    # Log error but don't crash
    print(f"⚠️  Partial failure in position closure: {e}")
    # Database still updated, but in-memory might be inconsistent
    # Validation method will catch this
```

### 2. Never Use Mock Values
All calculations use REAL values:
- ✅ `entry_price` from position object (real value from BUY)
- ✅ `exit_price` from trade object (real value from SELL)
- ✅ `original_quantity` from metadata (real value)
- ❌ NO hardcoded assumptions
- ❌ NO default fallbacks unless absolutely necessary

### 3. Database as Source of Truth
- In-memory tracking can have bugs
- Database is always correct
- Validation method compares and alerts

---

## 🚀 Implementation Order

1. **Change #1** (Capital Release) - HIGHEST PRIORITY
   - This immediately fixes the depletion bug
   - Without this, all other fixes are useless

2. **Change #2** (Memory Cleanup) - HIGH PRIORITY
   - Fixes position count issue
   - Prevents hitting 50 position limit

3. **Change #3** (Use Config) - MEDIUM PRIORITY
   - Respects user settings
   - Good practice, but not blocking

4. **Change #4** (Validation) - LOW PRIORITY (Optional)
   - Safety net for future bugs
   - Can be added later if needed

---

## 📝 Exact Line Numbers for Changes

### Change #1 - Capital Release
**File:** `core/virtual_order_executor.py`  
**Insert after:** Line 721 (after `if result.data:` block)  
**Before:** Line 764 (`except Exception as e:` at method end)

### Change #2 - Memory Cleanup
**File:** `core/virtual_order_executor.py`  
**Insert after:** Change #1 code  
**Same location**

### Change #3 - Use Config
**File 1:** `core/virtual_order_executor.py` Line 99  
**File 2:** `core/trading_manager.py` Line 44  
**File 3:** `web_ui/app.py` Line 142

### Change #4 - Validation (Optional)
**File:** `core/virtual_order_executor.py`  
**Insert after:** `__init__` method (around line 130)  
**Call from:** `place_order()` method (around line 395)

---

## ✅ Success Criteria

Fix is successful when:
1. ✅ Capital released on every SELL order
2. ✅ `available_capital` stays around initial value (±P&L)
3. ✅ `used_margin` matches dashboard's "Margin Used"
4. ✅ Closed positions removed from memory
5. ✅ Can execute 50+ trades without depletion
6. ✅ Dashboard and VirtualOrderExecutor show same values
7. ✅ Configuration value (100k) is respected

---

## 🔍 How to Verify Fix is Working

After implementing, look for these log messages:

```
✅ Position closed in database: NIFTY24200CE (P&L: +2.50%)
💰 Capital released: Locked=₹7,500, P&L=+₹750, Available=₹100,750
🗑️  Removed closed position from memory: NIFTY24200CE_a1b2c3d4
📊 Active positions in memory: 1
```

If you see these on every SELL order → Fix is working! ✅
