#!/usr/bin/env python3
# main.py
"""
Main Orchestration System for Nifty Options Trading Platform
Coordinates AI analysis, strategy execution, risk management, and order placement
"""

import logging
import sys
import time
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from threading import Thread, Event
import schedule

# Import core modules
from config.settings import TradingConfig, validate_config, is_trading_allowed, get_trading_session_status
from auth_handler import KiteAuthenticator
from intelligence.gemini_client import GeminiNewsAnalyzer, NewsAnalysisResult
from strategies.news_sentiment_strategy import NewsSentimentStrategy
from strategies.base_strategy import TradeSignal, OrderResult
from risk_management.options_risk_manager import OptionsRiskManager
from utils.logging_config import setup_logging
from utils.market_utils import MarketDataManager
from database.models import TradeRecord, AnalysisRecord
from database.supabase_client import DatabaseManager

# Setup logging
logger = setup_logging()

class NiftyOptionsTradingBot:
    """Main trading bot orchestrator"""
    
    def __init__(self):
        """Initialize the trading bot with all components"""
        logger.info("🚀 Initializing Nifty Options Trading Bot...")
        
        # Validate configuration
        if not validate_config():
            raise RuntimeError("❌ Configuration validation failed")
        
        # Initialize core components
        self.shutdown_event = Event()
        self.trading_active = False
        
        # Initialize services (will be set in initialize_services)
        self.authenticator: Optional[KiteAuthenticator] = None
        self.ai_analyzer: Optional[GeminiNewsAnalyzer] = None
        self.strategy: Optional[NewsSentimentStrategy] = None
        self.risk_manager: Optional[OptionsRiskManager] = None
        self.market_data: Optional[MarketDataManager] = None
        self.database: Optional[DatabaseManager] = None
        
        # Trading state
        self.daily_pnl = 0.0
        self.position_count = 0
        self.consecutive_losses = 0
        
        # Performance tracking
        self.session_start_time = datetime.now()
        self.total_trades = 0
        self.successful_trades = 0
        
        logger.info("✅ Trading bot initialized")
    
    def initialize_services(self) -> bool:
        """Initialize all trading services"""
        try:
            logger.info("🔧 Initializing trading services...")
            
            # 1. Initialize authenticator
            logger.info("📡 Setting up Kite Connect...")
            self.authenticator = KiteAuthenticator()
            
            # 2. Initialize AI analyzer
            logger.info("🧠 Setting up AI analysis engine...")
            self.ai_analyzer = GeminiNewsAnalyzer()
            logger.info("✅ Gemini AI analyzer ready")
            
            # 3. Initialize market data manager
            logger.info("📊 Setting up market data...")
            self.market_data = MarketDataManager(self.authenticator.kite)
            
            # 4. Initialize risk manager
            logger.info("🛡️ Setting up risk management...")
            self.risk_manager = OptionsRiskManager(self.authenticator.kite, self.market_data)
            
            # 5. Initialize trading strategy
            logger.info("📈 Setting up trading strategy...")
            self.strategy = NewsSentimentStrategy(
                kite_client=self.authenticator.kite,
                ai_analyzer=self.ai_analyzer,
                risk_manager=self.risk_manager,
                market_data=self.market_data
            )
            
            # 6. Initialize database (if configured)
            if TradingConfig.SUPABASE_URL and TradingConfig.SUPABASE_KEY:
                logger.info("💾 Setting up database connection...")
                self.database = DatabaseManager()
            else:
                logger.warning("⚠️ Database not configured - using local logging only")
            
            logger.info("✅ All services initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Service initialization failed: {e}")
            return False
    
    def start_trading(self) -> None:
        """Start the main trading loop"""
        logger.info("🎯 Starting trading system...")
        
        if not self.initialize_services():
            logger.error("❌ Cannot start trading - service initialization failed")
            return
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Schedule analysis cycles
        self._schedule_trading_activities()
        
        # Start main loop
        self.trading_active = True
        logger.info("🔄 Trading loop started - Press Ctrl+C to stop")
        
        try:
            while self.trading_active and not self.shutdown_event.is_set():
                # Run scheduled activities
                schedule.run_pending()
                
                # Check system health
                self._monitor_system_health()
                
                # Sleep before next iteration
                time.sleep(10)  # Check every 10 seconds
                
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested by user")
        except Exception as e:
            logger.error(f"❌ Trading loop error: {e}")
        finally:
            self._shutdown_gracefully()
    
    def _schedule_trading_activities(self) -> None:
        """Schedule all trading activities"""
        logger.info("📅 Setting up trading schedule...")
        
        # News analysis every 5 minutes during market hours
        schedule.every(5).minutes.do(self._run_news_analysis_cycle)
        
        # Risk monitoring every minute
        schedule.every(1).minutes.do(self._monitor_positions)
        
        # Market data refresh every 30 seconds
        schedule.every(30).seconds.do(self._refresh_market_data)
        
        # Daily cleanup at market close
        schedule.every().day.at("15:35").do(self._daily_cleanup)
        
        # System health check every 10 minutes
        schedule.every(10).minutes.do(self._system_health_check)
        
        logger.info("✅ Trading schedule configured")
    
    def _run_news_analysis_cycle(self) -> None:
        """Execute a complete news analysis and trading cycle"""
        try:
            # Only run during market hours
            if not is_trading_allowed():
                logger.debug("⏸️ Trading not allowed at this time")
                return
            
            logger.info("📰 Starting news analysis cycle...")
            
            # Check if AI analyzer is available
            if not self.ai_analyzer:
                logger.error("❌ AI analyzer not initialized")
                return
            
            # Get AI analysis (10-point signals)
            analysis_results = self.ai_analyzer.get_nifty50_news_analysis()
            
            if not analysis_results:
                logger.warning("⚠️ No analysis results received")
                return
            
            # Log analysis to database
            if self.database:
                self._save_analysis_to_db(analysis_results)
            
            # Execute trading strategy
            if not self.strategy:
                logger.error("❌ Trading strategy not initialized")
                return
            
            trade_signals = self.strategy.process_analysis_results(analysis_results)
            
            if trade_signals:
                logger.info(f"📋 Generated {len(trade_signals)} trade signals")
                self._execute_trade_signals(trade_signals)
            else:
                logger.info("ℹ️ No actionable trade signals generated")
            
        except Exception as e:
            logger.error(f"❌ News analysis cycle failed: {e}")
    
    def _execute_trade_signals(self, trade_signals: List[TradeSignal]) -> None:
        """Execute trade signals with risk management"""
        for signal in trade_signals:
            try:
                # Check if services are available
                if not self.risk_manager or not self.strategy:
                    logger.error("❌ Required services not initialized")
                    continue
                
                # Check risk limits (convert TradeSignal to dict)
                signal_dict = {
                    'symbol': signal.symbol,
                    'action': signal.action,
                    'quantity': signal.quantity,
                    'entry_price': signal.entry_price,
                    'confidence': signal.confidence
                }
                if not self.risk_manager.can_place_new_trade(signal_dict):
                    logger.warning(f"🚫 Trade blocked by risk management: {signal.symbol}")
                    continue
                
                # Execute the trade
                trade_result = self.strategy.execute_trade(signal)
                
                if trade_result:
                    self.total_trades += 1
                    self.position_count += 1
                    
                    # Handle different return types from execute_trade
                    status = None
                    if hasattr(trade_result, 'status'):
                        status = trade_result.status
                    elif isinstance(trade_result, dict):
                        status = trade_result.get('status')
                    
                    if status == 'SUCCESS':
                        self.successful_trades += 1
                        logger.info(f"✅ Trade executed: {trade_result}")
                    else:
                        logger.warning(f"⚠️ Trade failed: {trade_result}")
                    
                    # Save trade to database
                    if self.database:
                        self._save_trade_to_db(trade_result)
                
            except Exception as e:
                logger.error(f"❌ Failed to execute trade signal: {e}")
    
    def _monitor_positions(self) -> None:
        """Monitor existing positions and manage risk"""
        try:
            if self.position_count == 0:
                return  # No positions to monitor
            
            # Check if authenticator is available
            if not self.authenticator or not self.authenticator.kite:
                logger.error("❌ Authenticator not initialized")
                return
            
            # Get current positions
            positions = self.authenticator.kite.positions()
            
            if not isinstance(positions, dict):
                return
            
            net_positions = positions.get('net', [])
            
            if not net_positions:
                self.position_count = 0
                return
            
            # Update position count
            active_positions = [p for p in net_positions if isinstance(p, dict) and p.get('quantity', 0) != 0]
            self.position_count = len(active_positions)
            
            # Monitor each position
            if self.risk_manager:
                for position in active_positions:
                    self.risk_manager.monitor_position(position)
            
            # Update daily P&L
            total_pnl = sum(float(p.get('pnl', 0)) for p in active_positions if isinstance(p, dict))
            self.daily_pnl = total_pnl
            
            # Check daily loss limits
            if self.daily_pnl < -TradingConfig.MAX_DAILY_LOSS:
                logger.error(f"🚨 Daily loss limit exceeded: ₹{self.daily_pnl:,.2f}")
                self._emergency_exit_all_positions()
            
        except Exception as e:
            logger.error(f"❌ Position monitoring failed: {e}")
    
    def _refresh_market_data(self) -> None:
        """Refresh market data for decision making"""
        try:
            if self.market_data:
                self.market_data.refresh_data()
        except Exception as e:
            logger.error(f"❌ Market data refresh failed: {e}")
    
    def _daily_cleanup(self) -> None:
        """Perform daily cleanup tasks"""
        try:
            logger.info("🧹 Performing daily cleanup...")
            
            # Print daily summary
            self._print_daily_summary()
            
            # Reset daily counters
            self.daily_pnl = 0.0
            self.total_trades = 0
            self.successful_trades = 0
            self.consecutive_losses = 0
            
            # Close any remaining positions if configured
            if TradingConfig.TRADING_MODE == 'PAPER':  # Only in paper mode for safety
                self._close_eod_positions()
            
        except Exception as e:
            logger.error(f"❌ Daily cleanup failed: {e}")
    
    def _system_health_check(self) -> None:
        """Perform system health checks"""
        try:
            # Check if authenticator is available
            if not self.authenticator or not self.authenticator.kite:
                logger.warning("⚠️ Authenticator not available for health check")
                return
            
            # Check API connectivity
            profile = self.authenticator.kite.profile()
            
            # Check AI service
            if self.ai_analyzer and hasattr(self.ai_analyzer, 'model') and self.ai_analyzer.model:
                logger.debug("✅ AI analyzer is ready")
            else:
                logger.warning("⚠️ AI analyzer not available")
            
            # Log system status
            logger.debug("💚 System health check passed")
            
        except Exception as e:
            logger.error(f"❌ System health check failed: {e}")
    
    def _monitor_system_health(self) -> None:
        """Monitor overall system health during trading"""
        try:
            # Check memory usage, connection status, etc.
            session_duration = datetime.now() - self.session_start_time
            
            if session_duration.seconds > 0 and session_duration.seconds % 3600 == 0:  # Every hour
                success_rate = (self.successful_trades / max(1, self.total_trades)) * 100
                logger.info(f"📊 Hourly Stats - Trades: {self.total_trades}, Success: {success_rate:.1f}%, P&L: ₹{self.daily_pnl:,.2f}")
            
        except Exception as e:
            logger.debug(f"System health monitoring error: {e}")
    
    def _emergency_exit_all_positions(self) -> None:
        """Emergency exit all positions"""
        logger.error("🚨 EMERGENCY EXIT - Closing all positions")
        try:
            if self.strategy:
                self.strategy.close_all_positions()
            self.position_count = 0
            self.trading_active = False
        except Exception as e:
            logger.error(f"❌ Emergency exit failed: {e}")
    
    def _close_eod_positions(self) -> None:
        """Close end-of-day positions"""
        logger.info("🌅 Closing end-of-day positions...")
        try:
            if self.strategy:
                self.strategy.close_eod_positions()
        except Exception as e:
            logger.error(f"❌ EOD position closure failed: {e}")
    
    def _save_analysis_to_db(self, analysis_results: List[NewsAnalysisResult]) -> None:
        """Save analysis results to database"""
        try:
            if not self.database:
                logger.debug("Database not available for saving analysis")
                return
            
            for result in analysis_results:
                analysis_record = AnalysisRecord(
                    timestamp=result.timestamp,
                    sentiment=result.sentiment,
                    impact=result.impact,  # Map impact field
                    action=result.action,
                    strike_type=result.strike_type,  # Map strike_type field
                    confidence=result.confidence,
                    reason=result.reason,
                    nifty_level=float(self.market_data.get_nifty_ltp()) if hasattr(self, 'market_data') and self.market_data else 0.0,
                    used_for_trade=False,  # Will be updated when trade is executed
                    trading_mode=TradingConfig.TRADING_MODE  # Set current trading mode
                )
                self.database.save_analysis(analysis_record)
        except Exception as e:
            logger.error(f"❌ Failed to save analysis to database: {e}")
    
    def _save_trade_to_db(self, trade_result: Any) -> None:
        """Save trade result to database"""
        try:
            if not self.database:
                logger.debug("Database not available for saving trade")
                return
            
            # Convert trade result to dictionary if needed
            if hasattr(trade_result, 'to_dict'):
                trade_dict = trade_result.to_dict()
            elif isinstance(trade_result, dict):
                trade_dict = trade_result
            else:
                logger.warning(f"Unknown trade result type: {type(trade_result)}")
                return
            
            # Ensure trading mode is set
            trade_dict['trading_mode'] = TradingConfig.TRADING_MODE
            
            trade_record = TradeRecord.from_dict(trade_dict)
            self.database.save_trade(trade_record)
        except Exception as e:
            logger.error(f"❌ Failed to save trade to database: {e}")
    
    def _print_daily_summary(self) -> None:
        """Print daily trading summary"""
        success_rate = (self.successful_trades / max(1, self.total_trades)) * 100
        session_duration = datetime.now() - self.session_start_time
        
        logger.info("📊 DAILY TRADING SUMMARY")
        logger.info("=" * 40)
        logger.info(f"Trading Mode: {TradingConfig.TRADING_MODE}")
        logger.info(f"Session Duration: {session_duration}")
        logger.info(f"Total Trades: {self.total_trades}")
        logger.info(f"Successful Trades: {self.successful_trades}")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        logger.info(f"Daily P&L: ₹{self.daily_pnl:,.2f}")
        logger.info(f"Active Positions: {self.position_count}")
        logger.info("=" * 40)
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals"""
        logger.info(f"🛑 Received shutdown signal: {signum}")
        self.shutdown_event.set()
        self.trading_active = False
    
    def _shutdown_gracefully(self) -> None:
        """Gracefully shutdown the trading system"""
        logger.info("🛑 Shutting down trading system...")
        
        try:
            # Stop trading activities
            self.trading_active = False
            
            # Print final summary
            self._print_daily_summary()
            
            # Close database connections
            if self.database:
                self.database.close()
            
            logger.info("✅ Trading system shutdown complete")
            
        except Exception as e:
            logger.error(f"❌ Shutdown error: {e}")

def main():
    """Main entry point"""
    print("🚀 Nifty Options Trading Platform")
    print("=" * 50)
    
    try:
        # Create and start trading bot
        bot = NiftyOptionsTradingBot()
        
        # Check market status
        session_status = get_trading_session_status()
        logger.info(f"📅 Market Status: {session_status}")
        
        if session_status == "PRE_MARKET":
            logger.info("⏰ Market not open yet - system will activate when market opens")
        elif session_status == "POST_MARKET":
            logger.info("🌅 Market closed - system will activate next trading day")
        
        # Start the trading system
        bot.start_trading()
        
    except KeyboardInterrupt:
        logger.info("👋 Trading system stopped by user")
    except Exception as e:
        logger.error(f"❌ Trading system failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
