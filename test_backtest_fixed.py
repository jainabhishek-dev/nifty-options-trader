import sys
sys.path.append('.')
from datetime import datetime, timedelta
from backtest.backtesting_engine import BacktestEngine

print('=== FULL BACKTEST WITH WORKING STRATEGY ===')

engine = BacktestEngine()

# Test with the exact same time we just validated
test_date = datetime(2025, 10, 14, 9, 25, 0)  
end_date = test_date + timedelta(hours=6, minutes=30)  

print(f'Running backtest: {test_date} to {end_date}')

try:
    result = engine.run_backtest('ATM_Straddle', test_date, end_date, 100000)
    
    print(f'BACKTEST RESULTS:')
    print(f'Total trades: {result.total_trades}')
    print(f'Final capital: Rs{result.final_capital:,.2f}')
    print(f'Total return: {result.total_return:.2f}%')
    print(f'Win rate: {result.win_rate:.2f}%')
    
    if result.trades:
        print(f'SUCCESS! Trade details:')
        for i, trade in enumerate(result.trades):
            print(f'  {i+1}. {trade.symbol}: {trade.action}')
            print(f'      Entry: Rs{trade.entry_price} at {trade.entry_time.strftime("%H:%M")}')
            print(f'      Exit: Rs{trade.exit_price} at {trade.exit_time.strftime("%H:%M")}')
            print(f'      P&L: Rs{trade.pnl:.2f} ({trade.pnl_percent:.2f}%)')
    else:
        print('No completed trades yet (may need exit conditions)')

except Exception as e:
    print(f'Backtest error: {e}')
    import traceback
    traceback.print_exc()