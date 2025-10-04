# Personal Nifty Options Trading Platform - Rebuild Plan

## 🎯 Project Vision
A Streak-like personal trading platform for Nifty options with backtesting, paper trading, and automated live trading capabilities.

## 📊 Current Status: PHASE 1 - Foundation & Core Architecture

### Files to Keep (Useful Components)
- `config/settings.py` - Configuration management
- `config/trading_params.py` - Trading parameters
- `database/supabase_client.py` - Database connectivity (if working)
- `utils/market_utils.py` - Market data utilities
- `utils/options_utils.py` - Options calculations
- `kite_connect` authentication code
- `requirements.txt` - Dependencies

### Files to Remove (Debug/Test/Unnecessary)
- All `test_*.py` files
- All `debug_*.py` files  
- `desktop_dashboard.py`
- `real_time_dashboard.py` (replace with new clean version)
- `gemini_*.py` files (AI implementation - Phase 5)
- `intelligence/` folder (AI - Phase 5)
- All log files
- Cache files

### New Structure to Create
```
nifty_options_trader/
├── core/                      # Core platform components
│   ├── __init__.py
│   ├── kite_manager.py       # Kite Connect wrapper
│   ├── data_manager.py       # Historical & live data
│   └── portfolio_manager.py  # Portfolio tracking
├── strategies/               # Strategy definitions
│   ├── __init__.py
│   ├── base_strategy.py     # Base strategy class
│   ├── scalping.py          # Scalping strategies
│   └── swing.py             # Swing strategies
├── backtesting/             # Backtesting engine
│   ├── __init__.py
│   ├── engine.py            # Main backtesting engine
│   └── metrics.py           # Performance calculations
├── trading/                 # Live/Paper trading
│   ├── __init__.py
│   ├── paper_trader.py      # Paper trading engine
│   ├── live_trader.py       # Live trading engine
│   └── risk_manager.py      # Risk management
├── web_ui/                  # Web-based dashboard
│   ├── app.py               # Flask/FastAPI app
│   ├── templates/           # HTML templates
│   └── static/              # CSS/JS files
├── config/                  # Configuration (keep existing)
├── database/                # Database models (keep existing)
├── utils/                   # Utilities (keep existing)
└── main.py                  # Main application launcher
```

## 🎯 Phase 1 Goals
1. ✅ Clean workspace structure
2. ✅ Robust Kite Connect integration
3. ✅ Clean database architecture
4. ✅ Basic web dashboard
5. ✅ Foundation for strategy system

## 🚀 Next Steps
1. Clean workspace and create new structure
2. Build core Kite Connect manager
3. Create basic web dashboard
4. Set up database for strategies and trades
5. Build foundation for backtesting engine

## 📝 Success Criteria for Phase 1
- Clean, organized codebase
- Reliable Kite Connect authentication and data
- Working web dashboard showing portfolio
- Database ready for strategy storage
- Clear separation between paper/live trading modes