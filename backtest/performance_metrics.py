#!/usr/bin/env python3
"""
Performance Metrics and Analysis
Comprehensive performance analysis for trading strategies
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
import os

from .backtesting_engine import BacktestResult, BacktestTrade

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics"""
    # Basic metrics
    total_return: float
    annual_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    
    # Risk metrics
    max_drawdown: float
    avg_drawdown: float
    drawdown_duration: float
    var_95: float  # Value at Risk (95%)
    cvar_95: float  # Conditional VaR (95%)
    
    # Trade metrics
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    
    # Advanced metrics
    information_ratio: float
    treynor_ratio: float
    jensen_alpha: float
    beta: float
    
    # Consistency metrics
    up_months: int
    down_months: int
    monthly_win_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_return': self.total_return,
            'annual_return': self.annual_return,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'max_drawdown': self.max_drawdown,
            'avg_drawdown': self.avg_drawdown,
            'drawdown_duration': self.drawdown_duration,
            'var_95': self.var_95,
            'cvar_95': self.cvar_95,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'largest_win': self.largest_win,
            'largest_loss': self.largest_loss,
            'information_ratio': self.information_ratio,
            'treynor_ratio': self.treynor_ratio,
            'jensen_alpha': self.jensen_alpha,
            'beta': self.beta,
            'up_months': self.up_months,
            'down_months': self.down_months,
            'monthly_win_rate': self.monthly_win_rate
        }

class PerformanceAnalyzer:
    """Advanced performance analysis engine"""
    
    def __init__(self):
        """Initialize performance analyzer"""
        self.charts_dir = "performance_charts"
        os.makedirs(self.charts_dir, exist_ok=True)
        
        logger.info("📊 Performance Analyzer initialized")
    
    def analyze_backtest(self, backtest_result: BacktestResult) -> PerformanceMetrics:
        """Perform comprehensive performance analysis"""
        try:
            logger.info(f"📊 Analyzing performance for {backtest_result.strategy_name}")
            
            # Convert to pandas for easier analysis
            trades_df = self._trades_to_dataframe(backtest_result.trades)
            daily_pnl_df = self._daily_pnl_to_dataframe(backtest_result.daily_pnl)
            
            # Calculate all metrics
            metrics = self._calculate_comprehensive_metrics(
                backtest_result, trades_df, daily_pnl_df
            )
            
            logger.info(f"✅ Performance analysis completed - Sharpe: {metrics.sharpe_ratio:.2f}")
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Performance analysis failed: {e}")
            raise
    
    def _trades_to_dataframe(self, trades: List[BacktestTrade]) -> pd.DataFrame:
        """Convert trades list to DataFrame"""
        try:
            if not trades:
                return pd.DataFrame()
            
            data = []
            for trade in trades:
                data.append({
                    'entry_time': trade.entry_time,
                    'exit_time': trade.exit_time,
                    'symbol': trade.symbol,
                    'action': trade.action,
                    'quantity': trade.quantity,
                    'entry_price': trade.entry_price,
                    'exit_price': trade.exit_price,
                    'pnl': trade.pnl,
                    'pnl_percent': trade.pnl_percent,
                    'holding_period': trade.holding_period_minutes,
                    'exit_reason': trade.exit_reason,
                    'confidence': trade.confidence
                })
            
            df = pd.DataFrame(data)
            df['entry_time'] = pd.to_datetime(df['entry_time'])
            df['exit_time'] = pd.to_datetime(df['exit_time'])
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to convert trades to DataFrame: {e}")
            return pd.DataFrame()
    
    def _daily_pnl_to_dataframe(self, daily_pnl: List[Tuple[datetime, float]]) -> pd.DataFrame:
        """Convert daily P&L to DataFrame"""
        try:
            if not daily_pnl:
                return pd.DataFrame()
            
            data = [{'date': date, 'pnl': pnl} for date, pnl in daily_pnl]
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            # Calculate cumulative returns
            df['cumulative_pnl'] = df['pnl'].cumsum()
            df['returns'] = df['pnl'] / 100000  # Assuming 1L initial capital
            df['cumulative_returns'] = (1 + df['returns']).cumprod()
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to convert daily P&L to DataFrame: {e}")
            return pd.DataFrame()
    
    def _calculate_comprehensive_metrics(self, 
                                       backtest_result: BacktestResult,
                                       trades_df: pd.DataFrame,
                                       daily_pnl_df: pd.DataFrame) -> PerformanceMetrics:
        """Calculate all performance metrics"""
        try:
            # Basic calculations
            initial_capital = backtest_result.initial_capital
            total_days = (backtest_result.end_date - backtest_result.start_date).days
            
            # Return metrics
            total_return = backtest_result.total_return
            annual_return = self._calculate_annual_return(total_return, total_days)
            
            # Risk metrics
            volatility = self._calculate_volatility(daily_pnl_df)
            sharpe_ratio = backtest_result.sharpe_ratio
            sortino_ratio = self._calculate_sortino_ratio(daily_pnl_df)
            calmar_ratio = self._calculate_calmar_ratio(annual_return, backtest_result.max_drawdown)
            
            # Drawdown metrics
            max_drawdown = backtest_result.max_drawdown
            avg_drawdown, drawdown_duration = self._calculate_drawdown_metrics(daily_pnl_df)
            
            # VaR calculations
            var_95, cvar_95 = self._calculate_var_metrics(daily_pnl_df)
            
            # Trade metrics
            win_rate = backtest_result.win_rate
            profit_factor = backtest_result.profit_factor
            avg_win = backtest_result.avg_winning_trade
            avg_loss = abs(backtest_result.avg_losing_trade)
            largest_win = backtest_result.max_winning_trade
            largest_loss = abs(backtest_result.max_losing_trade)
            
            # Advanced metrics
            information_ratio = self._calculate_information_ratio(daily_pnl_df)
            treynor_ratio = self._calculate_treynor_ratio(annual_return, volatility)
            jensen_alpha = self._calculate_jensen_alpha(daily_pnl_df)
            beta = self._calculate_beta(daily_pnl_df)
            
            # Monthly consistency
            up_months, down_months, monthly_win_rate = self._calculate_monthly_consistency(daily_pnl_df)
            
            metrics = PerformanceMetrics(
                total_return=total_return,
                annual_return=annual_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                calmar_ratio=calmar_ratio,
                max_drawdown=max_drawdown,
                avg_drawdown=avg_drawdown,
                drawdown_duration=drawdown_duration,
                var_95=var_95,
                cvar_95=cvar_95,
                win_rate=win_rate,
                profit_factor=profit_factor,
                avg_win=avg_win,
                avg_loss=avg_loss,
                largest_win=largest_win,
                largest_loss=largest_loss,
                information_ratio=information_ratio,
                treynor_ratio=treynor_ratio,
                jensen_alpha=jensen_alpha,
                beta=beta,
                up_months=up_months,
                down_months=down_months,
                monthly_win_rate=monthly_win_rate
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate comprehensive metrics: {e}")
            raise
    
    def _calculate_annual_return(self, total_return: float, total_days: int) -> float:
        """Calculate annualized return"""
        if total_days <= 0:
            return 0.0
        
        years = total_days / 365.0
        if years == 0:
            return total_return
        
        annual_return = ((1 + total_return / 100) ** (1 / years) - 1) * 100
        return annual_return
    
    def _calculate_volatility(self, daily_pnl_df: pd.DataFrame) -> float:
        """Calculate annualized volatility"""
        try:
            if daily_pnl_df.empty or 'returns' not in daily_pnl_df.columns:
                return 0.0
            
            returns = daily_pnl_df['returns'].dropna()
            if len(returns) < 2:
                return 0.0
            
            daily_vol = returns.std()
            annual_vol = daily_vol * np.sqrt(252)  # 252 trading days
            
            return annual_vol * 100
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate volatility: {e}")
            return 0.0
    
    def _calculate_sortino_ratio(self, daily_pnl_df: pd.DataFrame) -> float:
        """Calculate Sortino ratio (return/downside deviation)"""
        try:
            if daily_pnl_df.empty or 'returns' not in daily_pnl_df.columns:
                return 0.0
            
            returns = daily_pnl_df['returns'].dropna()
            if len(returns) < 2:
                return 0.0
            
            excess_returns = returns - 0.0  # Assuming 0% risk-free rate
            downside_returns = excess_returns[excess_returns < 0]
            
            if len(downside_returns) == 0:
                return float('inf') if excess_returns.mean() > 0 else 0.0
            
            downside_deviation = downside_returns.std()
            if downside_deviation == 0:
                return 0.0
            
            sortino = (excess_returns.mean() / downside_deviation) * np.sqrt(252)
            return sortino
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate Sortino ratio: {e}")
            return 0.0
    
    def _calculate_calmar_ratio(self, annual_return: float, max_drawdown: float) -> float:
        """Calculate Calmar ratio (annual return / max drawdown)"""
        try:
            if max_drawdown == 0:
                return float('inf') if annual_return > 0 else 0.0
            
            return annual_return / max_drawdown
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate Calmar ratio: {e}")
            return 0.0
    
    def _calculate_drawdown_metrics(self, daily_pnl_df: pd.DataFrame) -> Tuple[float, float]:
        """Calculate average drawdown and duration"""
        try:
            if daily_pnl_df.empty or 'cumulative_pnl' not in daily_pnl_df.columns:
                return 0.0, 0.0
            
            cumulative = daily_pnl_df['cumulative_pnl']
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max.abs() * 100
            
            # Calculate average drawdown
            negative_drawdowns = drawdown[drawdown < 0]
            avg_drawdown = negative_drawdowns.mean() if len(negative_drawdowns) > 0 else 0.0
            
            # Calculate average drawdown duration
            drawdown_periods = []
            in_drawdown = False
            start_period = 0
            
            for i, dd in enumerate(drawdown):
                if dd < 0 and not in_drawdown:
                    in_drawdown = True
                    start_period = i
                elif dd >= 0 and in_drawdown:
                    in_drawdown = False
                    drawdown_periods.append(i - start_period)
            
            avg_duration = float(np.mean(drawdown_periods)) if drawdown_periods else 0.0
            
            return float(abs(avg_drawdown)), avg_duration
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate drawdown metrics: {e}")
            return 0.0, 0.0
    
    def _calculate_var_metrics(self, daily_pnl_df: pd.DataFrame) -> Tuple[float, float]:
        """Calculate Value at Risk (VaR) and Conditional VaR"""
        try:
            if daily_pnl_df.empty or 'pnl' not in daily_pnl_df.columns:
                return 0.0, 0.0
            
            daily_pnl = daily_pnl_df['pnl'].dropna()
            if len(daily_pnl) < 20:  # Need sufficient data
                return 0.0, 0.0
            
            # 95% VaR (5th percentile of losses)
            var_95 = float(np.percentile(daily_pnl, 5))
            
            # Conditional VaR (expected loss beyond VaR)
            tail_losses = daily_pnl[daily_pnl <= var_95]
            cvar_95 = float(tail_losses.mean()) if len(tail_losses) > 0 else var_95
            
            return abs(var_95), abs(cvar_95)
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate VaR metrics: {e}")
            return 0.0, 0.0
    
    def _calculate_information_ratio(self, daily_pnl_df: pd.DataFrame) -> float:
        """Calculate information ratio (excess return / tracking error)"""
        try:
            if daily_pnl_df.empty or 'returns' not in daily_pnl_df.columns:
                return 0.0
            
            returns = daily_pnl_df['returns'].dropna()
            if len(returns) < 2:
                return 0.0
            
            # Assuming benchmark return is 0% (risk-free rate)
            excess_returns = returns - 0.0
            tracking_error = excess_returns.std()
            
            if tracking_error == 0:
                return 0.0
            
            info_ratio = (excess_returns.mean() / tracking_error) * np.sqrt(252)
            return info_ratio
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate information ratio: {e}")
            return 0.0
    
    def _calculate_treynor_ratio(self, annual_return: float, volatility: float) -> float:
        """Calculate Treynor ratio (simplified as return/volatility)"""
        try:
            if volatility == 0:
                return 0.0
            
            # Simplified Treynor ratio (would need beta for proper calculation)
            return annual_return / volatility
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate Treynor ratio: {e}")
            return 0.0
    
    def _calculate_jensen_alpha(self, daily_pnl_df: pd.DataFrame) -> float:
        """Calculate Jensen's Alpha (simplified)"""
        try:
            if daily_pnl_df.empty or 'returns' not in daily_pnl_df.columns:
                return 0.0
            
            returns = daily_pnl_df['returns'].dropna()
            if len(returns) < 2:
                return 0.0
            
            # Simplified alpha calculation (excess return over risk-free rate)
            risk_free_rate = 0.06 / 252  # 6% annual risk-free rate
            excess_return = returns.mean() - risk_free_rate
            
            return excess_return * 252 * 100  # Annualized percentage
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate Jensen's Alpha: {e}")
            return 0.0
    
    def _calculate_beta(self, daily_pnl_df: pd.DataFrame) -> float:
        """Calculate beta (simplified as 1.0 for options strategies)"""
        try:
            # For options strategies, beta is complex to calculate
            # Returning 1.0 as a placeholder
            return 1.0
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate beta: {e}")
            return 1.0
    
    def _calculate_monthly_consistency(self, daily_pnl_df: pd.DataFrame) -> Tuple[int, int, float]:
        """Calculate monthly performance consistency"""
        try:
            if daily_pnl_df.empty or 'pnl' not in daily_pnl_df.columns:
                return 0, 0, 0.0
            
            # Group by month
            monthly_pnl = daily_pnl_df.groupby(pd.Grouper(freq='M'))['pnl'].sum()
            
            up_months = (monthly_pnl > 0).sum()
            down_months = (monthly_pnl < 0).sum()
            total_months = len(monthly_pnl)
            
            monthly_win_rate = (up_months / total_months) * 100 if total_months > 0 else 0.0
            
            return up_months, down_months, monthly_win_rate
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate monthly consistency: {e}")
            return 0, 0, 0.0
    
    def generate_performance_report(self, backtest_result: BacktestResult, 
                                  metrics: PerformanceMetrics) -> str:
        """Generate comprehensive performance report"""
        try:
            report = f"""
=================================================
PERFORMANCE ANALYSIS REPORT
=================================================

Strategy: {backtest_result.strategy_name}
Period: {backtest_result.start_date.strftime('%Y-%m-%d')} to {backtest_result.end_date.strftime('%Y-%m-%d')}
Initial Capital: ₹{backtest_result.initial_capital:,.2f}
Final Capital: ₹{backtest_result.final_capital:,.2f}

RETURN METRICS
-------------------------------------------------
Total Return: {metrics.total_return:.2f}%
Annualized Return: {metrics.annual_return:.2f}%
Volatility (Annual): {metrics.volatility:.2f}%

RISK-ADJUSTED RETURNS
-------------------------------------------------
Sharpe Ratio: {metrics.sharpe_ratio:.2f}
Sortino Ratio: {metrics.sortino_ratio:.2f}
Calmar Ratio: {metrics.calmar_ratio:.2f}
Information Ratio: {metrics.information_ratio:.2f}

RISK METRICS
-------------------------------------------------
Maximum Drawdown: {metrics.max_drawdown:.2f}%
Average Drawdown: {metrics.avg_drawdown:.2f}%
Drawdown Duration: {metrics.drawdown_duration:.1f} days
VaR (95%): ₹{metrics.var_95:,.2f}
CVaR (95%): ₹{metrics.cvar_95:,.2f}

TRADE ANALYSIS
-------------------------------------------------
Total Trades: {backtest_result.total_trades}
Winning Trades: {backtest_result.winning_trades}
Losing Trades: {backtest_result.losing_trades}
Win Rate: {metrics.win_rate:.2f}%
Profit Factor: {metrics.profit_factor:.2f}

Average Win: ₹{metrics.avg_win:,.2f}
Average Loss: ₹{metrics.avg_loss:,.2f}
Largest Win: ₹{metrics.largest_win:,.2f}
Largest Loss: ₹{metrics.largest_loss:,.2f}

CONSISTENCY METRICS
-------------------------------------------------
Up Months: {metrics.up_months}
Down Months: {metrics.down_months}
Monthly Win Rate: {metrics.monthly_win_rate:.2f}%

=================================================
            """
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Failed to generate performance report: {e}")
            return "Error generating report"
    
    def save_performance_report(self, report: str, strategy_name: str) -> str:
        """Save performance report to file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{strategy_name}_performance_report_{timestamp}.txt"
            filepath = os.path.join(self.charts_dir, filename)
            
            with open(filepath, 'w') as f:
                f.write(report)
            
            logger.info(f"📊 Performance report saved: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Failed to save performance report: {e}")
            return ""

# Export classes
__all__ = ['PerformanceAnalyzer', 'PerformanceMetrics']
