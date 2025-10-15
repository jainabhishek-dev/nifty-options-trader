import sys
sys.path.append('.')
from datetime import datetime, timedelta
from core.kite_manager import KiteManager

print('=== KITE CONNECT HISTORICAL DATA ANALYSIS ===')

kite_manager = KiteManager()

print('1. Current instruments loaded:')
if not kite_manager.instruments:
    kite_manager.load_instruments()

print(f'   Total instruments: {len(kite_manager.instruments)}')

# Check date range of available options
print('2. NIFTY options date range:')
nifty_expiries = []
for token, instrument in kite_manager.instruments.items():
    if (instrument.get('name') == 'NIFTY' and 
        instrument.get('segment') == 'NFO-OPT'):
        expiry = instrument.get('expiry')
        if expiry:
            nifty_expiries.append(expiry)

if nifty_expiries:
    nifty_expiries.sort()
    print(f'   Earliest expiry: {nifty_expiries[0]}')
    print(f'   Latest expiry: {nifty_expiries[-1]}')
    print(f'   Total expiry dates: {len(set(nifty_expiries))}')
else:
    print('   No NIFTY options found')

print('3. Testing historical data API:')
try:
    # Test if we can get historical data for old dates
    from_date = datetime.now() - timedelta(days=30)  # 30 days ago
    to_date = datetime.now() - timedelta(days=29)    # 29 days ago
    
    # Try to get NIFTY historical data
    nifty_token = '256265'  # NIFTY 50 token
    
    print(f'   Attempting historical data from {from_date.date()} to {to_date.date()}')
    
    # This will test if Kite Connect provides historical data
    historical_data = kite_manager.kite.historical_data(
        instrument_token=nifty_token,
        from_date=from_date,
        to_date=to_date,
        interval="15minute"
    )
    
    if historical_data:
        print(f'   ✅ Historical data available: {len(historical_data)} records')
        print(f'   Sample: {historical_data[0]}')
    else:
        print(f'   ❌ No historical data returned')
        
except Exception as e:
    print(f'   ❌ Historical data API error: {e}')

print('4. Dynamic expiry detection:')
# Check if we can detect actual expiry pattern dynamically
current_expiries = list(set(nifty_expiries))
current_expiries.sort()

print('   Available expiries (next 10):')
for i, expiry in enumerate(current_expiries[:10]):
    expiry_date = datetime.strptime(str(expiry), '%Y-%m-%d')
    weekday = expiry_date.strftime('%A')
    print(f'     {expiry} ({weekday})')

print('5. Recommendation:')
# Check if expiries are old enough for backtesting
today = datetime.now().date()
old_expiries = [exp for exp in current_expiries if exp < today]
future_expiries = [exp for exp in current_expiries if exp >= today]

print(f'   Past expiries: {len(old_expiries)}')
print(f'   Future expiries: {len(future_expiries)}')

if len(old_expiries) == 0:
    print('   ❌ NO HISTORICAL OPTIONS: Cannot backtest old data')
    print('   ✅ RECOMMENDATION: Focus on PAPER TRADING')
else:
    print(f'   ✅ Historical options available for {len(old_expiries)} past dates')
    print('   ✅ RECOMMENDATION: Backtesting possible with limited history')