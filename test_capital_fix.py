"""
Test script to verify capital release fix
Tests that capital is properly released when positions are closed
"""
import sys
from datetime import datetime
from core.virtual_order_executor import VirtualOrderExecutor, TradingSignal, SignalType
from core.database_manager import DatabaseManager
from config.settings import TradingConfig

def test_capital_release():
    """Test that capital is released when position closes"""
    
    print("=" * 80)
    print("CAPITAL RELEASE FIX TEST")
    print("=" * 80)
    
    # Initialize with database
    db_manager = DatabaseManager()
    
    # Check configuration value
    print(f"\n1. Configuration Check:")
    print(f"   PAPER_TRADING_CAPITAL from config: ₹{TradingConfig.PAPER_TRADING_CAPITAL:,.0f}")
    
    # Initialize executor - should use config value
    executor = VirtualOrderExecutor(db_manager=db_manager)
    print(f"   Executor initialized with: ₹{executor.initial_capital:,.0f}")
    print(f"   ✅ Config value {'USED' if executor.initial_capital == TradingConfig.PAPER_TRADING_CAPITAL else 'NOT USED'}")
    
    # Record initial state
    initial_capital = executor.available_capital
    print(f"\n2. Initial State:")
    print(f"   Available Capital: ₹{executor.available_capital:,.0f}")
    print(f"   Used Margin: ₹{executor.used_margin:,.0f}")
    print(f"   Positions in Memory: {len(executor.positions)}")
    
    # Create BUY signal
    buy_signal = TradingSignal(
        signal_type=SignalType.BUY_CALL,
        symbol="NIFTY26JAN2624200CE",
        strike_price=24200,
        entry_price=100.0,
        target_price=120.0,
        stop_loss_price=90.0,
        quantity=75,
        timestamp=datetime.now(),
        confidence=0.8
    )
    
    print(f"\n3. Placing BUY Order:")
    print(f"   Symbol: {buy_signal.symbol}")
    print(f"   Quantity: {buy_signal.quantity}")
    print(f"   Price: ₹{buy_signal.entry_price}")
    
    buy_order_id = executor.place_order(buy_signal, current_market_price=100.0)
    
    if not buy_order_id:
        print("   ❌ BUY order failed")
        return False
    
    print(f"   ✅ BUY order executed: {buy_order_id}")
    print(f"\n   After BUY:")
    print(f"   Available Capital: ₹{executor.available_capital:,.0f}")
    print(f"   Used Margin: ₹{executor.used_margin:,.0f}")
    print(f"   Positions in Memory: {len(executor.positions)}")
    
    locked_capital = executor.used_margin
    capital_after_buy = executor.available_capital
    
    # Create SELL signal (with profit)
    sell_signal = TradingSignal(
        signal_type=SignalType.SELL_CALL,
        symbol="NIFTY26JAN2624200CE",
        strike_price=24200,
        entry_price=110.0,  # ₹10 profit per unit
        target_price=120.0,
        stop_loss_price=90.0,
        quantity=75,
        timestamp=datetime.now(),
        confidence=0.8
    )
    
    print(f"\n4. Placing SELL Order:")
    print(f"   Symbol: {sell_signal.symbol}")
    print(f"   Quantity: {sell_signal.quantity}")
    print(f"   Price: ₹{sell_signal.entry_price} (₹10 profit per unit)")
    print(f"   Expected P&L: ₹{(sell_signal.entry_price - buy_signal.entry_price) * sell_signal.quantity:,.0f}")
    
    sell_order_id = executor.place_order(sell_signal, current_market_price=110.0)
    
    if not sell_order_id:
        print("   ❌ SELL order failed")
        return False
    
    print(f"   ✅ SELL order executed: {sell_order_id}")
    print(f"\n   After SELL:")
    print(f"   Available Capital: ₹{executor.available_capital:,.0f}")
    print(f"   Used Margin: ₹{executor.used_margin:,.0f}")
    print(f"   Positions in Memory: {len(executor.positions)}")
    
    # Verify capital was released
    print(f"\n5. Capital Release Verification:")
    print(f"   Initial Capital: ₹{initial_capital:,.0f}")
    print(f"   Locked on BUY: ₹{locked_capital:,.0f}")
    realized_pnl = (sell_signal.entry_price - buy_signal.entry_price) * sell_signal.quantity
    print(f"   Realized P&L: ₹{realized_pnl:+,.0f}")
    print(f"   Expected Available: ₹{initial_capital + realized_pnl:,.0f}")
    print(f"   Actual Available: ₹{executor.available_capital:,.0f}")
    
    expected_capital = initial_capital + realized_pnl
    capital_match = abs(executor.available_capital - expected_capital) < 100  # Allow small rounding
    
    print(f"   {'✅' if capital_match else '❌'} Capital Release: {'WORKING' if capital_match else 'BROKEN'}")
    
    # Verify margin was released
    margin_released = executor.used_margin == 0
    print(f"   {'✅' if margin_released else '❌'} Margin Release: {'WORKING' if margin_released else 'BROKEN'}")
    
    # Verify position was removed from memory
    position_removed = len(executor.positions) == 0
    print(f"   {'✅' if position_removed else '❌'} Memory Cleanup: {'WORKING' if position_removed else 'BROKEN'}")
    
    # Test multiple positions
    print(f"\n6. Testing Multiple Positions (10 trades):")
    for i in range(10):
        # BUY
        buy_sig = TradingSignal(
            signal_type=SignalType.BUY_CALL,
            symbol=f"NIFTY26JAN2624{200 + i}00CE",
            strike_price=24200 + i * 100,
            entry_price=100.0,
            target_price=120.0,
            stop_loss_price=90.0,
            quantity=75,
            timestamp=datetime.now(),
            confidence=0.8
        )
        executor.place_order(buy_sig, current_market_price=100.0)
        
        # SELL with small profit
        sell_sig = TradingSignal(
            signal_type=SignalType.SELL_CALL,
            symbol=f"NIFTY26JAN2624{200 + i}00CE",
            strike_price=24200 + i * 100,
            entry_price=102.0,
            target_price=120.0,
            stop_loss_price=90.0,
            quantity=75,
            timestamp=datetime.now(),
            confidence=0.8
        )
        executor.place_order(sell_sig, current_market_price=102.0)
    
    print(f"   After 10 complete trades:")
    print(f"   Available Capital: ₹{executor.available_capital:,.0f}")
    print(f"   Used Margin: ₹{executor.used_margin:,.0f}")
    print(f"   Positions in Memory: {len(executor.positions)}")
    
    # Final verification
    expected_final = initial_capital + (10 * 2.0 * 75) + (750)  # 10 trades × ₹2 profit × 75 qty + first trade profit
    capital_stable = abs(executor.available_capital - expected_final) < 500
    
    print(f"\n7. Final Result:")
    print(f"   Expected Capital: ₹{expected_final:,.0f}")
    print(f"   Actual Capital: ₹{executor.available_capital:,.0f}")
    print(f"   Difference: ₹{abs(executor.available_capital - expected_final):,.0f}")
    print(f"   {'✅' if capital_stable else '❌'} Capital Tracking: {'STABLE' if capital_stable else 'UNSTABLE'}")
    
    print("\n" + "=" * 80)
    if capital_match and margin_released and position_removed and capital_stable:
        print("✅ ALL FIXES WORKING CORRECTLY!")
        print("=" * 80)
        return True
    else:
        print("❌ SOME FIXES NOT WORKING")
        print("=" * 80)
        return False

if __name__ == "__main__":
    try:
        success = test_capital_release()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
