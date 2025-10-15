import sys
sys.path.append('.')
from datetime import datetime, timedelta
from core.kite_manager import KiteManager

print('=== EXPIRY DATE ANALYSIS ===')

kite_manager = KiteManager()
if not kite_manager.instruments:
    kite_manager.load_instruments()

print('1. All NIFTY expiry dates (near current date):')
expiry_dates = set()
for token, instrument in kite_manager.instruments.items():
    if (instrument.get('name') == 'NIFTY' and 
        instrument.get('segment') == 'NFO-OPT'):
        expiry = instrument.get('expiry')
        if expiry and '2025-10' in str(expiry):
            expiry_dates.add(expiry)

for expiry in sorted(expiry_dates):
    expiry_date = datetime.strptime(str(expiry), '%Y-%m-%d')
    weekday = expiry_date.strftime('%A')
    print(f'   {expiry} ({weekday})')

print('2. Checking Oct 2025 Thursdays:')
# Generate all Thursdays in October 2025
oct_2025 = datetime(2025, 10, 1)
current_date = oct_2025
thursdays = []

while current_date.month == 10:
    if current_date.weekday() == 3:  # Thursday
        thursdays.append(current_date)
    current_date += timedelta(days=1)

for thursday in thursdays:
    print(f'   {thursday.strftime("%Y-%m-%d")} ({thursday.strftime("%A")})')
    
    # Check if this Thursday has options available
    thursday_str = thursday.strftime('%Y-%m-%d')
    has_options = any(
        str(inst.get('expiry', '')) == thursday_str 
        for inst in kite_manager.instruments.values() 
        if inst.get('name') == 'NIFTY' and inst.get('segment') == 'NFO-OPT'
    )
    print(f'     Has options: {has_options}')

print('3. For backtesting Oct 14, 2025:')
backtest_date = datetime(2025, 10, 14)
print(f'   Backtest date: {backtest_date.strftime("%A, %B %d, %Y")}')

# Find the next available expiry after backtest date
available_expiries = []
for expiry in sorted(expiry_dates):
    expiry_date = datetime.strptime(str(expiry), '%Y-%m-%d')
    if expiry_date >= backtest_date:
        available_expiries.append(expiry_date)

print('   Available expiries after Oct 14:')
for expiry in available_expiries[:5]:
    weekday = expiry.strftime('%A')
    symbol_format = f"{str(expiry.year)[2:]}{expiry.strftime('%b').upper()[:1]}{expiry.day:02d}"
    print(f'     {expiry.strftime("%Y-%m-%d")} ({weekday}) -> Symbol: {symbol_format}')

print('4. Recommended fix:')
if available_expiries:
    best_expiry = available_expiries[0]
    symbol_format = f"{str(best_expiry.year)[2:]}{best_expiry.strftime('%b').upper()[:1]}{best_expiry.day:02d}"
    print(f'   Use expiry: {best_expiry.strftime("%Y-%m-%d")}')
    print(f'   Symbol format: {symbol_format}')
    print(f'   Example: NIFTY{symbol_format}25300CE')
    
    # Test if this symbol exists
    test_symbol = f'NIFTY{symbol_format}25300CE'
    symbol_exists = any(
        inst.get('tradingsymbol') == test_symbol
        for inst in kite_manager.instruments.values()
    )
    print(f'   Symbol exists: {symbol_exists}')