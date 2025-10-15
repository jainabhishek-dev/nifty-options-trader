import sys
sys.path.append('.')
from core.kite_manager import KiteManager

print('=== COMPREHENSIVE INSTRUMENT ANALYSIS ===')

kite_manager = KiteManager()

if not kite_manager.instruments:
    kite_manager.load_instruments()

print('1. Available segments:')
segments = set()
for token, instrument in kite_manager.instruments.items():
    segment = instrument.get('segment', 'NO_SEGMENT')
    segments.add(segment)

for seg in sorted(segments):
    count = sum(1 for _, inst in kite_manager.instruments.items() if inst.get('segment') == seg)
    print(f'   {seg}: {count} instruments')

print('\n2. Available instrument types:')
types = set()
for token, instrument in kite_manager.instruments.items():
    inst_type = instrument.get('instrument_type', 'NO_TYPE')
    types.add(inst_type)

for itype in sorted(types):
    count = sum(1 for _, inst in kite_manager.instruments.items() if inst.get('instrument_type') == itype)
    print(f'   {itype}: {count} instruments')

print('\n3. Looking for options (CE/PE) in any segment:')
options_found = 0
for token, instrument in kite_manager.instruments.items():
    inst_type = instrument.get('instrument_type', '')
    if inst_type in ['CE', 'PE']:
        options_found += 1
        if options_found <= 5:
            print(f'   Option {options_found}: {instrument}')

print(f'Total options found: {options_found}')

print('\n4. Looking for instruments with NIFTY in tradingsymbol:')
nifty_symbols = 0
for token, instrument in kite_manager.instruments.items():
    symbol = instrument.get('tradingsymbol', '')
    if 'NIFTY' in symbol and instrument.get('instrument_type') in ['CE', 'PE']:
        nifty_symbols += 1
        if nifty_symbols <= 5:
            print(f'   NIFTY option {nifty_symbols}: {instrument}')

print(f'Total NIFTY options by symbol: {nifty_symbols}')

print('\n5. Sample NSE/NFO instruments:')
nse_nfo_count = 0
for token, instrument in kite_manager.instruments.items():
    exchange = instrument.get('exchange', '')
    segment = instrument.get('segment', '')
    if 'NSE' in exchange or 'NFO' in segment:
        nse_nfo_count += 1
        if nse_nfo_count <= 3:
            print(f'   NSE/NFO {nse_nfo_count}: {instrument}')

print(f'Total NSE/NFO instruments: {nse_nfo_count}')