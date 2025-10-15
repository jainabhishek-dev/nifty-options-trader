#!/usr/bin/env python3
"""
Backtesting Engine for Nifty Options Trading Strategies
Provides historical simulation and performance analysis
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import json
import os

from strategies.base_strategy import BaseStrategy, TradeSignal
from strategies.strategy_registry import strategy_registry
from config.settings import TradingConfig

logger = logging.getLogger(__name__)

@dataclass
class BacktestTrade:
    """Represents a completed backtest trade"""
    entry_time: datetime
    exit_time: datetime
    symbol: str
    action: str
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    pnl_percent: float
    holding_period_minutes: int
    exit_reason: str
    confidence: int

@dataclass 
class BacktestResult:
    """Complete backtest results"""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    avg_winning_trade: float
    avg_losing_trade: float
    max_winning_trade: float
    max_losing_trade: float
    avg_holding_period: float
    trades: List[BacktestTrade]
    daily_pnl: List[Tuple[datetime, float]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        # Convert datetime objects to strings
        result['start_date'] = self.start_date.isoformat()
        result['end_date'] = self.end_date.isoformat() 
        result['trades'] = [
            {
                **asdict(trade),
                'entry_time': trade.entry_time.isoformat(),
                'exit_time': trade.exit_time.isoformat()
            }
            for trade in self.trades
        ]
        result['daily_pnl'] = [
            (date.isoformat(), pnl) for date, pnl in self.daily_pnl
        ]
        return result



class BacktestEngine:
    """Comprehensive backtesting engine"""
    
    def __init__(self):
        """Initialize backtesting engine"""
        self.results_dir = "backtest_results"
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Default parameters
        self.initial_capital = 100000  # ₹1 Lakh
        self.transaction_cost = 20     # ₹20 per trade
        self.slippage_percent = 0.1    # 0.1% slippage
        
        # Register strategies for backtesting
        self._register_strategies()
        
        logger.info("🔬 Backtesting Engine initialized")
    
    def _register_strategies(self):
        """Register all available strategies for backtesting"""
        try:
            from strategies.options_strategy import ATMStraddleStrategy, IronCondorStrategy
            from strategies.strategy_registry import strategy_registry
            
            # Register strategy classes
            success1 = strategy_registry.register_strategy(ATMStraddleStrategy)
            success2 = strategy_registry.register_strategy(IronCondorStrategy)
            
            # Create default strategy configurations for backtesting
            self._create_default_strategy_configs(strategy_registry)
            
            registered_classes = strategy_registry.get_registered_strategy_classes()
            logger.info(f"✅ Strategies registered for backtesting: {registered_classes}")
            
            if not success1 or not success2:
                logger.warning("⚠️ Some strategies failed to register")
            
        except Exception as e:
            logger.error(f"❌ Failed to register strategies: {e}")
            raise  # Re-raise to ensure backtesting fails if strategies can't be registered
    
    def _create_default_strategy_configs(self, strategy_registry):
        """Create default strategy configurations for backtesting"""
        try:
            # ATM Straddle Strategy Configuration
            if not strategy_registry.get_strategy_config('ATM_Straddle'):
                strategy_registry.create_strategy_config(
                    name='ATM_Straddle',
                    description='ATM Straddle strategy for backtesting with 9:20 entry and 15:00 exit',
                    strategy_class='ATMStraddleStrategy',
                    parameters={
                        'entry_time_start': '09:20',
                        'entry_time_end': '14:00',
                        'exit_time': '15:00',
                        'max_loss_percent': 50.0,
                        'profit_target_percent': 100.0,
                        'volatility_threshold': 0.5
                    },
                    author='system'
                )
                logger.info("✅ Created ATM_Straddle config for backtesting")
            
            # Iron Condor Strategy Configuration
            if not strategy_registry.get_strategy_config('Iron_Condor'):
                strategy_registry.create_strategy_config(
                    name='Iron_Condor',
                    description='Iron Condor strategy for backtesting with neutral market conditions',
                    strategy_class='IronCondorStrategy',
                    parameters={
                        'entry_time_start': '09:30',
                        'entry_time_end': '10:30',
                        'exit_time': '15:15',
                        'wing_width': 100,
                        'max_loss_percent': 80.0,
                        'profit_target_percent': 50.0
                    },
                    author='system'
                )
                logger.info("✅ Created Iron_Condor config for backtesting")
                
        except Exception as e:
            logger.error(f"❌ Failed to create default strategy configs: {e}")
    
    def run_backtest(self,
                    strategy_name: str,
                    start_date: datetime,
                    end_date: datetime,
                    initial_capital: float = 100000) -> BacktestResult:
        """Run comprehensive backtest for a strategy"""
        try:
            logger.info(f"🔬 Starting backtest: {strategy_name} ({start_date.date()} to {end_date.date()})")
            
            # Set backtesting parameters
            self.initial_capital = initial_capital
            current_capital = initial_capital
            
            # Load historical data
            historical_data = self._load_historical_data(start_date, end_date)
            if not historical_data:
                raise ValueError("No historical data available")
            
            # Use real KiteManager for backtesting (no mock data)
            from core.kite_manager import KiteManager
            kite_manager = KiteManager()
            
            # Create strategy instance with real KiteManager
            strategy = self._create_strategy_instance(strategy_name, kite_manager)
            if not strategy:
                raise ValueError(f"Strategy '{strategy_name}' not found")
            
            # Initialize tracking variables
            trades: List[BacktestTrade] = []
            daily_pnl: List[Tuple[datetime, float]] = []
            active_positions: Dict[str, Dict] = {}
            
            # Get trading days
            trading_days = self._get_trading_days(start_date, end_date)
            
            # Main backtest loop
            for day in trading_days:
                day_start = datetime.combine(day, time(9, 15))  # Market open
                day_end = datetime.combine(day, time(15, 30))   # Market close
                
                current_time = day_start
                day_pnl = 0.0
                
                # Intraday simulation (15-minute intervals)
                while current_time <= day_end:
                    # Set current time context for strategy (critical for backtesting)
                    if hasattr(strategy, 'set_time_context'):
                        strategy.set_time_context(current_time)
                    
                    # Generate signals
                    try:
                        signals = strategy.generate_signals()
                        
                        # Process new signals
                        for signal in signals:
                            if current_capital > 0:
                                trade_result = self._execute_backtest_trade(signal, current_time, kite_manager)
                                if trade_result:
                                    active_positions[signal.symbol] = {
                                        'signal': signal,
                                        'entry_time': current_time,
                                        'entry_price': signal.entry_price
                                    }
                                    current_capital -= (signal.entry_price * signal.quantity) + self.transaction_cost
                        
                        # Monitor active positions
                        positions_to_close = []
                        for symbol, position in active_positions.items():
                            exit_signal = self._check_exit_conditions(position, current_time, kite_manager)
                            if exit_signal:
                                positions_to_close.append(symbol)
                        
                        # Close positions
                        for symbol in positions_to_close:
                            position = active_positions[symbol]
                            trade = self._close_position(position, current_time, kite_manager)
                            if trade:
                                trades.append(trade)
                                current_capital += (trade.exit_price * trade.quantity) - self.transaction_cost
                                day_pnl += trade.pnl
                            del active_positions[symbol]
                        
                    except Exception as e:
                        logger.error(f"Error in backtest loop: {e}")
                    
                    # Move to next interval
                    current_time += timedelta(minutes=15)
                
                # Close all positions at end of day
                for symbol in list(active_positions.keys()):
                    position = active_positions[symbol]
                    trade = self._close_position(position, day_end, kite_manager, "EOD")
                    if trade:
                        trades.append(trade)
                        current_capital += (trade.exit_price * trade.quantity) - self.transaction_cost
                        day_pnl += trade.pnl
                    del active_positions[symbol]
                
                daily_pnl.append((day, day_pnl))
                logger.debug(f"Day {day.date()}: P&L ₹{day_pnl:,.2f}, Capital: ₹{current_capital:,.2f}")
            
            # Calculate final results
            result = self._calculate_backtest_metrics(
                strategy_name, start_date, end_date, initial_capital, 
                current_capital, trades, daily_pnl
            )
            
            # Save results
            self._save_backtest_results(result)
            
            logger.info(f"✅ Backtest completed: {result.total_trades} trades, {result.total_return:.2f}% return")
            return result
            
        except Exception as e:
            logger.error(f"❌ Backtest failed: {e}")
            raise
    
    def _load_historical_data(self, start_date: datetime, end_date: datetime) -> Dict[str, pd.DataFrame]:
        """Load real historical market data for backtesting from Kite Connect"""
        try:
            if not hasattr(self, 'kite_manager'):
                from core.kite_manager import KiteManager
                self.kite_manager = KiteManager()
            
            if not self.kite_manager.is_authenticated:
                raise ValueError("❌ Kite Connect authentication required for backtesting")
            
            data = {}
            
            # Load real Nifty 50 data
            logger.info(f"📊 Loading Nifty historical data from {start_date} to {end_date}")
            nifty_data = self._load_nifty_historical_data(start_date, end_date)
            
            if nifty_data.empty:
                raise ValueError("❌ No Nifty historical data available for the specified date range")
            
            data['NIFTY 50'] = nifty_data
            
            # Load real options data
            logger.info("📊 Loading options chain historical data...")
            options_data = self._load_options_historical_data(start_date, end_date, nifty_data)
            data.update(options_data)
            
            logger.info(f"✅ Loaded historical data for {len(data)} instruments from Kite Connect")
            return data
            
        except Exception as e:
            logger.error(f"❌ Failed to load historical data: {e}")
            # No fallback - fail fast with real error message
            raise
    
    def _load_nifty_historical_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Load real Nifty 50 historical data from Kite Connect"""
        try:
            nifty_token = '256265'  # NSE:NIFTY 50 token
            
            # Get historical data from Kite
            raw_data = self.kite_manager.get_historical_data(
                instrument_token=nifty_token,
                from_date=start_date,
                to_date=end_date,
                interval='15minute'  # 15-minute intervals for intraday backtesting
            )
            
            if not raw_data:
                raise ValueError("❌ No Nifty historical data returned from Kite Connect")
            
            # Convert to DataFrame
            df = pd.DataFrame(raw_data)
            
            # Ensure required columns exist
            required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_columns):
                raise ValueError(f"❌ Missing required columns in Nifty data: {required_columns}")
            
            # Set date as index
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # Ensure data is sorted by time
            df = df.sort_index()
            
            logger.info(f"✅ Loaded {len(df)} Nifty data points from {df.index[0]} to {df.index[-1]}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to load Nifty historical data: {e}")
            raise
    
    def _load_options_historical_data(self, start_date: datetime, end_date: datetime, nifty_data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Load real options historical data from Kite Connect"""
        try:
            if nifty_data.empty:
                raise ValueError("❌ Nifty data required for options data loading")
            
            # Get current ATM price from Nifty data to determine strike range
            avg_nifty_price = nifty_data['close'].mean()
            base_strike = round(avg_nifty_price / 50) * 50  # Round to nearest 50
            
            # Load instruments to get option tokens
            if not self.kite_manager.instruments:
                self.kite_manager.load_instruments()
            
            options_data = {}
            
            # Get nearby strikes (ATM ± 500 points in 50-point intervals)
            strike_range = 500
            step = 50
            strikes = [base_strike + (i * step) for i in range(-strike_range//step, (strike_range//step)+1)]
            
            # Find current week's expiry
            current_expiry = self._get_current_weekly_expiry(start_date)
            
            loaded_count = 0
            max_options = 20  # Limit to prevent excessive API calls
            
            for strike in strikes[:max_options//2]:  # Limit strikes
                try:
                    # Find CE and PE instruments for this strike
                    ce_symbol, pe_symbol, ce_token, pe_token = self._find_option_instruments(
                        strike, current_expiry
                    )
                    
                    if ce_token and pe_token:
                        # Load CE data
                        ce_data = self._load_option_data(ce_token, start_date, end_date, ce_symbol)
                        if not ce_data.empty:
                            options_data[ce_symbol] = ce_data
                            loaded_count += 1
                        
                        # Load PE data
                        pe_data = self._load_option_data(pe_token, start_date, end_date, pe_symbol)
                        if not pe_data.empty:
                            options_data[pe_symbol] = pe_data
                            loaded_count += 1
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load options data for strike {strike}: {e}")
                    continue
            
            logger.info(f"✅ Loaded {loaded_count} option instruments historical data")
            return options_data
            
        except Exception as e:
            logger.error(f"❌ Failed to load options historical data: {e}")
            # Return empty dict instead of raising - some strategies might work without full options data
            return {}
    
    def _get_current_weekly_expiry(self, reference_date: datetime) -> str:
        """Get current week's expiry date for options"""
        try:
            # Nifty weekly options expire on Thursdays
            days_until_thursday = (3 - reference_date.weekday()) % 7
            if days_until_thursday == 0 and reference_date.hour >= 15:  # After market close on Thursday
                days_until_thursday = 7  # Next Thursday
            
            expiry_date = reference_date + timedelta(days=days_until_thursday)
            
            # Format as DDMMM (e.g., 07NOV, 14NOV)
            month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                          'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
            
            formatted_expiry = f"{expiry_date.day:02d}{month_names[expiry_date.month-1]}"
            return formatted_expiry
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate expiry: {e}")
            # Fallback to a reasonable expiry
            return "07NOV"
    
    def _find_option_instruments(self, strike: int, expiry: str) -> Tuple[str, str, Optional[str], Optional[str]]:
        """Find option instruments for given strike and expiry"""
        try:
            ce_symbol = f"NIFTY25{expiry}{strike}CE"
            pe_symbol = f"NIFTY25{expiry}{strike}PE"
            
            ce_token = None
            pe_token = None
            
            # Search for instruments in loaded instruments
            for instrument in self.kite_manager.instruments.values():
                if (instrument.get('name') == 'NIFTY' and 
                    instrument.get('expiry') and
                    instrument.get('strike') == strike):
                    
                    if instrument.get('instrument_type') == 'CE':
                        ce_token = str(instrument.get('instrument_token'))
                    elif instrument.get('instrument_type') == 'PE':
                        pe_token = str(instrument.get('instrument_token'))
            
            return ce_symbol, pe_symbol, ce_token, pe_token
            
        except Exception as e:
            logger.error(f"❌ Failed to find option instruments for strike {strike}: {e}")
            return "", "", "", ""
    
    def _load_option_data(self, token: str, start_date: datetime, end_date: datetime, symbol: str) -> pd.DataFrame:
        """Load individual option's historical data"""
        try:
            if not token:
                return pd.DataFrame()
            
            raw_data = self.kite_manager.get_historical_data(
                instrument_token=token,
                from_date=start_date,
                to_date=end_date,
                interval='15minute'
            )
            
            if not raw_data:
                return pd.DataFrame()
            
            df = pd.DataFrame(raw_data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df = df.sort_index()
            
            logger.debug(f"✅ Loaded {len(df)} data points for {symbol}")
            return df
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to load data for {symbol}: {e}")
            return pd.DataFrame()
    
    def _create_strategy_instance(self, strategy_name: str, kite_manager) -> Optional[BaseStrategy]:
        """Create strategy instance for backtesting with real KiteManager"""
        try:
            # First ensure strategies are registered
            self._register_strategies()
            
            # Real dependencies (no mock objects)
            from risk_management.options_risk_manager import OptionsRiskManager
            from utils.market_utils import MarketDataManager
            
            market_data = MarketDataManager(kite_manager)
            risk_manager = OptionsRiskManager(kite_manager, market_data)
            
            # Create strategy instance from registry with real managers
            strategy = strategy_registry.create_strategy_instance(
                strategy_name, kite_manager, risk_manager, market_data
            )
            
            if not strategy:
                logger.error(f"❌ Strategy creation failed for '{strategy_name}'")
                # Check what went wrong
                config = strategy_registry.get_strategy_config(strategy_name)
                if config:
                    logger.info(f"Config found: {config.strategy_class}, enabled: {config.enabled}")
                    registered = strategy_registry.get_registered_strategy_classes()
                    logger.info(f"Registered classes: {registered}")
                else:
                    logger.error(f"No config found for strategy '{strategy_name}'")
            
            return strategy
            
        except Exception as e:
            logger.error(f"❌ Failed to create strategy instance: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_trading_days(self, start_date: datetime, end_date: datetime) -> List[datetime]:
        """Get trading days between start and end date"""
        try:
            days = []
            current = start_date
            
            while current <= end_date:
                # Only weekdays (Monday = 0, Sunday = 6)
                if current.weekday() < 5:
                    days.append(current)
                current += timedelta(days=1)
            
            return days
            
        except Exception as e:
            logger.error(f"❌ Failed to get trading days: {e}")
            return []
    
    def _execute_backtest_trade(self, signal: TradeSignal, current_time: datetime, kite_manager) -> bool:
        """Execute trade in backtest"""
        try:
            # Apply slippage
            slippage = signal.entry_price * (self.slippage_percent / 100)
            actual_price = signal.entry_price + slippage
            
            # Update signal with actual price
            signal.entry_price = actual_price
            
            logger.debug(f"🔄 Backtest trade: {signal.symbol} @ ₹{actual_price:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to execute backtest trade: {e}")
            return False
    
    def _check_exit_conditions(self, position: Dict, current_time: datetime, kite_manager) -> bool:
        """Check if position should be closed"""
        try:
            signal = position['signal']
            entry_time = position['entry_time']
            entry_price = position['entry_price']
            
            # Get current price from real KiteManager
            quotes = kite_manager.quote([f"NFO:{signal.symbol}"])
            current_price = quotes.get(f"NFO:{signal.symbol}", {}).get('last_price', entry_price)
            
            # Check stop loss
            if current_price <= signal.stop_loss:
                return True
            
            # Check target
            if current_price >= signal.target:
                return True
            
            # Check time-based exit (holding period > 4 hours)
            holding_period = (current_time - entry_time).total_seconds() / 3600
            if holding_period > 4:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to check exit conditions: {e}")
            return False
    
    def _close_position(self, position: Dict, current_time: datetime, 
                      kite_manager, exit_reason: str = "SIGNAL") -> Optional[BacktestTrade]:
        """Close position and create trade record"""
        try:
            signal = position['signal']
            entry_time = position['entry_time']
            entry_price = position['entry_price']
            
            # Get current price from real KiteManager
            quotes = kite_manager.quote([f"NFO:{signal.symbol}"])
            exit_price = quotes.get(f"NFO:{signal.symbol}", {}).get('last_price', entry_price)
            
            # Apply slippage
            slippage = exit_price * (self.slippage_percent / 100)
            actual_exit_price = exit_price - slippage
            
            # Calculate P&L
            pnl = (actual_exit_price - entry_price) * signal.quantity
            pnl_percent = ((actual_exit_price - entry_price) / entry_price) * 100
            
            # Calculate holding period
            holding_period = int((current_time - entry_time).total_seconds() / 60)
            
            trade = BacktestTrade(
                entry_time=entry_time,
                exit_time=current_time,
                symbol=signal.symbol,
                action=signal.action,
                quantity=signal.quantity,
                entry_price=entry_price,
                exit_price=actual_exit_price,
                pnl=pnl,
                pnl_percent=pnl_percent,
                holding_period_minutes=holding_period,
                exit_reason=exit_reason,
                confidence=signal.confidence
            )
            
            return trade
            
        except Exception as e:
            logger.error(f"❌ Failed to close position: {e}")
            return None
    
    def _calculate_backtest_metrics(self, strategy_name: str, start_date: datetime, 
                                  end_date: datetime, initial_capital: float, 
                                  final_capital: float, trades: List[BacktestTrade],
                                  daily_pnl: List[Tuple[datetime, float]]) -> BacktestResult:
        """Calculate comprehensive backtest metrics"""
        try:
            total_trades = len(trades)
            if total_trades == 0:
                # Return empty result if no trades
                return BacktestResult(
                    strategy_name=strategy_name,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=initial_capital,
                    final_capital=initial_capital,
                    total_trades=0,
                    winning_trades=0,
                    losing_trades=0,
                    win_rate=0.0,
                    total_pnl=0.0,
                    total_return=0.0,
                    max_drawdown=0.0,
                    sharpe_ratio=0.0,
                    profit_factor=0.0,
                    avg_winning_trade=0.0,
                    avg_losing_trade=0.0,
                    max_winning_trade=0.0,
                    max_losing_trade=0.0,
                    avg_holding_period=0.0,
                    trades=[],
                    daily_pnl=daily_pnl
                )
            
            # Basic metrics
            winning_trades = [t for t in trades if t.pnl > 0]
            losing_trades = [t for t in trades if t.pnl < 0]
            
            total_pnl = sum(t.pnl for t in trades)
            total_return = ((final_capital - initial_capital) / initial_capital) * 100
            
            # Win rate
            win_rate = (len(winning_trades) / total_trades) * 100
            
            # Average trades
            avg_winning_trade = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_losing_trade = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0
            
            # Max trades
            max_winning_trade = max((t.pnl for t in winning_trades), default=0)
            max_losing_trade = min((t.pnl for t in losing_trades), default=0)
            
            # Profit factor
            gross_profit = sum(t.pnl for t in winning_trades)
            gross_loss = abs(sum(t.pnl for t in losing_trades))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            
            # Average holding period
            avg_holding_period = sum(t.holding_period_minutes for t in trades) / total_trades
            
            # Calculate drawdown
            max_drawdown = self._calculate_max_drawdown(daily_pnl)
            
            # Calculate Sharpe ratio
            sharpe_ratio = self._calculate_sharpe_ratio(daily_pnl)
            
            result = BacktestResult(
                strategy_name=strategy_name,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                final_capital=final_capital,
                total_trades=total_trades,
                winning_trades=len(winning_trades),
                losing_trades=len(losing_trades),
                win_rate=win_rate,
                total_pnl=total_pnl,
                total_return=total_return,
                max_drawdown=max_drawdown,
                sharpe_ratio=sharpe_ratio,
                profit_factor=profit_factor,
                avg_winning_trade=avg_winning_trade,
                avg_losing_trade=avg_losing_trade,
                max_winning_trade=max_winning_trade,
                max_losing_trade=max_losing_trade,
                avg_holding_period=avg_holding_period,
                trades=trades,
                daily_pnl=daily_pnl
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate backtest metrics: {e}")
            raise
    
    def _calculate_max_drawdown(self, daily_pnl: List[Tuple[datetime, float]]) -> float:
        """Calculate maximum drawdown"""
        try:
            if not daily_pnl:
                return 0.0
            
            cumulative = 0.0
            peak = 0.0
            max_dd = 0.0
            
            for _, pnl in daily_pnl:
                cumulative += pnl
                if cumulative > peak:
                    peak = cumulative
                drawdown = (peak - cumulative) / max(peak, 1) * 100
                max_dd = max(max_dd, drawdown)
            
            return max_dd
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate drawdown: {e}")
            return 0.0
    
    def _calculate_sharpe_ratio(self, daily_pnl: List[Tuple[datetime, float]]) -> float:
        """Calculate Sharpe ratio"""
        try:
            if len(daily_pnl) < 2:
                return 0.0
            
            daily_returns = [pnl for _, pnl in daily_pnl]
            avg_return = sum(daily_returns) / len(daily_returns)
            
            # Calculate standard deviation
            variance = sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)
            std_dev = np.sqrt(variance)
            
            if std_dev == 0:
                return 0.0
            
            # Annualize (assuming 252 trading days)
            sharpe = (avg_return / std_dev) * np.sqrt(252)
            return sharpe
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate Sharpe ratio: {e}")
            return 0.0
    
    def _save_backtest_results(self, result: BacktestResult) -> None:
        """Save backtest results to file"""
        try:
            filename = f"{result.strategy_name}_{result.start_date.strftime('%Y%m%d')}_{result.end_date.strftime('%Y%m%d')}.json"
            filepath = os.path.join(self.results_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)
            
            logger.info(f"💾 Backtest results saved: {filepath}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save backtest results: {e}")
    
    def load_backtest_results(self, filename: str) -> Optional[BacktestResult]:
        """Load backtest results from file"""
        try:
            filepath = os.path.join(self.results_dir, filename)
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Convert back to BacktestResult
            # This is simplified - in production, you'd want proper deserialization
            logger.info(f"📊 Loaded backtest results: {filename}")
            return data  # Return dict for now
            
        except Exception as e:
            logger.error(f"❌ Failed to load backtest results: {e}")
            return None

# Export classes
__all__ = ['BacktestEngine', 'BacktestResult', 'BacktestTrade']