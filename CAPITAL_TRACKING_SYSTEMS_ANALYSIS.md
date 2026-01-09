# Capital Tracking Systems Analysis
**Date:** January 9, 2026  
**Issue:** Trading stops after 16 positions despite dashboard showing correct available margin

---

## 🔍 DISCOVERY: Two Separate Capital Tracking Systems

The system has **TWO INDEPENDENT** capital tracking mechanisms that are NOT synchronized:

### System 1: VirtualOrderExecutor (Trading Logic) ❌ BROKEN
**Location:** `core/virtual_order_executor.py`  
**Purpose:** Actual trading decisions - decides if orders can be placed  
**Data Source:** In-memory tracking

```python
# Initialization (Line 99-101)
def __init__(self, initial_capital: float = 200000.0):
    self.initial_capital = initial_capital
    self.available_capital = initial_capital  # Always 200,000 on startup
    self.used_margin = 0.0

# Capital Check BEFORE placing order (Line 406-407)
if required_capital > self.available_capital:
    print(f"Insufficient capital. Required: ₹{required_capital:,.0f}, Available: ₹{self.available_capital:,.0f}")
    return False

# Capital Lock on BUY (Line 583-584)
self.available_capital -= total_cost  # LOCKS capital
self.used_margin += total_cost

# PROBLEM: No capital release on SELL (Lines 685-764)
# _close_matching_position() method closes position but NEVER does:
# self.available_capital += locked_capital + pnl  ❌ MISSING!
```

**Result:** Capital depletes from ₹200,000 → ₹92 over 16 positions, blocking further trades

---

### System 2: Dashboard/Web UI (Display) ✅ CORRECT
**Location:** `web_ui/app.py`  
**Purpose:** Display metrics to user  
**Data Source:** Database positions (real-time calculation)

#### Dashboard Calculations (Line 324-365)

```python
# Initial margin (Line 324)
initial_margin = 100000.0  # Fixed starting capital

# Calculate from DATABASE positions (Line 329-360)
total_pnl = 0.0
margin_used = 0.0

for position in all_positions:  # Read from database
    # Total P&L from ALL positions (open + closed, all days)
    unrealized_pnl = position.get('unrealized_pnl', 0.0)
    realized_pnl = position.get('realized_pnl', 0.0)
    total_pnl += unrealized_pnl + realized_pnl
    
    # Margin used ONLY for currently OPEN positions
    if position.get('is_open', False):
        quantity = position.get('quantity', 0)
        entry_price = position.get('entry_price', 0.0)
        margin_used += abs(quantity * entry_price)

# Calculate available margin (Line 364-365)
margin_available = initial_margin - margin_used + total_pnl
```

**This calculation is CORRECT** - it accounts for:
- ✅ Capital locked in open positions (`margin_used`)
- ✅ Profits/losses from ALL positions (`total_pnl`)
- ✅ Capital recovery from closed positions

---

### Positions Page Calculations (Line 695-697)

```python
# Margin Used = investment in ALL OPEN positions
all_positions = trading_manager.db_manager.get_positions(trading_mode='paper')
margin_used = sum(
    abs(pos.get('quantity', 0)) * (pos.get('entry_price', 0.0) or pos.get('average_price', 0.0)) 
    for pos in all_positions 
    if pos.get('is_open', False)
)

# Current Day P&L = sum of P&L from positions opened today
total_pnl = sum(pos.get('pnl', 0.0) for pos in db_positions)
```

**Also CORRECT** - reads from database and calculates properly

---

## 📊 Dashboard Metrics Breakdown

### Card 1: Market Status (Line 91-107)
- **Source:** Real-time from Kite API
- **Shows:** Open/Closed

### Card 2: Current Day P&L (Line 109-120)
- **Source:** Dashboard calculation (line 349-350)
- **Formula:** Sum of P&L from positions opened today
- **Variable:** `data.portfolio.total_pnl`
- **Displays:** Amount + Percentage

### Card 3: Total P&L (All Time) (Line 122-132)
- **Source:** Same as Current Day P&L
- **Variable:** `data.portfolio.total_realized_pnl`
- **Note:** Actually shows the same as Card 2 (needs clarification)

### Card 4: Margin Available (Line 134-147)
- **Source:** Dashboard calculation (line 364-365)
- **Formula:** `initial_margin - margin_used + total_pnl`
- **Variable:** `data.portfolio.margin_available`
- **This is the KEY metric** ✅ Shows CORRECT available capital

### Card 5: Margin Used (Line 149-160)
- **Source:** Dashboard calculation (line 354-356)
- **Formula:** Sum of `quantity × entry_price` for OPEN positions only
- **Variable:** `data.portfolio.margin_used`
- **Also CORRECT** ✅

---

## 🎯 Why Dashboard Shows Correct Values

The dashboard **reads from database** and **recalculates on every page load**:

```python
# Dashboard Route (Line 307-380)
@app.route('/paper/dashboard')
def paper_dashboard():
    # Get ALL positions from database
    all_positions = trading_manager.db_manager.get_positions(trading_mode='paper')
    
    # Recalculate everything from scratch
    for position in all_positions:
        total_pnl += position['unrealized_pnl'] + position['realized_pnl']
        if position['is_open']:
            margin_used += position['quantity'] * position['entry_price']
    
    margin_available = 100000 - margin_used + total_pnl
```

**This is stateless** - it doesn't depend on any in-memory variable that could get corrupted

---

## ❌ Why Trading Stops

Trading uses `VirtualOrderExecutor.available_capital` which is **stateful** and has bugs:

```python
# Order placement check (Line 406-407)
if required_capital > self.available_capital:  # Uses broken in-memory variable
    print("Insufficient capital")
    return False  # ❌ REJECTS ORDER
```

**Flow of Capital Depletion:**

1. **Startup:** `available_capital = 200,000`
2. **Trade 1 (BUY):** Lock ₹6,000 → `available_capital = 194,000`
3. **Trade 1 (SELL):** Position closed but capital NOT released → `available_capital = 194,000` ❌
4. **Trade 2 (BUY):** Lock ₹6,200 → `available_capital = 187,800`
5. **Trade 2 (SELL):** Capital NOT released → `available_capital = 187,800` ❌
6. ... *repeats 16 times*
7. **After 16 positions:** `available_capital = ₹92`
8. **Next trade attempt:** Needs ₹6,185 > ₹92 available → **REJECTED** ❌

Meanwhile, the dashboard correctly shows: `100,000 - margin_used + total_pnl = ₹95,500` (example)

---

## 🔢 Example Scenario

Let's trace through actual numbers:

### Initial State
```
VirtualOrderExecutor.available_capital = 200,000
Dashboard: margin_available = 100,000 - 0 + 0 = 100,000
```

### After 1st Position (BUY NIFTY CE @ ₹100, Qty 75)
```
VirtualOrderExecutor:
  - available_capital -= 7,500 → 192,500
  - used_margin += 7,500 → 7,500

Dashboard (from DB):
  - margin_used = 7,500 (1 open position)
  - total_pnl = 0
  - margin_available = 100,000 - 7,500 + 0 = 92,500 ✅
```

### After 1st Position Closes (SELL @ ₹110, Profit ₹750)
```
VirtualOrderExecutor:
  - available_capital = 192,500 (UNCHANGED!) ❌
  - used_margin = 7,500 (UNCHANGED!) ❌
  - Position closed in DB but NOT reflected in memory

Dashboard (from DB):
  - margin_used = 0 (no open positions)
  - total_pnl = +750 (realized)
  - margin_available = 100,000 - 0 + 750 = 100,750 ✅
```

**Gap Created:** 
- VirtualOrderExecutor thinks: ₹192,500 available
- Reality (Dashboard): ₹100,750 available
- But VirtualOrderExecutor is what matters for trading!

### After 16 Positions
```
VirtualOrderExecutor:
  - available_capital = 92 (leaked away)
  - Cannot place new orders ❌

Dashboard (from DB):
  - margin_used = 12,000 (2 open positions)
  - total_pnl = +3,500
  - margin_available = 100,000 - 12,000 + 3,500 = 91,500 ✅
```

**Critical Observation:** User sees ₹91,500 available on dashboard but trading is blocked!

---

## 🔍 Database Values

### daily_pnl Table (Line 1129-1178)
```python
# Trading Manager writes to this table (Line 1162)
portfolio_value = self.order_executor.available_capital + realized_pnl + unrealized_pnl

# This RECORDS the broken value (₹92)
pnl_data = {
    'portfolio_value': portfolio_value  # 92.10 stored in DB
}
```

**The ₹92.10 in daily_pnl is a SYMPTOM not a CAUSE:**
- It's written FROM `available_capital` (broken value)
- It's NOT read back to set `available_capital`
- Dashboard reads it for display only (Line 600-601)

---

## 🐛 The Three Bugs

### Bug #1: Capital Never Released on SELL (PRIMARY CAUSE)
**Location:** Lines 685-764 in `_close_matching_position()`  
**Problem:** Position closed, capital stays locked forever  
**Impact:** Capital depletes with each position until ₹92

```python
# What happens now:
def _close_matching_position(...):
    self.positions[key].is_closed = True  # Mark closed
    # ❌ MISSING: self.available_capital += locked_capital + pnl
    # ❌ MISSING: self.used_margin -= locked_capital

# What should happen:
locked_capital = entry_price * quantity
realized_pnl = (exit_price - entry_price) * quantity
self.available_capital += locked_capital + realized_pnl
self.used_margin -= locked_capital
```

### Bug #2: Position Memory Leak
**Location:** Same method  
**Problem:** Closed positions never removed from `self.positions` dict  
**Impact:** Position count includes closed positions → hits 50 limit prematurely

```python
# Missing:
del self.positions[target_position_key]
```

### Bug #3: Configuration Not Used
**Location:** Multiple files  
**Problem:** `TradingConfig.PAPER_TRADING_CAPITAL` defined but never used  
**Impact:** User sets 100k in .env, system uses hardcoded 200k

---

## ✅ The Solution

Make `VirtualOrderExecutor` use the same logic as the dashboard:

### Option A: Calculate Available Capital Dynamically
```python
def get_available_capital(self) -> float:
    """Calculate available capital from database (same as dashboard)"""
    if not self.db_manager:
        return self.available_capital  # Fallback to in-memory
    
    # Get all positions from database
    all_positions = self.db_manager.get_positions(trading_mode='paper')
    
    # Calculate margin used (open positions only)
    margin_used = 0.0
    for pos in all_positions:
        if pos.get('is_open', False):
            margin_used += abs(pos['quantity'] * pos['average_price'])
    
    # Calculate total P&L (all positions)
    total_pnl = 0.0
    for pos in all_positions:
        total_pnl += pos.get('unrealized_pnl', 0.0) + pos.get('realized_pnl', 0.0)
    
    # Same formula as dashboard
    return self.initial_capital - margin_used + total_pnl

# Use in validation (Line 406)
available = self.get_available_capital()
if required_capital > available:
    print(f"Insufficient capital. Required: ₹{required_capital:,.0f}, Available: ₹{available:,.0f}")
    return False
```

### Option B: Fix Capital Release (Maintain In-Memory Tracking)
```python
# In _close_matching_position() after closing position:
locked_capital = entry_price * quantity + fees_on_entry
realized_pnl = (exit_price - entry_price) * quantity - fees_on_exit
self.available_capital += locked_capital + realized_pnl
self.used_margin -= locked_capital

# Also remove closed position from memory:
del self.positions[target_position_key]
```

**Recommendation:** Implement BOTH
- Option B for immediate fix (restores in-memory tracking)
- Option A as validation/fallback (ensures consistency with dashboard)

---

## 📋 Testing Checklist

After implementing fixes:

1. ✅ Verify capital released on SELL
2. ✅ Verify closed positions removed from memory
3. ✅ Compare VirtualOrderExecutor.available_capital with dashboard
4. ✅ Test with restart scenario (capital persists correctly)
5. ✅ Verify configuration value (100k) is used instead of 200k
6. ✅ Run 20+ positions to ensure no depletion
7. ✅ Check logs for "Insufficient capital" errors

---

## 🎯 Summary

**Why dashboard is correct:**
- Reads from database on every page load
- Calculates: `initial - locked + pnl`
- Stateless, cannot get corrupted

**Why trading stops:**
- Uses in-memory `available_capital`
- Locks capital on BUY, never releases on SELL
- Depletes to ₹92 after 16 positions
- Rejects further trades

**The fix:**
- Release capital on SELL: `available_capital += locked + pnl`
- Remove closed positions: `del self.positions[key]`
- Use config value instead of hardcoded 200k
- Add validation against database calculation
