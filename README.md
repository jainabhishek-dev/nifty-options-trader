# Nifty Options Trader 🚀

**NEWLY ENHANCED:** Enterprise-grade options trading platform with real-time paper trading, virtual money, live market data integration, and fully automated background execution.

## 🚀 Core Features

### 📊 **Real Data Backtesting**
- **Authentic Historical Data**: Uses real market data from Kite Connect API
- **Advanced Strategies**: ATM Straddle, Iron Condor with complete backtesting
- **Professional Metrics**: 15+ performance indicators including Sharpe ratio, max drawdown

### 🤖 **Machine Learning & AI**
- **LSTM Price Prediction**: Advanced neural networks for price forecasting
- **ML Trading Signals**: AI-powered buy/sell recommendations
- **Technical Indicators**: SMA, EMA, RSI, MACD, Bollinger Bands integration

### 💰 **Trading Modes**
- **Paper Trading**: Risk-free testing with virtual capital (₹2,00,000 default)
- **Live Trading**: Automated execution with real money
- **Strategy Automation**: Multi-strategy execution with risk management

### 🛡️ **Risk Management**
- **Real-time Monitoring**: Position tracking and P&L monitoring
- **Advanced Greeks**: Delta, Gamma, Theta, Vega calculations
- **Stop Loss & Targets**: Automated exit strategies

## 🔧 Quick Setup

### Prerequisites
- **Kite Connect Account** (₹500/month plan for historical data)
- **Python 3.13+**
- **Valid API Keys**

### Installation
```bash
1. Clone repository
2. Install dependencies: pip install -r requirements.txt
3. Configure .env file with Kite API keys
4. Start web interface: python web_ui/app.py
5. Navigate to: http://localhost:5000
```

## 📈 Trading Capabilities

### **Backtesting**
- Real historical data from NSE via Kite Connect
- Intraday 15-minute data resolution
- Complete options chain backtesting
- Performance analytics and visualization

### **Paper Trading**
- Live market data with simulated execution
- Configurable virtual capital
- Real-time P&L tracking
- Risk-free strategy testing

### **Live Trading**
- Automated strategy execution
- Market hours compliance
- Real-time order placement
- Position monitoring and management

## 📂 **NEW: Organized Project Structure**

The project has been cleaned up and reorganized for better maintainability:

```
nifty_options_trader/
├── 📁 analytics/          # Analytics and ML models
├── 📁 backtest/          # Backtesting engine
├── 📁 core/              # Core platform components (KiteManager, etc.)
├── 📁 database/          # Database models and clients
├── 📁 paper_trading/     # 🆕 Paper trading engine with virtual money
├── 📁 risk_management/   # Risk management systems
├── 📁 strategies/        # 🆕 Enhanced strategy management
├── 📁 web_ui/           # Professional web dashboard
├── 📁 tests/            # 🆕 Comprehensive test suite
├── 📁 docs/             # 🆕 Documentation
├── 📁 deployment/       # 🆕 Deployment configurations
├── 📁 scripts/          # 🆕 Utility scripts
└── 📁 config/           # Centralized configuration
```

### **🆕 Recent Major Enhancements:**
- ✅ **Paper Trading Engine** - Complete implementation with virtual ₹2 Lakhs
- ✅ **Strategy Manager** - Advanced lifecycle management (BACKTEST/PAPER/LIVE)
- ✅ **Real-time Dashboard** - Professional web interface with live charts
- ✅ **Automated Background Execution** - Runs continuously, even after logout
- ✅ **Comprehensive Testing** - Unit and integration test suites added
- ✅ **Project Organization** - Clean, maintainable structure
