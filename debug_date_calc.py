from datetime import datetime, timedelta

# Test the date calculation
test_date = datetime(2025, 10, 14)  # Monday Oct 14, 2025
print(f'Test date: {test_date.strftime("%A, %B %d, %Y")} (weekday: {test_date.weekday()})')

# Find next Thursday
days_ahead = 3 - test_date.weekday()  # Thursday is 3
if days_ahead <= 0:  # Target day already happened this week
    days_ahead += 7

next_thursday = test_date + timedelta(days_ahead)
print(f'Next Thursday: {next_thursday.strftime("%A, %B %d, %Y")} (weekday: {next_thursday.weekday()})')

# From the debug, actual expiry is Oct 20
actual_expiry = datetime(2025, 10, 20)
print(f'Actual expiry: {actual_expiry.strftime("%A, %B %d, %Y")} (weekday: {actual_expiry.weekday()})')

# Check what day Oct 20 is
print(f'Oct 20 is a {actual_expiry.strftime("%A")}')

# The issue might be that we need the NEXT weekly expiry, not this week's
print('\nChecking weekly expiry pattern:')
print('Oct 17 (Thursday) - Current week')
print('Oct 20 (Sunday) - This seems wrong...')

# Let me check if Oct 17 has options
print('\nLet me check different Thursday dates:')
dates_to_check = [
    datetime(2025, 10, 16),  # Wednesday
    datetime(2025, 10, 17),  # Thursday 
    datetime(2025, 10, 20),  # Sunday (from debug)
    datetime(2025, 10, 24),  # Thursday next week
]

for date in dates_to_check:
    year = str(date.year)[2:]
    month_abbr = date.strftime('%b').upper()[:1]
    day = f"{date.day:02d}"
    format_result = f"{year}{month_abbr}{day}"
    print(f'{date.strftime("%A, %B %d")}: {format_result}')