#!/usr/bin/env python3
"""
Model Trainer
Handles data collection, preparation, and training of ML models
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import yfinance as yf
from pathlib import Path

from core.kite_manager import KiteManager
from .base_model import BaseMLModel, ModelConfig
from .lstm_price_predictor import LSTMPricePredictor

logger = logging.getLogger(__name__)

class ModelTrainer:
    """
    Comprehensive model trainer for ML models
    Handles data collection, preprocessing, and training coordination
    """
    
    def __init__(self, kite_manager: Optional[KiteManager] = None, data_dir: str = "data/ml_training"):
        """
        Initialize Model Trainer
        
        Args:
            kite_manager: KiteManager instance for live data
            data_dir: Directory to store training data and models
        """
        self.kite_manager = kite_manager
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Training configuration
        self.default_training_period = 365 * 2  # 2 years of data
        self.min_training_samples = 1000
        
        logger.info("🎓 Model Trainer initialized")
    
    def collect_training_data(self, symbol: str = "^NSEI", period_days: int = None) -> pd.DataFrame:
        """
        Collect historical data for training
        
        Args:
            symbol: Symbol to collect data for (default: Nifty 50)
            period_days: Number of days of historical data
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            if period_days is None:
                period_days = self.default_training_period
            
            logger.info(f"📊 Collecting {period_days} days of training data for {symbol}")
            
            # Try to get data from Kite Connect first (if available and authenticated)
            if self.kite_manager and self.kite_manager.is_authenticated:
                historical_data = self._get_kite_historical_data(symbol, period_days)
                if historical_data is not None and not historical_data.empty:
                    logger.info(f"✅ Retrieved {len(historical_data)} samples from Kite Connect")
                    return historical_data
            
            # Fallback to yfinance for historical data
            logger.info("🔄 Using yfinance for historical data collection...")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)
            
            # Download data using yfinance
            ticker = yf.Ticker(symbol)
            data = ticker.history(start=start_date, end=end_date, interval="1d")
            
            if data.empty:
                raise ValueError(f"❌ No historical data available for {symbol}")
            
            # Standardize column names
            data.columns = [col.lower() for col in data.columns]
            data = data.reset_index()
            
            # Ensure we have the required columns
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            missing_columns = set(required_columns) - set(data.columns)
            if missing_columns:
                raise ValueError(f"❌ Missing required columns: {missing_columns}")
            
            # Clean data
            data = self._clean_training_data(data)
            
            logger.info(f"✅ Collected {len(data)} samples from yfinance")
            
            # Save data for future use
            self._save_training_data(data, symbol)
            
            return data
            
        except Exception as e:
            logger.error(f"❌ Failed to collect training data: {str(e)}")
            raise
    
    def _get_kite_historical_data(self, symbol: str, period_days: int) -> Optional[pd.DataFrame]:
        """Get historical data from Kite Connect"""
        try:
            # This would require implementing historical data fetch from Kite
            # For now, return None to use yfinance fallback
            logger.info("⚠️ Kite historical data not implemented yet, using yfinance")
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to get Kite historical data: {str(e)}")
            return None
    
    def _clean_training_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate training data"""
        try:
            logger.debug("🧹 Cleaning training data...")
            
            # Remove any rows with missing OHLCV data
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            data = data.dropna(subset=required_cols)
            
            # Remove rows where high < low (data errors)
            data = data[data['high'] >= data['low']]
            
            # Remove rows where close is not between high and low
            data = data[(data['close'] >= data['low']) & (data['close'] <= data['high'])]
            data = data[(data['open'] >= data['low']) & (data['open'] <= data['high'])]
            
            # Remove extreme outliers (more than 20% daily move)
            data['daily_return'] = data['close'].pct_change()
            data = data[abs(data['daily_return']) <= 0.20]
            
            # Remove zero volume days (likely data errors)
            data = data[data['volume'] > 0]
            
            # Sort by date
            if 'date' in data.columns:
                data = data.sort_values('date')
            elif data.index.name == 'Date':
                data = data.sort_index()
            
            # Reset index
            data = data.reset_index(drop=True)
            
            logger.debug(f"✅ Data cleaned: {len(data)} valid samples")
            return data
            
        except Exception as e:
            logger.error(f"❌ Data cleaning failed: {str(e)}")
            raise
    
    def _save_training_data(self, data: pd.DataFrame, symbol: str) -> None:
        """Save training data to disk"""
        try:
            filename = f"{symbol}_training_data_{datetime.now().strftime('%Y%m%d')}.csv"
            filepath = self.data_dir / filename
            data.to_csv(filepath, index=False)
            logger.debug(f"💾 Training data saved to {filepath}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to save training data: {str(e)}")
    
    def train_lstm_model(self, 
                        symbol: str = "^NSEI",
                        period_days: int = None,
                        config: Optional[ModelConfig] = None,
                        force_retrain: bool = False) -> Dict[str, Any]:
        """
        Train LSTM price prediction model
        
        Args:
            symbol: Symbol to train on
            period_days: Days of historical data
            config: Custom model configuration
            force_retrain: Force retraining even if model exists
            
        Returns:
            Training results and model info
        """
        try:
            logger.info(f"🎓 Starting LSTM model training for {symbol}")
            
            # Create LSTM model
            lstm_model = LSTMPricePredictor(config)
            
            # Check if model already exists and is trained
            if not force_retrain and lstm_model.load_model():
                logger.info("📁 Existing trained model loaded")
                return {
                    'status': 'loaded_existing',
                    'model_info': lstm_model.get_model_info(),
                    'message': 'Existing trained model loaded successfully'
                }
            
            # Collect training data
            training_data = self.collect_training_data(symbol, period_days)
            
            if len(training_data) < self.min_training_samples:
                raise ValueError(f"❌ Insufficient training data: {len(training_data)} < {self.min_training_samples}")
            
            # Train the model
            training_results = lstm_model.train(training_data)
            
            # Validate model performance
            validation_results = self._validate_model_performance(lstm_model, training_results)
            
            result = {
                'status': 'training_completed',
                'model_info': lstm_model.get_model_info(),
                'training_results': training_results,
                'validation_results': validation_results,
                'training_data_size': len(training_data),
                'message': 'LSTM model trained successfully'
            }
            
            logger.info(f"✅ LSTM model training completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"❌ LSTM model training failed: {str(e)}")
            raise
    
    def _validate_model_performance(self, model: BaseMLModel, training_results: Dict[str, Any]) -> Dict[str, Any]:
        """Validate model performance and provide recommendations"""
        try:
            validation_metrics = training_results.get('validation_metrics', {})
            
            # Performance thresholds
            min_directional_accuracy = 0.55  # 55% directional accuracy
            max_acceptable_mse = 10000  # MSE threshold
            min_r2_score = 0.1  # R-squared threshold
            
            # Check performance
            directional_acc = validation_metrics.get('directional_accuracy', 0.0)
            mse = validation_metrics.get('mse', float('inf'))
            r2 = validation_metrics.get('r2', 0.0)
            
            performance_grade = 'EXCELLENT'
            recommendations = []
            
            # Grade the model
            if directional_acc < 0.50:
                performance_grade = 'POOR'
                recommendations.append("Model performs worse than random - consider different features or architecture")
            elif directional_acc < min_directional_accuracy:
                performance_grade = 'BELOW_AVERAGE'
                recommendations.append("Directional accuracy is low - consider feature engineering or hyperparameter tuning")
            elif directional_acc > 0.65:
                performance_grade = 'EXCELLENT'
            else:
                performance_grade = 'GOOD'
            
            if mse > max_acceptable_mse:
                recommendations.append("High MSE - model predictions may be unreliable for absolute values")
            
            if r2 < min_r2_score:
                recommendations.append("Low R-squared - model explains little variance, consider more features")
            
            # Trading viability assessment
            trading_viable = (
                directional_acc >= min_directional_accuracy and
                mse <= max_acceptable_mse and
                r2 >= min_r2_score
            )
            
            validation_result = {
                'performance_grade': performance_grade,
                'trading_viable': trading_viable,
                'directional_accuracy': directional_acc,
                'mse': mse,
                'r2_score': r2,
                'recommendations': recommendations,
                'thresholds': {
                    'min_directional_accuracy': min_directional_accuracy,
                    'max_acceptable_mse': max_acceptable_mse,
                    'min_r2_score': min_r2_score
                }
            }
            
            logger.info(f"📊 Model Performance: {performance_grade} (Viable for trading: {trading_viable})")
            
            return validation_result
            
        except Exception as e:
            logger.error(f"❌ Model validation failed: {str(e)}")
            return {'performance_grade': 'UNKNOWN', 'trading_viable': False, 'error': str(e)}
    
    def quick_model_test(self, model: BaseMLModel, test_data: pd.DataFrame = None) -> Dict[str, Any]:
        """
        Quick test of trained model with recent data
        
        Args:
            model: Trained model to test
            test_data: Test data (if None, will collect recent data)
            
        Returns:
            Test results
        """
        try:
            if not model.is_trained:
                raise ValueError("❌ Model must be trained before testing")
            
            # Get test data if not provided
            if test_data is None:
                test_data = self.collect_training_data(period_days=30)  # Last 30 days
            
            logger.info(f"🧪 Testing model with {len(test_data)} samples")
            
            # Make prediction on the most recent data
            if isinstance(model, LSTMPricePredictor):
                prediction_result = model.predict_next_price(test_data)
            else:
                # For other model types, use generic prediction
                prediction_result = model.predict(test_data.iloc[-1:])
            
            test_results = {
                'prediction': prediction_result.to_dict(),
                'current_price': float(test_data['close'].iloc[-1]),
                'test_data_points': len(test_data),
                'model_name': model.config.model_name,
                'test_timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Model test completed - Prediction: {prediction_result.prediction_value:.2f}")
            
            return test_results
            
        except Exception as e:
            logger.error(f"❌ Model test failed: {str(e)}")
            raise
    
    def get_training_status(self) -> Dict[str, Any]:
        """Get status of all trained models"""
        try:
            status = {
                'available_models': [],
                'training_data_files': [],
                'last_updated': datetime.now().isoformat()
            }
            
            # Check for saved models
            model_files = list(self.data_dir.glob("*.pkl"))
            for model_file in model_files:
                model_name = model_file.stem
                config_file = model_file.parent / f"{model_name}_config.json"
                metrics_file = model_file.parent / f"{model_name}_metrics.json"
                
                status['available_models'].append({
                    'model_name': model_name,
                    'model_file': str(model_file),
                    'has_config': config_file.exists(),
                    'has_metrics': metrics_file.exists(),
                    'file_size': model_file.stat().st_size,
                    'last_modified': datetime.fromtimestamp(model_file.stat().st_mtime).isoformat()
                })
            
            # Check for training data files
            data_files = list(self.data_dir.glob("*_training_data_*.csv"))
            for data_file in data_files:
                status['training_data_files'].append({
                    'filename': data_file.name,
                    'file_size': data_file.stat().st_size,
                    'last_modified': datetime.fromtimestamp(data_file.stat().st_mtime).isoformat()
                })
            
            return status
            
        except Exception as e:
            logger.error(f"❌ Failed to get training status: {str(e)}")
            return {'error': str(e)}