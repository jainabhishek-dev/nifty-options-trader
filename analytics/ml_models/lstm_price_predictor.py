#!/usr/bin/env python3
"""
LSTM Price Predictor
Advanced LSTM neural network for Nifty price prediction
Uses historical price data and technical indicators to predict future prices
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
import warnings

# Suppress TensorFlow warnings
warnings.filterwarnings('ignore')
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    from sklearn.preprocessing import MinMaxScaler, StandardScaler
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    TENSORFLOW_AVAILABLE = True
    KerasModel = tf.keras.Model
except ImportError:
    TENSORFLOW_AVAILABLE = False
    tf = None
    KerasModel = Any  # Fallback type for when TensorFlow is not available

from .base_model import BaseMLModel, ModelConfig, PredictionResult

logger = logging.getLogger(__name__)

class LSTMPricePredictor(BaseMLModel):
    """
    LSTM-based price predictor for Nifty 50
    Predicts future price movements using historical price and volume data
    """
    
    def __init__(self, config: Optional[ModelConfig] = None):
        """Initialize LSTM Price Predictor"""
        
        # Check TensorFlow availability
        if not TENSORFLOW_AVAILABLE:
            raise ImportError(
                "❌ TensorFlow not available. Install with: pip install tensorflow scikit-learn"
            )
        
        # Default configuration if not provided
        if config is None:
            config = self._create_default_config()
        
        super().__init__(config)
        
        # LSTM specific parameters
        self.sequence_length = config.lookback_period
        self.n_features = len(config.input_features)
        self.prediction_steps = config.prediction_horizon
        
        # Technical indicator calculation parameters
        self.technical_indicators = [
            'sma_5', 'sma_10', 'sma_20', 'ema_12', 'ema_26',
            'rsi', 'macd', 'bb_upper', 'bb_lower', 'volume_sma'
        ]
        
        logger.info(f"🧠 LSTM Price Predictor initialized (seq_len: {self.sequence_length})")
    
    def _create_default_config(self) -> ModelConfig:
        """Create default configuration for LSTM model"""
        return ModelConfig(
            model_name="lstm_price_predictor",
            model_type="LSTM",
            input_features=[
                'open', 'high', 'low', 'close', 'volume',
                'sma_5', 'sma_10', 'sma_20', 'ema_12', 'ema_26',
                'rsi', 'macd', 'bb_upper', 'bb_lower', 'volume_sma'
            ],
            target_variable="close_next",
            lookback_period=60,  # 60 time periods lookback
            prediction_horizon=1,  # Predict next period
            training_data_size=5000,  # Minimum samples for training
            validation_split=0.2,
            hyperparameters={
                'lstm_units_1': 50,
                'lstm_units_2': 30,
                'dropout_rate': 0.2,
                'learning_rate': 0.001,
                'batch_size': 32,
                'epochs': 100,
                'patience': 15
            },
            created_at=datetime.now(),
            version="1.0"
        )
    
    def _build_model(self) -> Any:
        """Build LSTM neural network architecture"""
        try:
            # Get hyperparameters
            hp = self.config.hyperparameters
            
            # Create sequential model
            model = Sequential([
                # First LSTM layer
                LSTM(
                    units=hp.get('lstm_units_1', 50),
                    return_sequences=True,
                    input_shape=(self.sequence_length, self.n_features),
                    name='lstm_1'
                ),
                BatchNormalization(),
                Dropout(hp.get('dropout_rate', 0.2)),
                
                # Second LSTM layer
                LSTM(
                    units=hp.get('lstm_units_2', 30),
                    return_sequences=False,
                    name='lstm_2'
                ),
                BatchNormalization(),
                Dropout(hp.get('dropout_rate', 0.2)),
                
                # Dense layers
                Dense(25, activation='relu', name='dense_1'),
                Dropout(hp.get('dropout_rate', 0.2)),
                Dense(1, activation='linear', name='output')
            ])
            
            # Compile model
            model.compile(
                optimizer=Adam(learning_rate=hp.get('learning_rate', 0.001)),
                loss='mse',
                metrics=['mae', 'mse']
            )
            
            logger.info(f"✅ LSTM model built successfully")
            logger.info(f"📊 Model parameters: {model.count_params()}")
            
            return model
            
        except Exception as e:
            logger.error(f"❌ Failed to build LSTM model: {str(e)}")
            raise
    
    def _prepare_data(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare data for LSTM training
        Creates sequences and technical indicators
        """
        try:
            logger.info(f"🔄 Preparing LSTM training data ({len(data)} samples)")
            
            # Create a copy to avoid modifying original data
            df = data.copy()
            
            # Ensure we have required basic columns
            required_basic = ['open', 'high', 'low', 'close', 'volume']
            missing_basic = set(required_basic) - set(df.columns)
            if missing_basic:
                raise ValueError(f"❌ Missing basic OHLCV columns: {missing_basic}")
            
            # Calculate technical indicators
            df = self._add_technical_indicators(df)
            
            # Create target variable (next period close price)
            df['close_next'] = df['close'].shift(-1)
            
            # Remove last row (no target available)
            df = df[:-1]
            
            # Select only the features we need
            feature_columns = self.config.input_features
            available_features = [col for col in feature_columns if col in df.columns]
            
            if len(available_features) != len(feature_columns):
                missing = set(feature_columns) - set(available_features)
                logger.warning(f"⚠️ Missing features (will be excluded): {missing}")
                # Update config to reflect available features
                self.config.input_features = available_features
                self.n_features = len(available_features)
            
            # Select feature data
            feature_data = df[available_features].values
            target_data = df[self.config.target_variable].values
            
            # Remove any rows with NaN values
            valid_mask = ~(np.isnan(feature_data).any(axis=1) | np.isnan(target_data))
            feature_data = feature_data[valid_mask]
            target_data = target_data[valid_mask]
            
            logger.info(f"📊 Valid samples after cleaning: {len(feature_data)}")
            
            if len(feature_data) < self.sequence_length + 100:
                raise ValueError(f"❌ Insufficient data for training. Need at least {self.sequence_length + 100} samples")
            
            # Scale features and targets
            self.feature_scaler = MinMaxScaler()
            self.target_scaler = MinMaxScaler()
            
            scaled_features = self.feature_scaler.fit_transform(feature_data)
            scaled_targets = self.target_scaler.fit_transform(target_data.reshape(-1, 1)).flatten()
            
            # Create sequences for LSTM
            X, y = self._create_sequences(scaled_features, scaled_targets)
            
            logger.info(f"📈 Created {len(X)} sequences for LSTM training")
            logger.info(f"📐 Input shape: {X.shape}, Target shape: {y.shape}")
            
            return X, y
            
        except Exception as e:
            logger.error(f"❌ Data preparation failed: {str(e)}")
            raise
    
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to the dataset"""
        try:
            logger.debug("📊 Calculating technical indicators...")
            
            # Simple Moving Averages
            df['sma_5'] = df['close'].rolling(window=5).mean()
            df['sma_10'] = df['close'].rolling(window=10).mean()
            df['sma_20'] = df['close'].rolling(window=20).mean()
            
            # Exponential Moving Averages
            df['ema_12'] = df['close'].ewm(span=12).mean()
            df['ema_26'] = df['close'].ewm(span=26).mean()
            
            # MACD
            df['macd'] = df['ema_12'] - df['ema_26']
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            bb_period = 20
            bb_std = 2
            df['bb_middle'] = df['close'].rolling(window=bb_period).mean()
            bb_std_val = df['close'].rolling(window=bb_period).std()
            df['bb_upper'] = df['bb_middle'] + (bb_std_val * bb_std)
            df['bb_lower'] = df['bb_middle'] - (bb_std_val * bb_std)
            
            # Volume indicators
            df['volume_sma'] = df['volume'].rolling(window=10).mean()
            
            # Forward fill any remaining NaN values
            df = df.fillna(method='ffill').fillna(method='bfill')
            
            logger.debug("✅ Technical indicators calculated")
            return df
            
        except Exception as e:
            logger.error(f"❌ Technical indicator calculation failed: {str(e)}")
            raise
    
    def _create_sequences(self, features: np.ndarray, targets: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for LSTM training"""
        X, y = [], []
        
        for i in range(self.sequence_length, len(features)):
            # Features: sequence of past values
            X.append(features[i-self.sequence_length:i])
            # Target: next value
            y.append(targets[i])
        
        return np.array(X), np.array(y)
    
    def _train_model(self, X_train: np.ndarray, y_train: np.ndarray, 
                    X_val: np.ndarray, y_val: np.ndarray) -> Dict[str, Any]:
        """Train the LSTM model"""
        try:
            logger.info(f"🔄 Training LSTM model...")
            
            hp = self.config.hyperparameters
            
            # Callbacks
            callbacks = [
                EarlyStopping(
                    monitor='val_loss',
                    patience=hp.get('patience', 15),
                    restore_best_weights=True,
                    verbose=1
                ),
                ReduceLROnPlateau(
                    monitor='val_loss',
                    factor=0.5,
                    patience=7,
                    min_lr=1e-7,
                    verbose=1
                )
            ]
            
            # Train model
            history = self.model.fit(
                X_train, y_train,
                epochs=hp.get('epochs', 100),
                batch_size=hp.get('batch_size', 32),
                validation_data=(X_val, y_val),
                callbacks=callbacks,
                verbose=1
            )
            
            # Calculate final metrics
            train_pred = self.model.predict(X_train, verbose=0)
            val_pred = self.model.predict(X_val, verbose=0)
            
            # Inverse transform predictions for evaluation
            train_pred_inv = self.target_scaler.inverse_transform(train_pred.reshape(-1, 1)).flatten()
            val_pred_inv = self.target_scaler.inverse_transform(val_pred.reshape(-1, 1)).flatten()
            y_train_inv = self.target_scaler.inverse_transform(y_train.reshape(-1, 1)).flatten()
            y_val_inv = self.target_scaler.inverse_transform(y_val.reshape(-1, 1)).flatten()
            
            # Calculate metrics
            self.training_metrics = {
                'mse': float(mean_squared_error(y_train_inv, train_pred_inv)),
                'mae': float(mean_absolute_error(y_train_inv, train_pred_inv)),
                'r2': float(r2_score(y_train_inv, train_pred_inv)),
                'final_loss': float(history.history['loss'][-1])
            }
            
            self.validation_metrics = {
                'mse': float(mean_squared_error(y_val_inv, val_pred_inv)),
                'mae': float(mean_absolute_error(y_val_inv, val_pred_inv)),
                'r2': float(r2_score(y_val_inv, val_pred_inv)),
                'final_val_loss': float(history.history['val_loss'][-1])
            }
            
            # Calculate directional accuracy (more important for trading)
            train_direction_acc = self._calculate_directional_accuracy(y_train_inv, train_pred_inv)
            val_direction_acc = self._calculate_directional_accuracy(y_val_inv, val_pred_inv)
            
            self.training_metrics['directional_accuracy'] = train_direction_acc
            self.validation_metrics['directional_accuracy'] = val_direction_acc
            
            training_results = {
                'training_metrics': self.training_metrics,
                'validation_metrics': self.validation_metrics,
                'epochs_trained': len(history.history['loss']),
                'model_architecture': str(self.model.layers),
                'training_time': datetime.now().isoformat()
            }
            
            logger.info(f"✅ LSTM training completed")
            logger.info(f"📊 Validation MSE: {self.validation_metrics['mse']:.2f}")
            logger.info(f"🎯 Directional Accuracy: {val_direction_acc:.2%}")
            
            return training_results
            
        except Exception as e:
            logger.error(f"❌ LSTM training failed: {str(e)}")
            raise
    
    def _calculate_directional_accuracy(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Calculate directional accuracy (up/down prediction correctness)"""
        if len(y_true) < 2 or len(y_pred) < 2:
            return 0.0
        
        # Calculate actual and predicted directions
        actual_direction = np.sign(np.diff(y_true))
        predicted_direction = np.sign(np.diff(y_pred))
        
        # Calculate accuracy
        correct_predictions = (actual_direction == predicted_direction).sum()
        total_predictions = len(actual_direction)
        
        return correct_predictions / total_predictions if total_predictions > 0 else 0.0
    
    def _predict_raw(self, X: np.ndarray) -> np.ndarray:
        """Make raw prediction with LSTM model"""
        try:
            if X.shape[0] == 1 and len(X.shape) == 2:
                # Single sample - reshape for LSTM
                X = X.reshape(1, self.sequence_length, self.n_features)
            
            prediction = self.model.predict(X, verbose=0)
            return prediction.flatten()
            
        except Exception as e:
            logger.error(f"❌ LSTM prediction failed: {str(e)}")
            raise
    
    def _calculate_confidence(self, X: np.ndarray, raw_prediction: np.ndarray) -> float:
        """
        Calculate confidence score based on model performance and prediction consistency
        """
        try:
            # Base confidence from validation directional accuracy
            base_confidence = self.validation_metrics.get('directional_accuracy', 0.5)
            
            # Adjust based on validation R2 score
            r2_score = self.validation_metrics.get('r2', 0.0)
            r2_bonus = max(0.0, r2_score) * 0.2  # Up to 20% bonus for good R2
            
            # Adjust based on validation MSE (lower is better)
            mse = self.validation_metrics.get('mse', float('inf'))
            if mse < 1000:  # Good MSE threshold
                mse_bonus = 0.1
            elif mse < 5000:  # Moderate MSE
                mse_bonus = 0.05
            else:
                mse_bonus = 0.0
            
            # Final confidence
            confidence = min(0.95, base_confidence + r2_bonus + mse_bonus)
            confidence = max(0.05, confidence)  # Minimum 5% confidence
            
            return float(confidence)
            
        except Exception as e:
            logger.warning(f"⚠️ Confidence calculation failed: {str(e)}")
            return 0.5
    
    def predict_next_price(self, recent_data: pd.DataFrame) -> PredictionResult:
        """
        Predict next price given recent market data
        
        Args:
            recent_data: DataFrame with recent OHLCV data (at least sequence_length rows)
            
        Returns:
            PredictionResult with next price prediction
        """
        try:
            if not self.is_trained:
                raise ValueError("❌ Model must be trained before making predictions")
            
            if len(recent_data) < self.sequence_length:
                raise ValueError(f"❌ Need at least {self.sequence_length} data points for prediction")
            
            # Prepare data (same process as training)
            df = recent_data.copy()
            df = self._add_technical_indicators(df)
            
            # Get the last sequence for prediction
            feature_data = df[self.config.input_features].iloc[-self.sequence_length:].values
            
            # Check for NaN values
            if np.isnan(feature_data).any():
                logger.warning("⚠️ NaN values in recent data, forward filling...")
                df = df.fillna(method='ffill').fillna(method='bfill')
                feature_data = df[self.config.input_features].iloc[-self.sequence_length:].values
            
            # Scale features
            scaled_features = self.feature_scaler.transform(feature_data)
            
            # Reshape for LSTM
            X = scaled_features.reshape(1, self.sequence_length, self.n_features)
            
            # Make prediction
            result = self.predict(X)
            
            # Add additional trading-relevant information
            current_price = df['close'].iloc[-1]
            predicted_price = result.prediction_value
            price_change = predicted_price - current_price
            price_change_pct = (price_change / current_price) * 100
            
            result.additional_info.update({
                'current_price': float(current_price),
                'price_change': float(price_change),
                'price_change_percent': float(price_change_pct),
                'direction': 'UP' if price_change > 0 else 'DOWN',
                'sequence_length_used': self.sequence_length
            })
            
            logger.info(f"📈 Price Prediction: {current_price:.2f} → {predicted_price:.2f} "
                       f"({price_change_pct:+.2f}%) [Confidence: {result.confidence_score:.2%}]")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Next price prediction failed: {str(e)}")
            raise
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Estimate feature importance (simplified approach for LSTM)
        Note: True feature importance in LSTM is complex; this provides a rough estimate
        """
        try:
            if not self.is_trained or self.feature_scaler is None:
                return {}
            
            # This is a simplified approach - in practice, more sophisticated methods
            # like SHAP or permutation importance would be used
            importance_scores = {}
            
            for i, feature in enumerate(self.config.input_features):
                # Use the scale range as a proxy for importance
                feature_range = (self.feature_scaler.data_max_[i] - 
                               self.feature_scaler.data_min_[i])
                importance_scores[feature] = float(feature_range)
            
            # Normalize to sum to 1
            total_importance = sum(importance_scores.values())
            if total_importance > 0:
                importance_scores = {k: v/total_importance 
                                  for k, v in importance_scores.items()}
            
            return importance_scores
            
        except Exception as e:
            logger.warning(f"⚠️ Feature importance calculation failed: {str(e)}")
            return {}