# config/settings.py
"""
Core configuration for Nifty Options Trading Platform
Contains all trading parameters, API settings, and risk management rules
"""

import os
from dotenv import load_dotenv
from datetime import datetime, time, timedelta
import pytz
from typing import Dict, List, Tuple

# Load environment variables
load_dotenv()

class TradingConfig:
    """Main trading configuration class"""
    
    # ===================
    # API CONFIGURATION
    # ===================
    KITE_API_KEY = os.getenv('KITE_API_KEY')
    KITE_API_SECRET = os.getenv('KITE_API_SECRET') 
    KITE_ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Supabase Database
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # ===================
    # TRADING MODE
    # ===================
    TRADING_MODE = os.getenv('TRADING_MODE', 'PAPER')  # PAPER or LIVE
    
    # ===================
    # RISK MANAGEMENT
    # ===================
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', 5000))
    TRAILING_STOP_AMOUNT = float(os.getenv('TRAILING_STOP_AMOUNT', 500))
    MAX_POSITIONS = int(os.getenv('MAX_POSITIONS', 5))
    CAPITAL_PER_TRADE = float(os.getenv('CAPITAL_PER_TRADE', 10000))
    
    # Position sizing
    MAX_PORTFOLIO_RISK = 0.02  # 2% max risk per trade
    MAX_DAILY_TRADES = 10      # Maximum trades per day
    
    # ===================
    # NIFTY OPTIONS CONFIG
    # ===================
    NIFTY_SYMBOL = 'NIFTY'
    OPTIONS_EXPIRY_DAYS = int(os.getenv('OPTIONS_EXPIRY_DAYS', 7))
    ATM_RANGE = int(os.getenv('ATM_RANGE', 200))
    
    # Strike selection
    STRIKE_MULTIPLES = [50, 100]  # Nifty strikes are in multiples of 50/100
    MIN_PREMIUM = 5               # Minimum option premium in INR
    MAX_PREMIUM = 200             # Maximum option premium in INR
    
    # ===================
    # MARKET TIMING (IST)
    # ===================
    IST = pytz.timezone('Asia/Kolkata')
    MARKET_OPEN = time(9, 15)     # 9:15 AM IST
    MARKET_CLOSE = time(15, 30)   # 3:30 PM IST
    PRE_MARKET_START = time(9, 0) # 9:00 AM IST
    
    # Trading windows
    MORNING_SESSION = (time(9, 15), time(11, 30))
    AFTERNOON_SESSION = (time(13, 0), time(15, 15))
    AVOID_TRADING_TIMES = [
        (time(11, 30), time(13, 0)),  # Lunch break volatility
        (time(15, 15), time(15, 30))  # Market closing volatility
    ]
    
    # ===================
    # NEWS ANALYSIS CONFIG
    # ===================
    NEWS_FETCH_INTERVAL = 300      # 5 minutes
    NEWS_ANALYSIS_LOOKBACK = 3600  # 1 hour
    NEWS_SENTIMENT_THRESHOLD = 0.6 # Minimum sentiment score for trading
    
    # Nifty 50 constituent keywords for news filtering
    NIFTY50_KEYWORDS = [
        'RELIANCE', 'TCS', 'HDFC BANK', 'INFY', 'ICICI BANK',
        'BHARTI AIRTEL', 'SBI', 'LT', 'ITC', 'HCLTECH',
        'BAJAJ AUTO', 'ASIANPAINT', 'MARUTI', 'TITAN', 'NESTLEIND'
    ]
    
    # ===================
    # AI CONFIGURATION
    # ===================
    GEMINI_MODEL = 'gemini-2.5-flash'
    TEMPERATURE = 0.3              # Lower = more consistent responses
    MAX_TOKENS = 1000              # Response length limit
    
    # News analysis prompt template
    NEWS_ANALYSIS_PROMPT = """
    Analyze the following news and provide trading recommendations:
    
    News: {news_content}
    
    Please provide:
    1. Overall market sentiment (Bullish/Bearish/Neutral)
    2. Impact on Nifty 50 (High/Medium/Low)
    3. Recommended action (CALL/PUT)
    4. Strike selection (ITM/ATM/OTM)
    5. Confidence level (1-10)
    
    Response format:
    Sentiment: [Bullish/Bearish/Neutral]
    Impact: [High/Medium/Low]
    Action: [CALL/PUT]
    Strike: [ITM/ATM/OTM]
    Confidence: [1-10]
    Reason: [Brief explanation]
    """
    
    # ===================
    # LOGGING CONFIG
    # ===================
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE_PATH = 'logs/trading_bot.log'
    MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

class OptionsConfig:
    """Nifty options specific configuration"""
    
    # ===================
    # OPTION TYPES
    # ===================
    CALL = 'CE'
    PUT = 'PE'
    
    # ===================
    # GREEKS THRESHOLDS
    # ===================
    MIN_DELTA = 0.1                # Minimum delta for option selection
    MAX_DELTA = 0.9                # Maximum delta for option selection
    MAX_THETA = -10                # Avoid high time decay options
    MIN_GAMMA = 0.001              # Minimum gamma for momentum plays
    MAX_VEGA = 50                  # Maximum vega exposure
    
    # ===================
    # LIQUIDITY FILTERS
    # ===================
    MIN_VOLUME = 100               # Minimum daily volume
    MIN_OPEN_INTEREST = 1000       # Minimum open interest
    MIN_BID_ASK_RATIO = 0.8        # Minimum bid/ask ratio for liquidity
    
    # ===================
    # MONEYNESS CATEGORIES
    # ===================
    ITM_RANGE = (50, 200)          # In-the-money range (points)
    ATM_RANGE = (-50, 50)          # At-the-money range (points)
    OTM_RANGE = (-200, -50)        # Out-of-the-money range (points)
    
    # ===================
    # TIME DECAY MANAGEMENT
    # ===================
    MIN_DTE = 1                    # Minimum days to expiry
    MAX_DTE = 30                   # Maximum days to expiry
    EXIT_DTE = 1                   # Exit all positions at this DTE
    THETA_DECAY_WARNING = 0.5      # Warning when theta > 50% of premium
    
    # ===================
    # VOLATILITY MANAGEMENT
    # ===================
    MIN_IV = 0.1                   # Minimum implied volatility
    MAX_IV = 0.8                   # Maximum implied volatility
    IV_PERCENTILE_MIN = 20         # Minimum IV percentile for selling
    IV_PERCENTILE_MAX = 80         # Maximum IV percentile for buying

class RiskConfig:
    """Risk management configuration"""
    
    # ===================
    # POSITION SIZING
    # ===================
    MAX_POSITION_SIZE = 0.05       # 5% of portfolio per position
    MAX_SECTOR_EXPOSURE = 0.20     # 20% max exposure to any sector
    MAX_CORRELATION_TRADES = 3     # Max correlated positions
    
    # ===================
    # STOP LOSS RULES
    # ===================
    STOP_LOSS_PERCENTAGE = 0.20    # 20% stop loss
    TRAILING_STOP_TRIGGER = 0.10   # Start trailing at 10% profit
    TRAILING_STOP_DISTANCE = 0.05  # 5% trailing distance
    
    # ===================
    # PROFIT TARGETS
    # ===================
    PROFIT_TARGET_1 = 0.25         # 25% first target
    PROFIT_TARGET_2 = 0.50         # 50% second target
    MAX_PROFIT_TARGET = 1.00       # 100% maximum target
    
    # ===================
    # CIRCUIT BREAKERS
    # ===================
    MAX_CONSECUTIVE_LOSSES = 3     # Stop after 3 consecutive losses
    DAILY_DRAWDOWN_LIMIT = 0.03    # 3% daily drawdown limit
    WEEKLY_DRAWDOWN_LIMIT = 0.10   # 10% weekly drawdown limit
    
    # ===================
    # VOLATILITY FILTERS
    # ===================
    MAX_VIX_LEVEL = 35             # Don't trade if VIX > 35
    MIN_VIX_LEVEL = 12             # Avoid low volatility periods
    VOLATILITY_LOOKBACK = 20       # Days for volatility calculation

# ===================
# VALIDATION FUNCTIONS
# ===================
def validate_config() -> bool:
    """Validate all configuration parameters"""
    errors = []
    
    # Check API keys
    if not TradingConfig.KITE_API_KEY:
        errors.append("KITE_API_KEY is missing")
    if not TradingConfig.KITE_API_SECRET:
        errors.append("KITE_API_SECRET is missing")
    if not TradingConfig.GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY is missing")
    
    # Check numeric ranges
    if TradingConfig.MAX_DAILY_LOSS <= 0:
        errors.append("MAX_DAILY_LOSS must be positive")
    if TradingConfig.TRAILING_STOP_AMOUNT <= 0:
        errors.append("TRAILING_STOP_AMOUNT must be positive")
    if TradingConfig.MAX_POSITIONS <= 0:
        errors.append("MAX_POSITIONS must be positive")
    
    if errors:
        print("❌ Configuration validation failed:")
        for error in errors:
            print(f"  - {error}")
        return False
    
    print("✅ Configuration validation successful")
    return True

def get_trading_session_status() -> str:
    """Get current trading session status"""
    now = datetime.now(TradingConfig.IST).time()
    
    if now < TradingConfig.MARKET_OPEN:
        return "PRE_MARKET"
    elif TradingConfig.MARKET_OPEN <= now < TradingConfig.MARKET_CLOSE:
        return "MARKET_OPEN"
    else:
        return "POST_MARKET"

def is_trading_allowed() -> bool:
    """Check if trading is allowed at current time"""
    session = get_trading_session_status()
    if session != "MARKET_OPEN":
        return False
    
    current_time = datetime.now(TradingConfig.IST).time()
    
    # Check avoid trading times
    for start_time, end_time in TradingConfig.AVOID_TRADING_TIMES:
        if start_time <= current_time <= end_time:
            return False
    
    return True

# ===================
# EXPORT CLASSES
# ===================
__all__ = [
    'TradingConfig',
    'OptionsConfig', 
    'RiskConfig',
    'validate_config',
    'get_trading_session_status',
    'is_trading_allowed'
]
