import sys
sys.path.append('.')
from core.kite_manager import KiteManager

print('=== NIFTY OPTIONS SPECIFIC DEBUG ===')

kite_manager = KiteManager()

if not kite_manager.instruments:
    kite_manager.load_instruments()

print('Looking for actual NIFTY options...')

# Search for NIFTY options in NFO segment
nifty_options = []
for token, instrument in kite_manager.instruments.items():
    name = instrument.get('name', '')
    segment = instrument.get('segment', '')
    instrument_type = instrument.get('instrument_type', '')
    
    # Look for exact NIFTY name in NFO segment with CE/PE types
    if (name == 'NIFTY' and 
        segment == 'NFO' and 
        instrument_type in ['CE', 'PE']):
        nifty_options.append(instrument)

print(f'Found {len(nifty_options)} NIFTY options')

if len(nifty_options) > 0:
    print('Sample NIFTY options:')
    for i, opt in enumerate(nifty_options[:10]):
        symbol = opt.get('tradingsymbol', 'N/A')
        strike = opt.get('strike', 0)
        expiry = opt.get('expiry', 'N/A')
        opt_type = opt.get('instrument_type', 'N/A')
        print(f'  {i+1}. {symbol} - Strike: {strike} - Type: {opt_type} - Expiry: {expiry}')
    
    print('Current week ATM strikes (25200-25400):')
    current_week = []
    for opt in nifty_options:
        strike = opt.get('strike', 0)
        expiry = opt.get('expiry', '')
        symbol = opt.get('tradingsymbol', '')
        
        # Check for current week (Oct 17, 2025 is Thursday)
        if (strike >= 25200 and strike <= 25400 and 
            str(expiry) == '2025-10-17'):
            current_week.append(opt)
            print(f'    {symbol} - Strike: {strike} - Expiry: {expiry}')
    
    print(f'Current week options found: {len(current_week)}')
else:
    print('No NIFTY options found. Checking alternatives...')
    
    # Check different name patterns
    name_patterns = ['NIFTY', 'NIFTY 50', 'NIFTY50']
    for pattern in name_patterns:
        count = 0
        for token, instrument in kite_manager.instruments.items():
            if (instrument.get('name', '') == pattern and 
                instrument.get('segment', '') == 'NFO'):
                count += 1
                if count == 1:
                    print(f'Found with name "{pattern}": {instrument}')
        print(f'Pattern "{pattern}": {count} matches')
