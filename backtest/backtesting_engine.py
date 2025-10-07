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

class MockKiteClient:
    """Mock Kite client for backtesting"""
    
    def __init__(self, historical_data: Dict[str, pd.DataFrame]):
        self.historical_data = historical_data
        self.current_time = datetime.now()
    
    def set_current_time(self, timestamp: datetime):
        """Set current time for simulation"""
        self.current_time = timestamp
    
    def ltp(self, instruments: List[str]) -> Dict[str, Dict[str, float]]:
        """Mock LTP data"""
        result = {}
        for instrument in instruments:
            # Extract symbol from instrument
            symbol = instrument.replace('NFO:', '')
            if symbol in self.historical_data:
                df = self.historical_data[symbol]
                # Get price at current time
                current_data = df[df.index <= self.current_time]
                if not current_data.empty:
                    latest = current_data.iloc[-1]
                    result[instrument] = {'last_price': float(latest['close'])}
                else:
                    # No default value - return None to indicate no data
                    logger.warning(f"⚠️ No historical data available for {instrument}")
                    result[instrument] = None
            else:
                # No historical data available - return None
                logger.warning(f"⚠️ No price data available for {instrument}")
                result[instrument] = None
        return result
    
    def quote(self, instruments: List[str]) -> Dict[str, Dict[str, Any]]:
        """Mock quote data"""
        result = {}
        for instrument in instruments:
            symbol = instrument.replace('NSE:', '').replace('NFO:', '')
            if symbol in self.historical_data:
                df = self.historical_data[symbol]
                current_data = df[df.index <= self.current_time]
                if not current_data.empty:
                    latest = current_data.iloc[-1]
                    result[instrument] = {
                        'last_price': float(latest['close']),
                        'ohlc': {
                            'open': float(latest['open']),
                            'high': float(latest['high']),
                            'low': float(latest['low']),
                            'close': float(latest['close'])
                        },
                        'volume': int(latest.get('volume', 1000)),
                        'oi': int(latest.get('oi', 5000))
                    }
                else:
                    result[instrument] = {
                        'last_price': 100.0,
                        'ohlc': {'open': 100.0, 'high': 105.0, 'low': 95.0, 'close': 100.0},
                        'volume': 1000,
                        'oi': 5000
                    }
            else:
                # Default mock data
                result[instrument] = {
                    'last_price': 100.0,
                    'ohlc': {'open': 100.0, 'high': 105.0, 'low': 95.0, 'close': 100.0},
                    'volume': 1000,
                    'oi': 5000
                }
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
        
        logger.info("🔬 Backtesting Engine initialized")
    
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
            
            # Create mock Kite client
            mock_kite = MockKiteClient(historical_data)
            
            # Create strategy instance
            strategy = self._create_strategy_instance(strategy_name, mock_kite)
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
                    mock_kite.set_current_time(current_time)
                    
                    # Generate signals
                    try:
                        signals = strategy.generate_signals()
                        
                        # Process new signals
                        for signal in signals:
                            if current_capital > 0:
                                trade_result = self._execute_backtest_trade(signal, current_time, mock_kite)
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
                            exit_signal = self._check_exit_conditions(position, current_time, mock_kite)
                            if exit_signal:
                                positions_to_close.append(symbol)
                        
                        # Close positions
                        for symbol in positions_to_close:
                            position = active_positions[symbol]
                            trade = self._close_position(position, current_time, mock_kite)
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
                    trade = self._close_position(position, day_end, mock_kite, "EOD")
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
        """Load historical market data for backtesting"""
        try:
            # For now, generate synthetic data
            # In production, this would load real historical data
            
            data = {}
            
            # Generate Nifty 50 data
            nifty_data = self._generate_nifty_data(start_date, end_date)
            data['NIFTY 50'] = nifty_data
            
            # Generate option data for multiple strikes
            base_price = 25000
            strikes = [base_price + (i * 50) for i in range(-10, 11)]  # 21 strikes
            
            for strike in strikes:
                # CE data
                ce_data = self._generate_option_data(nifty_data, strike, 'CE')
                data[f'NIFTY25O07{strike}CE'] = ce_data
                
                # PE data
                pe_data = self._generate_option_data(nifty_data, strike, 'PE')
                data[f'NIFTY25O07{strike}PE'] = pe_data
            
            logger.info(f"📊 Generated historical data for {len(data)} instruments")
            return data
            
        except Exception as e:
            logger.error(f"❌ Failed to load historical data: {e}")
            return {}
    
    def _generate_nifty_data(self, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Generate realistic Nifty 50 data"""
        try:
            # Create time series
            dates = pd.date_range(start=start_date, end=end_date, freq='15T')
            
            # Filter to market hours (9:15 AM to 3:30 PM)
            market_dates = []
            for date in dates:
                if (date.weekday() < 5 and  # Weekdays only
                    time(9, 15) <= date.time() <= time(15, 30)):  # Market hours
                    market_dates.append(date)
            
            # Generate price data using random walk
            np.random.seed(42)  # For reproducible results
            n_points = len(market_dates)
            
            # Starting price
            start_price = 25000
            
            # Generate returns (mean-reverting random walk)
            returns = np.random.normal(0, 0.002, n_points)  # 0.2% volatility per 15min
            
            # Apply some trend and mean reversion
            prices = [start_price]
            for i in range(1, n_points):
                # Mean reversion factor
                mean_reversion = -0.001 * (prices[-1] - start_price) / start_price
                price_change = (returns[i] + mean_reversion) * prices[-1]
                new_price = prices[-1] + price_change
                prices.append(max(new_price, start_price * 0.8))  # Floor at 20% down
            
            # Create OHLC data
            data = []
            for i, (date, price) in enumerate(zip(market_dates, prices)):
                # Create realistic OHLC from close price
                high_factor = np.random.uniform(1.0, 1.005)
                low_factor = np.random.uniform(0.995, 1.0)
                
                open_price = prices[i-1] if i > 0 else price
                high_price = max(open_price, price) * high_factor
                low_price = min(open_price, price) * low_factor
                close_price = price
                
                data.append({
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price,
                    'volume': np.random.randint(100000, 500000)
                })
            
            df = pd.DataFrame(data, index=market_dates)
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to generate Nifty data: {e}")
            return pd.DataFrame()
    
    def _generate_option_data(self, nifty_data: pd.DataFrame, strike: float, option_type: str) -> pd.DataFrame:
        """Generate realistic option price data"""
        try:
            if nifty_data.empty:
                return pd.DataFrame()
            
            data = []
            
            for timestamp, row in nifty_data.iterrows():
                spot_price = row['close']
                
                # Calculate moneyness
                moneyness = (spot_price - strike) / strike
                
                # Simple option pricing (Black-Scholes approximation)
                time_to_expiry = 7 / 365  # 1 week to expiry
                volatility = 0.15  # 15% volatility
                
                if option_type == 'CE':  # Call
                    intrinsic = max(spot_price - strike, 0)
                    time_value = max(strike * volatility * np.sqrt(time_to_expiry) * 0.4, 1)
                else:  # Put
                    intrinsic = max(strike - spot_price, 0)
                    time_value = max(strike * volatility * np.sqrt(time_to_expiry) * 0.4, 1)
                
                option_price = intrinsic + time_value
                
                # Add some randomness
                option_price *= np.random.uniform(0.95, 1.05)
                option_price = max(option_price, 0.05)  # Minimum 5 paisa
                
                data.append({
                    'open': option_price * np.random.uniform(0.98, 1.02),
                    'high': option_price * np.random.uniform(1.0, 1.1),
                    'low': option_price * np.random.uniform(0.9, 1.0),
                    'close': option_price,
                    'volume': np.random.randint(1000, 10000),
                    'oi': np.random.randint(5000, 50000)
                })
            
            df = pd.DataFrame(data, index=nifty_data.index)
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to generate option data: {e}")
            return pd.DataFrame()
    
    def _create_strategy_instance(self, strategy_name: str, mock_kite) -> Optional[BaseStrategy]:
        """Create strategy instance for backtesting"""
        try:
            # Mock dependencies
            from risk_management.options_risk_manager import OptionsRiskManager
            from utils.market_utils import MarketDataManager
            
            mock_market_data = MarketDataManager(mock_kite)
            mock_risk_manager = OptionsRiskManager(mock_kite, mock_market_data)
            
            # Create strategy instance from registry
            strategy = strategy_registry.create_strategy_instance(
                strategy_name, mock_kite, mock_risk_manager, mock_market_data
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"❌ Failed to create strategy instance: {e}")
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
    
    def _execute_backtest_trade(self, signal: TradeSignal, current_time: datetime, mock_kite) -> bool:
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
    
    def _check_exit_conditions(self, position: Dict, current_time: datetime, mock_kite) -> bool:
        """Check if position should be closed"""
        try:
            signal = position['signal']
            entry_time = position['entry_time']
            entry_price = position['entry_price']
            
            # Get current price
            quotes = mock_kite.quote([f"NFO:{signal.symbol}"])
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
                      mock_kite, exit_reason: str = "SIGNAL") -> Optional[BacktestTrade]:
        """Close position and create trade record"""
        try:
            signal = position['signal']
            entry_time = position['entry_time']
            entry_price = position['entry_price']
            
            # Get current price
            quotes = mock_kite.quote([f"NFO:{signal.symbol}"])
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