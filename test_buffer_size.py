"""
Quick verification: Supertrend buffer is capped at 360 candles.
Run from project root: python test_buffer_size.py
"""
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategies.scalping_strategy import ScalpingStrategy, ScalpingConfig


def make_fake_ohlcv(rows: int) -> pd.DataFrame:
    """Build DataFrame with timestamp, open, high, low, close, volume."""
    base = datetime(2025, 2, 24, 9, 15, 0)
    data = []
    for i in range(rows):
        t = base + timedelta(minutes=i)
        o = 24000.0 + i * 2
        c = o + 1.5
        data.append({
            "timestamp": t,
            "open": o,
            "high": max(o, c) + 2,
            "low": min(o, c) - 1,
            "close": c,
            "volume": 1000 + i,
        })
    return pd.DataFrame(data)


def main():
    # Strategy with no Kite/DB (config only)
    config = ScalpingConfig()
    strategy = ScalpingStrategy(config=config, kite_manager=None, order_executor=None)

    # Feed more than 360 candles (400 rows -> 399 closed after dropping last)
    ohlcv_400 = make_fake_ohlcv(400)
    strategy.update_market_data(ohlcv_400)

    n = len(strategy.data_buffer)
    assert n == 360, f"Expected buffer length 360, got {n}"
    print(f"OK: data_buffer has {n} candles (capped at 360)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
