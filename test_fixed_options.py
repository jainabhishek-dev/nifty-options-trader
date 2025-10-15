import sys
sys.path.append('.')
from datetime import datetime
from strategies.options_strategy import ATMStraddleStrategy
from core.kite_manager import KiteManager
from risk_management.options_risk_manager import OptionsRiskManager
from utils.market_utils import MarketDataManager

print('=== TESTING FIXED OPTIONS FORMAT ===')

# Create instances
kite_manager = KiteManager()
market_data = MarketDataManager(kite_manager)
risk_manager = OptionsRiskManager(kite_manager, market_data)

strategy = ATMStraddleStrategy(
    kite_client=kite_manager.kite,
    risk_manager=risk_manager,
    market_data=market_data,
    entry_time_start='09:20',
    entry_time_end='14:00',
    exit_time='15:00'
)

# Set time context for backtesting
test_time = datetime(2025, 10, 14, 10, 30, 0)
strategy.set_time_context(test_time)

print('1. Time Check:')
current_time = strategy._get_current_time().time()
print(f'   Current: {current_time}')
time_ok = strategy.entry_time_start <= current_time <= strategy.entry_time_end
print(f'   Time OK: {time_ok}')

print('2. Nifty Data:')
nifty_ltp = strategy._get_nifty_ltp()
print(f'   Nifty LTP: {nifty_ltp}')
nifty_ok = nifty_ltp > 0

print('3. Fixed Symbol Generation:')
if nifty_ok:
    atm_strike = round(nifty_ltp / 50) * 50
    print(f'   ATM Strike: {atm_strike}')
    
    expiry = strategy._get_nearest_expiry()
    print(f'   Fixed Expiry Format: {expiry}')
    
    # Generate symbol using fixed format
    ce_symbol = f'NIFTY{expiry}{int(atm_strike)}CE'
    pe_symbol = f'NIFTY{expiry}{int(atm_strike)}PE'
    
    print(f'   CE Symbol: {ce_symbol}')
    print(f'   PE Symbol: {pe_symbol}')
    
    # Test LTP fetching
    ce_ltp = strategy._get_option_ltp(ce_symbol)
    pe_ltp = strategy._get_option_ltp(pe_symbol)
    
    print(f'   CE LTP: {ce_ltp}')
    print(f'   PE LTP: {pe_ltp}')
    
    options_ok = ce_ltp > 0 and pe_ltp > 0
    
print('4. Volatility Check:')
vol_ok = strategy._check_volatility_conditions()
print(f'   Volatility OK: {vol_ok}')

print('\nSUMMARY:')
print(f'Time OK: {time_ok}')
print(f'Nifty OK: {nifty_ok}')
print(f'Volatility OK: {vol_ok}')
print(f'Options OK: {options_ok}')

all_ok = time_ok and nifty_ok and vol_ok and options_ok
print(f'ALL CONDITIONS: {all_ok}')

if all_ok:
    print('\n*** TESTING SIGNAL GENERATION ***')
    signals = strategy.generate_signals()
    print(f'Signals Generated: {len(signals)}')
    
    for i, signal in enumerate(signals):
        print(f'  {i+1}. {signal.symbol}: {signal.action} @ Rs{signal.entry_price}')
        
    if len(signals) > 0:
        print('🎉 SUCCESS! Strategy is now generating trades!')
    else:
        print('⚠️ Still no signals - need further investigation')
else:
    print('❌ Some conditions still failing')