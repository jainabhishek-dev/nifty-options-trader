import sys
sys.path.append('.')
from datetime import datetime
from core.kite_manager import KiteManager

print('=== SYMBOL MATCHING DEBUG ===')

kite_manager = KiteManager()

if not kite_manager.instruments:
    kite_manager.load_instruments()

print('1. Generated symbols:')
nifty_ltp = 25323.55
atm_strike = round(nifty_ltp / 50) * 50
print(f'   ATM Strike: {atm_strike}')

# Our generated expiry format (25O16 for Oct 16)
generated_expiry = '25O16'
generated_ce = f'NIFTY{generated_expiry}{int(atm_strike)}CE'
generated_pe = f'NIFTY{generated_expiry}{int(atm_strike)}PE'

print(f'   Generated CE: {generated_ce}')
print(f'   Generated PE: {generated_pe}')

print('2. Searching for actual NIFTY options near ATM:')
found_options = []
target_strikes = [25250, 25300, 25350]

for token, instrument in kite_manager.instruments.items():
    if (instrument.get('name') == 'NIFTY' and 
        instrument.get('segment') == 'NFO-OPT' and
        instrument.get('strike') in target_strikes):
        found_options.append(instrument)

print(f'   Found {len(found_options)} options near ATM')

for opt in found_options[:10]:
    symbol = opt.get('tradingsymbol', '')
    strike = opt.get('strike', 0)
    expiry = opt.get('expiry', '')
    opt_type = opt.get('instrument_type', '')
    print(f'   {symbol} - Strike: {strike} - Type: {opt_type} - Expiry: {expiry}')

print('3. Looking for exact matches:')
exact_matches = []
for opt in found_options:
    symbol = opt.get('tradingsymbol', '')
    if symbol in [generated_ce, generated_pe]:
        exact_matches.append(opt)
        print(f'   EXACT MATCH: {symbol}')

if len(exact_matches) == 0:
    print('   No exact matches found')
    
    print('4. Checking different expiry formats:')
    # Look for any options with strike 25300
    strike_matches = []
    for token, instrument in kite_manager.instruments.items():
        if (instrument.get('name') == 'NIFTY' and 
            instrument.get('segment') == 'NFO-OPT' and
            instrument.get('strike') == 25300):
            strike_matches.append(instrument)
    
    print(f'   Found {len(strike_matches)} options with strike 25300:')
    for opt in strike_matches[:10]:
        symbol = opt.get('tradingsymbol', '')
        expiry = opt.get('expiry', '')
        opt_type = opt.get('instrument_type', '')
        print(f'     {symbol} - Type: {opt_type} - Expiry: {expiry}')
    
    if len(strike_matches) > 0:
        print('5. Correct symbol pattern analysis:')
        sample_symbol = strike_matches[0].get('tradingsymbol', '')
        print(f'   Sample symbol: {sample_symbol}')
        
        # Extract pattern parts
        if 'NIFTY' in sample_symbol and '25300' in sample_symbol:
            # Find the part between NIFTY and 25300
            nifty_pos = sample_symbol.find('NIFTY') + 5
            strike_pos = sample_symbol.find('25300')
            expiry_part = sample_symbol[nifty_pos:strike_pos]
            print(f'   Expiry part in actual symbol: "{expiry_part}"')
            print(f'   Our generated expiry: "{generated_expiry}"')
            
            if expiry_part != generated_expiry:
                print(f'   ❌ EXPIRY MISMATCH! Need to fix expiry format')
            else:
                print(f'   ✅ Expiry format correct')
else:
    print(f'   ✅ Found {len(exact_matches)} exact matches!')