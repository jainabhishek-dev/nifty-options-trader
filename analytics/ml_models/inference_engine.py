#!/usr/bin/env python3
"""
ML Inference Engine
Handles real-time predictions and model serving for live trading
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import json
from pathlib import Path

from core.kite_manager import KiteManager
from analytics.options_data_provider import OptionsDataProvider
from .base_model import BaseMLModel, PredictionResult
from .lstm_price_predictor import LSTMPricePredictor
from .model_trainer import ModelTrainer

logger = logging.getLogger(__name__)

class InferenceEngine:
    """
    Real-time ML inference engine for trading predictions
    Manages multiple models and provides live predictions
    """
    
    def __init__(self, kite_manager: Optional[KiteManager] = None):
        """
        Initialize Inference Engine
        
        Args:
            kite_manager: KiteManager for live data
        """
        self.kite_manager = kite_manager
        self.options_provider = OptionsDataProvider(kite_manager) if kite_manager else None
        
        # Model management
        self.loaded_models: Dict[str, BaseMLModel] = {}
        self.model_predictions: Dict[str, PredictionResult] = {}
        self.prediction_cache: Dict[str, Dict] = {}
        
        # Configuration
        self.cache_duration = 300  # 5 minutes
        self.min_data_points = 100  # Minimum data points for prediction
        self.max_models = 5  # Maximum loaded models
        
        # Performance tracking
        self.prediction_count = 0
        self.error_count = 0
        self.last_prediction_time = None
        
        logger.info("🔮 ML Inference Engine initialized")
    
    def load_model(self, model_name: str, model_type: str = "LSTM") -> bool:
        """
        Load a trained model for inference
        
        Args:
            model_name: Name of the model to load
            model_type: Type of model (LSTM, etc.)
            
        Returns:
            True if model loaded successfully
        """
        try:
            # Check if model already loaded
            if model_name in self.loaded_models:
                logger.info(f"📁 Model {model_name} already loaded")
                return True
            
            # Create model instance based on type
            if model_type.upper() == "LSTM":
                model = LSTMPricePredictor()
                model.config.model_name = model_name
            else:
                raise ValueError(f"❌ Unsupported model type: {model_type}")
            
            # Load the trained model
            if not model.load_model():
                logger.error(f"❌ Failed to load model {model_name}")
                return False
            
            # Validate model is trained
            if not model.is_trained:
                logger.error(f"❌ Model {model_name} is not trained")
                return False
            
            # Check if we need to remove old models (memory management)
            if len(self.loaded_models) >= self.max_models:
                oldest_model = min(self.loaded_models.keys())
                del self.loaded_models[oldest_model]
                logger.info(f"🗑️ Removed oldest model {oldest_model} to make space")
            
            # Add to loaded models
            self.loaded_models[model_name] = model
            
            logger.info(f"✅ Model {model_name} loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load model {model_name}: {str(e)}")
            return False
    
    def get_live_market_data(self, symbol: str = "NIFTY", periods: int = 100) -> pd.DataFrame:
        """
        Get live market data for inference
        
        Args:
            symbol: Symbol to get data for
            periods: Number of recent periods to fetch
            
        Returns:
            DataFrame with recent OHLCV data
        """
        try:
            if not self.kite_manager or not self.kite_manager.is_authenticated:
                raise ValueError("❌ Kite Manager not authenticated - cannot fetch live data")
            
            logger.debug(f"📊 Fetching live market data for {symbol}")
            
            # Get current Nifty LTP
            current_price = self.kite_manager.get_nifty_ltp()
            if not current_price:
                raise ValueError("❌ Cannot get current Nifty price")
            
            # For now, we'll create a simple data structure
            # In a full implementation, this would fetch actual historical intraday data
            logger.warning("⚠️ Using simplified market data - implement full historical data fetch")
            
            # Create sample recent data (this should be replaced with actual historical data)
            dates = pd.date_range(end=datetime.now(), periods=periods, freq='1H')
            
            # Generate realistic OHLCV data around current price
            np.random.seed(42)  # For reproducible results
            base_price = current_price
            
            data = []
            for i, date in enumerate(dates):
                # Simple random walk for demo purposes
                change_pct = np.random.normal(0, 0.005)  # 0.5% volatility
                if i == 0:
                    close = base_price
                else:
                    close = data[-1]['close'] * (1 + change_pct)
                
                high = close * (1 + abs(np.random.normal(0, 0.003)))
                low = close * (1 - abs(np.random.normal(0, 0.003)))
                open_price = low + (high - low) * np.random.random()
                volume = int(np.random.uniform(10000, 100000))
                
                data.append({
                    'date': date,
                    'open': open_price,
                    'high': high,
                    'low': low,
                    'close': close,
                    'volume': volume
                })
            
            df = pd.DataFrame(data)
            
            # Set the last close to actual current price
            df.loc[df.index[-1], 'close'] = current_price
            
            logger.debug(f"✅ Retrieved {len(df)} data points, current price: {current_price}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to get live market data: {str(e)}")
            raise
    
    def predict_price(self, 
                     model_name: str = "lstm_price_predictor", 
                     use_cache: bool = True) -> PredictionResult:
        """
        Make price prediction using specified model
        
        Args:
            model_name: Name of model to use
            use_cache: Whether to use cached predictions
            
        Returns:
            PredictionResult with price prediction
        """
        try:
            # Check cache first
            if use_cache and model_name in self.prediction_cache:
                cached_prediction = self.prediction_cache[model_name]
                cache_time = datetime.fromisoformat(cached_prediction['timestamp'])
                if (datetime.now() - cache_time).total_seconds() < self.cache_duration:
                    logger.debug(f"📚 Using cached prediction for {model_name}")
                    return PredictionResult(**cached_prediction['prediction'])
            
            # Load model if not already loaded
            if model_name not in self.loaded_models:
                if not self.load_model(model_name):
                    raise ValueError(f"❌ Cannot load model {model_name}")
            
            model = self.loaded_models[model_name]
            
            # Get live market data
            market_data = self.get_live_market_data(periods=model.config.lookback_period + 50)
            
            if len(market_data) < model.config.lookback_period:
                raise ValueError(f"❌ Insufficient market data: {len(market_data)} < {model.config.lookback_period}")
            
            # Make prediction
            if isinstance(model, LSTMPricePredictor):
                prediction = model.predict_next_price(market_data)
            else:
                # Generic prediction for other model types
                prediction = model.predict(market_data.iloc[-1:])
            
            # Update tracking
            self.prediction_count += 1
            self.last_prediction_time = datetime.now()
            self.model_predictions[model_name] = prediction
            
            # Cache prediction
            if use_cache:
                self.prediction_cache[model_name] = {
                    'prediction': prediction.to_dict(),
                    'timestamp': datetime.now().isoformat()
                }
            
            logger.info(f"🔮 Price prediction: {prediction.prediction_value:.2f} "
                       f"(confidence: {prediction.confidence_score:.2%})")
            
            return prediction
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"❌ Price prediction failed: {str(e)}")
            raise
    
    def predict_direction(self, model_name: str = "lstm_price_predictor") -> Dict[str, Any]:
        """
        Predict price direction (up/down) with confidence
        
        Args:
            model_name: Name of model to use
            
        Returns:
            Direction prediction with probabilities
        """
        try:
            # Get price prediction
            price_prediction = self.predict_price(model_name)
            
            # Get current price
            market_data = self.get_live_market_data(periods=2)
            current_price = market_data['close'].iloc[-1]
            
            # Calculate direction
            predicted_price = price_prediction.prediction_value
            price_change = predicted_price - current_price
            price_change_pct = (price_change / current_price) * 100
            
            # Determine direction and strength
            if abs(price_change_pct) < 0.1:  # Less than 0.1% change
                direction = "SIDEWAYS"
                strength = "WEAK"
            elif price_change > 0:
                direction = "UP"
                strength = "STRONG" if price_change_pct > 1.0 else "MODERATE"
            else:
                direction = "DOWN"
                strength = "STRONG" if price_change_pct < -1.0 else "MODERATE"
            
            # Direction confidence (based on model confidence and magnitude of change)
            base_confidence = price_prediction.confidence_score
            magnitude_bonus = min(0.2, abs(price_change_pct) / 100)  # Up to 20% bonus for large moves
            direction_confidence = min(0.95, base_confidence + magnitude_bonus)
            
            result = {
                'direction': direction,
                'strength': strength,
                'confidence': direction_confidence,
                'current_price': current_price,
                'predicted_price': predicted_price,
                'price_change': price_change,
                'price_change_percent': price_change_pct,
                'model_used': model_name,
                'timestamp': datetime.now().isoformat(),
                'raw_prediction': price_prediction.to_dict()
            }
            
            logger.info(f"📊 Direction: {direction} ({strength}) - "
                       f"{price_change_pct:+.2f}% [Confidence: {direction_confidence:.2%}]")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Direction prediction failed: {str(e)}")
            raise
    
    def get_ensemble_prediction(self, model_names: List[str] = None) -> Dict[str, Any]:
        """
        Get ensemble prediction from multiple models
        
        Args:
            model_names: List of model names to use (if None, use all loaded)
            
        Returns:
            Ensemble prediction result
        """
        try:
            if model_names is None:
                model_names = list(self.loaded_models.keys())
            
            if not model_names:
                raise ValueError("❌ No models available for ensemble prediction")
            
            logger.info(f"🎭 Creating ensemble prediction from {len(model_names)} models")
            
            predictions = []
            weights = []
            
            # Get predictions from all models
            for model_name in model_names:
                try:
                    prediction = self.predict_price(model_name, use_cache=True)
                    predictions.append(prediction.prediction_value)
                    weights.append(prediction.confidence_score)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to get prediction from {model_name}: {str(e)}")
                    continue
            
            if not predictions:
                raise ValueError("❌ No valid predictions available for ensemble")
            
            # Calculate weighted average
            predictions = np.array(predictions)
            weights = np.array(weights)
            
            # Normalize weights
            weights = weights / weights.sum()
            
            # Ensemble prediction
            ensemble_price = np.average(predictions, weights=weights)
            ensemble_confidence = np.average(weights)  # Average confidence
            
            # Calculate consensus (how much models agree)
            price_std = np.std(predictions)
            consensus_score = max(0.0, 1.0 - (price_std / ensemble_price))
            
            # Get current price for comparison
            market_data = self.get_live_market_data(periods=2)
            current_price = market_data['close'].iloc[-1]
            
            result = {
                'ensemble_price': ensemble_price,
                'ensemble_confidence': ensemble_confidence,
                'consensus_score': consensus_score,
                'current_price': current_price,
                'price_change': ensemble_price - current_price,
                'price_change_percent': ((ensemble_price - current_price) / current_price) * 100,
                'models_used': len(predictions),
                'individual_predictions': [
                    {'model': name, 'prediction': pred, 'weight': weight}
                    for name, pred, weight in zip(model_names[:len(predictions)], predictions, weights)
                ],
                'prediction_std': price_std,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"🎭 Ensemble prediction: {ensemble_price:.2f} "
                       f"(consensus: {consensus_score:.2%}, confidence: {ensemble_confidence:.2%})")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Ensemble prediction failed: {str(e)}")
            raise
    
    def get_trading_signals(self, model_name: str = "lstm_price_predictor") -> Dict[str, Any]:
        """
        Generate trading signals based on ML predictions
        
        Args:
            model_name: Model to use for signals
            
        Returns:
            Trading signals with entry/exit recommendations
        """
        try:
            # Get direction prediction
            direction_pred = self.predict_direction(model_name)
            
            # Get current market context
            market_data = self.get_live_market_data(periods=20)
            current_price = market_data['close'].iloc[-1]
            
            # Calculate recent volatility
            returns = market_data['close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)  # Annualized volatility
            
            # Generate signals based on prediction and confidence
            signals = {
                'primary_signal': 'HOLD',
                'signal_strength': 0.0,
                'confidence': direction_pred['confidence'],
                'entry_price': None,
                'stop_loss': None,
                'target_price': None,
                'risk_reward_ratio': None,
                'position_size_suggestion': 0.0,
                'reasoning': []
            }
            
            # Determine signal based on direction and confidence
            min_confidence = 0.60  # Minimum confidence for trading signals
            min_change = 0.5  # Minimum predicted change percentage
            
            direction = direction_pred['direction']
            confidence = direction_pred['confidence']
            change_pct = abs(direction_pred['price_change_percent'])
            
            if confidence >= min_confidence and change_pct >= min_change:
                if direction == "UP":
                    signals['primary_signal'] = 'BUY_CALL'
                    signals['entry_price'] = current_price
                    signals['target_price'] = direction_pred['predicted_price']
                    signals['stop_loss'] = current_price * 0.98  # 2% stop loss
                    
                elif direction == "DOWN":
                    signals['primary_signal'] = 'BUY_PUT'
                    signals['entry_price'] = current_price
                    signals['target_price'] = direction_pred['predicted_price']
                    signals['stop_loss'] = current_price * 1.02  # 2% stop loss
                
                # Calculate signal strength
                signals['signal_strength'] = min(1.0, (confidence - min_confidence) * 2.5)
                
                # Position sizing based on confidence and volatility
                base_position_size = 0.1  # 10% base position
                confidence_multiplier = confidence
                volatility_adjustment = max(0.5, 1.0 - volatility)
                
                signals['position_size_suggestion'] = (
                    base_position_size * confidence_multiplier * volatility_adjustment
                )
                
                # Calculate risk-reward ratio
                if signals['target_price'] and signals['stop_loss']:
                    profit_potential = abs(signals['target_price'] - signals['entry_price'])
                    loss_potential = abs(signals['entry_price'] - signals['stop_loss'])
                    signals['risk_reward_ratio'] = profit_potential / loss_potential if loss_potential > 0 else 0
                
                # Reasoning
                signals['reasoning'] = [
                    f"ML model predicts {direction} movement with {confidence:.1%} confidence",
                    f"Expected price change: {direction_pred['price_change_percent']:+.2f}%",
                    f"Current volatility: {volatility:.1%} (annualized)"
                ]
            else:
                # Not confident enough for signal
                signals['reasoning'] = [
                    f"Confidence {confidence:.1%} below threshold {min_confidence:.1%}",
                    f"Predicted change {change_pct:.2f}% below threshold {min_change:.2f}%",
                    "Market conditions not favorable for ML-based trading"
                ]
            
            # Add market context
            signals['market_context'] = {
                'current_price': current_price,
                'volatility': volatility,
                'direction_prediction': direction_pred,
                'model_used': model_name,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"📡 Trading Signal: {signals['primary_signal']} "
                       f"(strength: {signals['signal_strength']:.2f})")
            
            return signals
            
        except Exception as e:
            logger.error(f"❌ Trading signal generation failed: {str(e)}")
            raise
    
    def get_inference_stats(self) -> Dict[str, Any]:
        """Get inference engine statistics"""
        return {
            'loaded_models': list(self.loaded_models.keys()),
            'prediction_count': self.prediction_count,
            'error_count': self.error_count,
            'error_rate': self.error_count / max(1, self.prediction_count),
            'last_prediction_time': self.last_prediction_time.isoformat() if self.last_prediction_time else None,
            'cache_size': len(self.prediction_cache),
            'recent_predictions': {
                name: pred.to_dict() 
                for name, pred in self.model_predictions.items()
            }
        }
    
    def clear_cache(self):
        """Clear prediction cache"""
        self.prediction_cache.clear()
        logger.info("🧹 Inference cache cleared")