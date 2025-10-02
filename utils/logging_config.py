# utils/logging_config.py
"""
Centralized logging configuration for the trading platform
Provides structured logging with file rotation and performance monitoring
"""

import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional
from config.settings import TradingConfig

def setup_logging(
    log_level: str = TradingConfig.LOG_LEVEL,
    log_file: Optional[str] = None,
    console_output: bool = True
) -> logging.Logger:
    """
    Setup comprehensive logging for the trading platform
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path (defaults to config setting)
        console_output: Whether to log to console
    
    Returns:
        Configured logger instance
    """
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(TradingConfig.LOG_FILE_PATH)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Clear any existing handlers
    logging.getLogger().handlers.clear()
    
    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Create formatter
    formatter = logging.Formatter(
        fmt=TradingConfig.LOG_FORMAT,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler with rotation
    log_file_path = log_file or TradingConfig.LOG_FILE_PATH
    if log_file_path:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file_path,
            maxBytes=TradingConfig.MAX_LOG_SIZE,
            backupCount=TradingConfig.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Add trading-specific logger
    trading_logger = logging.getLogger('trading_bot')
    
    # Performance logger for timing analysis
    perf_logger = logging.getLogger('performance')
    perf_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'performance.log'),
        maxBytes=TradingConfig.MAX_LOG_SIZE // 2,
        backupCount=3,
        encoding='utf-8'
    )
    perf_formatter = logging.Formatter('%(asctime)s - %(message)s')
    perf_handler.setFormatter(perf_formatter)
    perf_logger.addHandler(perf_handler)
    perf_logger.setLevel(logging.INFO)
    
    # Trade logger for detailed trade records
    trade_logger = logging.getLogger('trades')
    trade_handler = logging.handlers.RotatingFileHandler(
        filename=os.path.join(log_dir, 'trades.log'),
        maxBytes=TradingConfig.MAX_LOG_SIZE,
        backupCount=TradingConfig.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    trade_formatter = logging.Formatter('%(asctime)s - %(message)s')
    trade_handler.setFormatter(trade_formatter)
    trade_logger.addHandler(trade_handler)
    trade_logger.setLevel(logging.INFO)
    
    # Silence external library logs (reduce noise)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)
    
    # Log initialization
    logger.info("=" * 60)
    logger.info(f"🚀 Trading Platform Logging Initialized")
    logger.info(f"📅 Session Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📊 Log Level: {log_level}")
    logger.info(f"📁 Log File: {log_file_path}")
    logger.info(f"🔄 Trading Mode: {TradingConfig.TRADING_MODE}")
    logger.info("=" * 60)
    
    return logger

class PerformanceLogger:
    """Helper class for performance timing"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.logger = logging.getLogger('performance')
    
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            self.logger.info(f"{self.operation_name}: {duration:.3f}s")

class TradeLogger:
    """Helper class for trade logging"""
    
    def __init__(self):
        self.logger = logging.getLogger('trades')
    
    def log_trade_signal(self, signal: dict):
        """Log trade signal generation"""
        self.logger.info(f"SIGNAL: {signal}")
    
    def log_trade_execution(self, trade_result: dict):
        """Log trade execution"""
        self.logger.info(f"EXECUTION: {trade_result}")
    
    def log_position_update(self, position: dict):
        """Log position updates"""
        self.logger.info(f"POSITION: {position}")

# Export the main function
__all__ = ['setup_logging', 'PerformanceLogger', 'TradeLogger']
