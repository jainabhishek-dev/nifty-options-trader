import sys
sys.path.append('.')
from core.kite_manager import KiteManager

print('=== INSTRUMENT STRUCTURE DEBUG ===')

kite_manager = KiteManager()

if not kite_manager.instruments:
    kite_manager.load_instruments()

print(f'Total instruments: {len(kite_manager.instruments)}')

print('Sample instrument structures:')
count = 0
for token, instrument in kite_manager.instruments.items():
    if count < 3:
        print(f'Token: {token}')
        print(f'Instrument keys: {list(instrument.keys())}')
        print(f'Sample data: {instrument}')
        print('---')
        count += 1

print('Looking for any NIFTY instruments:')
nifty_count = 0
for token, instrument in kite_manager.instruments.items():
    if 'NIFTY' in str(instrument).upper():
        nifty_count += 1
        if nifty_count <= 5:
            print(f'Found NIFTY: {instrument}')

print(f'Total NIFTY-related instruments: {nifty_count}')

print('Checking different field names:')
field_variations = ['name', 'instrument_name', 'tradingsymbol', 'symbol']
for field in field_variations:
    nifty_with_field = 0
    for token, instrument in kite_manager.instruments.items():
        value = instrument.get(field, '')
        if 'NIFTY' in str(value).upper():
            nifty_with_field += 1
            if nifty_with_field == 1:
                print(f'  Field "{field}": {value} (example)')
    print(f'  Field "{field}": {nifty_with_field} matches')
