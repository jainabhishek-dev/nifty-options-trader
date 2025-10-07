#!/usr/bin/env python3
"""
Base Machine Learning Model
Abstract base class for all ML models in the trading system
"""

import logging
import pickle
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
import numpy as np
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ModelConfig:
    """Configuration for ML models"""
    model_name: str
    model_type: str  # 'LSTM', 'RandomForest', 'SVM', etc.
    input_features: List[str]
    target_variable: str
    lookback_period: int
    prediction_horizon: int
    training_data_size: int
    validation_split: float
    hyperparameters: Dict[str, Any]
    created_at: datetime
    version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelConfig':
        """Create from dictionary"""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)

@dataclass
class PredictionResult:
    """Result from ML model prediction"""
    prediction_value: float
    confidence_score: float
    prediction_type: str  # 'price', 'direction', 'volatility'
    features_used: List[str]
    model_name: str
    timestamp: datetime
    additional_info: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

class BaseMLModel(ABC):
    """
    Abstract base class for all machine learning models
    Provides common functionality for training, prediction, and model management
    """
    
    def __init__(self, config: ModelConfig, data_dir: str = "data/ml_models"):
        """
        Initialize base ML model
        
        Args:
            config: Model configuration
            data_dir: Directory to save models and data
        """
        self.config = config
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Model state
        self.model = None
        self.is_trained = False
        self.training_history = []
        self.feature_scaler = None
        self.target_scaler = None
        
        # Performance metrics
        self.training_metrics = {}
        self.validation_metrics = {}
        self.last_prediction = None
        
        # File paths
        self.model_path = self.data_dir / f"{config.model_name}.pkl"
        self.config_path = self.data_dir / f"{config.model_name}_config.json"
        self.metrics_path = self.data_dir / f"{config.model_name}_metrics.json"
        
        logger.info(f"🧠 {self.config.model_name} initialized")
    
    @abstractmethod
    def _build_model(self) -> Any:
        """Build and compile the ML model (to be implemented by subclasses)"""
        pass
    
    @abstractmethod
    def _prepare_data(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare data for training (to be implemented by subclasses)"""
        pass
    
    @abstractmethod
    def _train_model(self, X_train: np.ndarray, y_train: np.ndarray, 
                    X_val: np.ndarray, y_val: np.ndarray) -> Dict[str, Any]:
        """Train the model (to be implemented by subclasses)"""
        pass
    
    @abstractmethod
    def _predict_raw(self, X: np.ndarray) -> np.ndarray:
        """Raw prediction without post-processing (to be implemented by subclasses)"""
        pass
    
    def train(self, training_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Train the model with provided data
        
        Args:
            training_data: DataFrame with features and target
            
        Returns:
            Training metrics and results
        """
        try:
            if training_data.empty:
                raise ValueError("❌ Training data is empty")
            
            logger.info(f"🔄 Training {self.config.model_name} with {len(training_data)} samples")
            
            # Validate required columns
            required_features = set(self.config.input_features + [self.config.target_variable])
            available_features = set(training_data.columns)
            missing_features = required_features - available_features
            
            if missing_features:
                raise ValueError(f"❌ Missing required features: {missing_features}")
            
            # Prepare data
            X, y = self._prepare_data(training_data)
            
            if len(X) == 0:
                raise ValueError("❌ No valid training samples after data preparation")
            
            # Split data
            split_idx = int(len(X) * (1 - self.config.validation_split))
            X_train, X_val = X[:split_idx], X[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]
            
            logger.info(f"📊 Training samples: {len(X_train)}, Validation samples: {len(X_val)}")
            
            # Build model
            self.model = self._build_model()
            
            # Train model
            training_results = self._train_model(X_train, y_train, X_val, y_val)
            
            # Update state
            self.is_trained = True
            self.training_history.append({
                'timestamp': datetime.now().isoformat(),
                'training_samples': len(X_train),
                'validation_samples': len(X_val),
                'results': training_results
            })
            
            # Save model
            self.save_model()
            
            logger.info(f"✅ {self.config.model_name} training completed successfully")
            return training_results
            
        except Exception as e:
            logger.error(f"❌ Training failed for {self.config.model_name}: {str(e)}")
            raise
    
    def predict(self, input_data: Union[pd.DataFrame, np.ndarray]) -> PredictionResult:
        """
        Make prediction with the trained model
        
        Args:
            input_data: Input features for prediction
            
        Returns:
            Prediction result with confidence
        """
        try:
            if not self.is_trained:
                raise ValueError(f"❌ Model {self.config.model_name} is not trained")
            
            if self.model is None:
                raise ValueError(f"❌ Model {self.config.model_name} not loaded")
            
            # Prepare input data
            if isinstance(input_data, pd.DataFrame):
                # Validate features
                missing_features = set(self.config.input_features) - set(input_data.columns)
                if missing_features:
                    raise ValueError(f"❌ Missing features for prediction: {missing_features}")
                
                X = input_data[self.config.input_features].values
            else:
                X = input_data
            
            # Ensure correct shape
            if len(X.shape) == 1:
                X = X.reshape(1, -1)
            
            # Apply feature scaling if available
            if self.feature_scaler is not None:
                X = self.feature_scaler.transform(X)
            
            # Get raw prediction
            raw_prediction = self._predict_raw(X)
            
            # Apply target scaling if available
            if self.target_scaler is not None:
                prediction_value = self.target_scaler.inverse_transform(raw_prediction.reshape(-1, 1))[0, 0]
            else:
                prediction_value = float(raw_prediction[0])
            
            # Calculate confidence (to be overridden by specific models)
            confidence_score = self._calculate_confidence(X, raw_prediction)
            
            # Create prediction result
            result = PredictionResult(
                prediction_value=prediction_value,
                confidence_score=confidence_score,
                prediction_type=self.config.target_variable,
                features_used=self.config.input_features,
                model_name=self.config.model_name,
                timestamp=datetime.now(),
                additional_info={
                    'raw_prediction': float(raw_prediction[0]),
                    'model_version': self.config.version
                }
            )
            
            self.last_prediction = result
            logger.debug(f"📈 Prediction: {prediction_value:.2f} (confidence: {confidence_score:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Prediction failed for {self.config.model_name}: {str(e)}")
            raise
    
    def _calculate_confidence(self, X: np.ndarray, raw_prediction: np.ndarray) -> float:
        """
        Calculate confidence score for prediction
        Base implementation - can be overridden by specific models
        """
        # Simple confidence based on validation metrics
        if 'accuracy' in self.validation_metrics:
            return float(self.validation_metrics['accuracy'])
        elif 'mse' in self.validation_metrics:
            # Convert MSE to confidence (lower MSE = higher confidence)
            mse = self.validation_metrics['mse']
            return max(0.0, min(1.0, 1.0 / (1.0 + mse)))
        else:
            return 0.5  # Default moderate confidence
    
    def save_model(self) -> bool:
        """Save model to disk"""
        try:
            if self.model is None:
                logger.warning(f"⚠️ No model to save for {self.config.model_name}")
                return False
            
            # Save model
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'feature_scaler': self.feature_scaler,
                    'target_scaler': self.target_scaler,
                    'is_trained': self.is_trained,
                    'training_history': self.training_history
                }, f)
            
            # Save config
            with open(self.config_path, 'w') as f:
                json.dump(self.config.to_dict(), f, indent=2)
            
            # Save metrics
            metrics_data = {
                'training_metrics': self.training_metrics,
                'validation_metrics': self.validation_metrics,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.metrics_path, 'w') as f:
                json.dump(metrics_data, f, indent=2)
            
            logger.info(f"💾 Model {self.config.model_name} saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save model {self.config.model_name}: {str(e)}")
            return False
    
    def load_model(self) -> bool:
        """Load model from disk"""
        try:
            if not self.model_path.exists():
                logger.warning(f"⚠️ No saved model found for {self.config.model_name}")
                return False
            
            # Load model
            with open(self.model_path, 'rb') as f:
                saved_data = pickle.load(f)
                self.model = saved_data['model']
                self.feature_scaler = saved_data.get('feature_scaler')
                self.target_scaler = saved_data.get('target_scaler')
                self.is_trained = saved_data.get('is_trained', False)
                self.training_history = saved_data.get('training_history', [])
            
            # Load metrics if available
            if self.metrics_path.exists():
                with open(self.metrics_path, 'r') as f:
                    metrics_data = json.load(f)
                    self.training_metrics = metrics_data.get('training_metrics', {})
                    self.validation_metrics = metrics_data.get('validation_metrics', {})
            
            logger.info(f"📁 Model {self.config.model_name} loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load model {self.config.model_name}: {str(e)}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get comprehensive model information"""
        return {
            'config': self.config.to_dict(),
            'is_trained': self.is_trained,
            'training_history': self.training_history,
            'training_metrics': self.training_metrics,
            'validation_metrics': self.validation_metrics,
            'last_prediction': self.last_prediction.to_dict() if self.last_prediction else None,
            'model_files': {
                'model_exists': self.model_path.exists(),
                'config_exists': self.config_path.exists(),
                'metrics_exists': self.metrics_path.exists()
            }
        }
    
    def delete_model(self) -> bool:
        """Delete saved model files"""
        try:
            deleted_files = []
            
            for file_path in [self.model_path, self.config_path, self.metrics_path]:
                if file_path.exists():
                    file_path.unlink()
                    deleted_files.append(file_path.name)
            
            # Reset model state
            self.model = None
            self.is_trained = False
            self.feature_scaler = None
            self.target_scaler = None
            
            logger.info(f"🗑️ Deleted model files: {deleted_files}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete model {self.config.model_name}: {str(e)}")
            return False