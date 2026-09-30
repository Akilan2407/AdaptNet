"""Reusable Congestion Predictor Interface.

Provides a unified programmatic class to load trained model artifacts,
preprocess streaming or historical telemetry, and predict future network
congestion score and categorical class.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import joblib
import numpy as np
import pandas as pd
from tensorflow import keras

from ml.congestion.config import (
    DEFAULT_METADATA_FILE,
    DEFAULT_MODEL_FILE,
    DEFAULT_SCALER_FILE,
    DEFAULT_TIMESTEPS,
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
)
from ml.congestion.metrics import score_to_class
from ml.congestion.preprocessing import reshape_to_sequences

logger = logging.getLogger("ml.congestion.congestion_predictor")


class CongestionPredictor:
    """Predicts future LAN congestion scores and classes using a trained GRU model."""

    def __init__(
        self,
        model_path: Union[str, Path] = DEFAULT_MODEL_FILE,
        scaler_path: Union[str, Path] = DEFAULT_SCALER_FILE,
        metadata_path: Optional[Union[str, Path]] = DEFAULT_METADATA_FILE,
        low_threshold: float = LOW_THRESHOLD,
        high_threshold: float = HIGH_THRESHOLD,
    ) -> None:
        """Initialize predictor by loading trained weights, scaler, and metadata.

        Args:
            model_path: Path to serialized .keras GRU model.
            scaler_path: Path to serialized .pkl StandardScaler.
            metadata_path: Optional path to model_metadata.json.
            low_threshold: Decision boundary between LOW and MEDIUM.
            high_threshold: Decision boundary between MEDIUM and HIGH.
        """
        self.model_path = Path(model_path)
        self.scaler_path = Path(scaler_path)
        self.metadata_path = Path(metadata_path) if metadata_path else None
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold

        self.model: Optional[keras.Model] = None
        self.scaler: Optional[Any] = None
        self.feature_columns: List[str] = []
        self.timesteps: int = DEFAULT_TIMESTEPS

        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Load Keras model, StandardScaler, and training metadata."""
        if not self.model_path.exists():
            logger.error("Model file not found at %s", self.model_path)
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        if not self.scaler_path.exists():
            logger.error("Scaler file not found at %s", self.scaler_path)
            raise FileNotFoundError(f"Scaler file not found: {self.scaler_path}")

        logger.info("Loading model from %s", self.model_path)
        self.model = keras.models.load_model(str(self.model_path))

        logger.info("Loading scaler from %s", self.scaler_path)
        self.scaler = joblib.load(str(self.scaler_path))

        # Recover feature column names and timesteps
        if self.metadata_path and self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r") as f:
                    meta = json.load(f)
                    self.feature_columns = meta.get("feature_columns", [])
                    self.timesteps = meta.get("timesteps", DEFAULT_TIMESTEPS)
            except Exception as e:
                logger.warning("Could not read metadata from %s: %s", self.metadata_path, e)

        if not self.feature_columns and hasattr(self.scaler, "feature_names_in_"):
            self.feature_columns = list(self.scaler.feature_names_in_)

    def classify_congestion(self, score: float) -> str:
        """Assign categorical congestion class based on continuous score."""
        return str(score_to_class(score, low_thresh=self.low_threshold, high_thresh=self.high_threshold))

    def prepare_input(
        self,
        telemetry_data: Union[pd.DataFrame, Dict[str, Any], np.ndarray, List[float]],
    ) -> np.ndarray:
        """Transform raw telemetry observation(s) into 3D input sequence tensor.

        Handles:
        - Single dictionary of features
        - Pandas DataFrame
        - Raw or scaled numpy array

        Args:
            telemetry_data: Input observation(s).

        Returns:
            3D numpy array of shape (samples, timesteps, features).
        """
        # If already a 3D tensor
        if isinstance(telemetry_data, np.ndarray) and telemetry_data.ndim == 3:
            return telemetry_data.astype(np.float32)

        # Convert dictionary to single-row DataFrame
        if isinstance(telemetry_data, dict):
            df = pd.DataFrame([telemetry_data])
        elif isinstance(telemetry_data, pd.DataFrame):
            df = telemetry_data.copy()
        elif isinstance(telemetry_data, (list, np.ndarray)):
            arr = np.asarray(telemetry_data, dtype=np.float32)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            # If array matches feature dimension, scale and reshape
            if arr.shape[1] == len(self.feature_columns):
                scaled = self.scaler.transform(arr)
                return reshape_to_sequences(scaled, feature_cols=self.feature_columns, timesteps=self.timesteps)
            return reshape_to_sequences(arr, timesteps=self.timesteps)
        else:
            raise TypeError(f"Unsupported telemetry data type: {type(telemetry_data)}")

        # Ensure all required features are present
        for col in self.feature_columns:
            if col not in df.columns:
                # If hist_mean_* is missing, mirror base feature if available
                if col.startswith("hist_mean_"):
                    base_col = col.replace("hist_mean_", "")
                    df[col] = df[base_col] if base_col in df.columns else 0.0
                else:
                    df[col] = 0.0

        # Extract numerical matrix in exact feature order
        matrix = df[self.feature_columns].fillna(0.0).to_numpy(dtype=np.float32)
        scaled_matrix = self.scaler.transform(matrix)
        tensor = reshape_to_sequences(scaled_matrix, feature_cols=self.feature_columns, timesteps=self.timesteps)
        return tensor

    def predict_congestion(
        self,
        telemetry_data: Union[pd.DataFrame, Dict[str, Any], np.ndarray, List[float]],
    ) -> Dict[str, Any]:
        """Predict future continuous congestion score and categorical class.

        Args:
            telemetry_data: Input features (dictionary, DataFrame, or numpy array).

        Returns:
            Dictionary containing predicted score, class, confidence, and metadata.
        """
        tensor = self.prepare_input(telemetry_data)
        raw_pred = self.model.predict(tensor, verbose=0)
        score = float(np.clip(raw_pred[0][0], 0.0, 1.0))
        cls_name = self.classify_congestion(score)

        # Confidence: distance from nearest decision threshold
        dist_low = abs(score - self.low_threshold)
        dist_high = abs(score - self.high_threshold)
        min_boundary_dist = min(dist_low, dist_high)
        # Normalize: distance of 0.165 (midpoint) yields confidence ~ 1.0
        confidence = float(np.clip(min_boundary_dist / 0.165, 0.50, 1.00))

        return {
            "future_congestion_score": round(score, 4),
            "future_congestion_class": cls_name,
            "confidence": round(confidence, 4),
            "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
            "input_timesteps": tensor.shape[1],
            "features_per_step": tensor.shape[2],
        }

    def predict_batch(self, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        """Run batch inference over a DataFrame and append prediction columns.

        Args:
            telemetry_df: DataFrame containing telemetry features.

        Returns:
            New DataFrame with predicted score and class columns.
        """
        tensor = self.prepare_input(telemetry_df)
        raw_preds = self.model.predict(tensor, verbose=0).flatten()
        scores = np.clip(raw_preds, 0.0, 1.0).astype(np.float64)
        classes = score_to_class(scores, low_thresh=self.low_threshold, high_thresh=self.high_threshold)

        result_df = telemetry_df.copy()
        result_df["predicted_congestion_score"] = [round(float(s), 4) for s in scores]
        result_df["predicted_congestion_class"] = classes
        return result_df
