"""Safe artifact loader and sequence preparation for Phase 10 GRU model."""

import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import joblib
import numpy as np
import pandas as pd
from tensorflow import keras

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.congestion.preprocessing import reshape_to_sequences
from ml.explainability.config import (
    BACKGROUND_SAMPLE_SIZE,
    DEFAULT_CONGESTION_DATASET_PATH,
    DEFAULT_METADATA_PATH,
    DEFAULT_MODEL_PATH,
    DEFAULT_SCALER_PATH,
    DEFAULT_TEST_DATASET_PATH,
    FEATURES_PER_STEP,
    RANDOM_SEED,
    RECURRENT_FEATURE_NAMES,
    SCALER_FEATURE_COLUMNS,
    TIMESTEPS,
)

logger = logging.getLogger("ml.explainability.model_loader")


class ModelLoader:
    """Loads and encapsulates Phase 10 GRU model, scaler, and background tensors."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        scaler_path: Optional[Path] = None,
        metadata_path: Optional[Path] = None,
    ):
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.scaler_path = scaler_path or DEFAULT_SCALER_PATH
        self.metadata_path = metadata_path or DEFAULT_METADATA_PATH

        self.model: Optional[keras.Model] = None
        self.scaler: Optional[Any] = None
        self.metadata: Dict[str, Any] = {}
        self.feature_columns: List[str] = list(SCALER_FEATURE_COLUMNS)
        self.recurrent_feature_names: List[str] = list(RECURRENT_FEATURE_NAMES)
        self.timesteps: int = TIMESTEPS

        self._load_artifacts()

    def _load_artifacts(self) -> None:
        """Load Keras model, fitted StandardScaler, and training metadata."""
        if not self.model_path.exists():
            raise FileNotFoundError(f"GRU model file not found: {self.model_path}")
        if not self.scaler_path.exists():
            raise FileNotFoundError(f"Scaler file not found: {self.scaler_path}")

        logger.info("Loading GRU model from %s", self.model_path)
        self.model = keras.models.load_model(str(self.model_path))

        logger.info("Loading StandardScaler from %s", self.scaler_path)
        self.scaler = joblib.load(str(self.scaler_path))

        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
                self.feature_columns = self.metadata.get("feature_columns", self.feature_columns)
                self.timesteps = self.metadata.get("timesteps", self.timesteps)

        # Preload congestion dataset for exact historical sequence lookups
        self.dataset_df = pd.DataFrame()
        for p in (DEFAULT_TEST_DATASET_PATH, DEFAULT_CONGESTION_DATASET_PATH):
            if p.exists():
                try:
                    df = pd.read_csv(p)
                    if not df.empty:
                        self.dataset_df = df
                        break
                except Exception:
                    pass

    def prepare_sequence_tensor(
        self,
        features_dict: Dict[str, float],
        device_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> np.ndarray:
        """Convert an observation into a 3D sequence tensor (1, 2, 11).

        If device_id and timestamp match an exact recorded sequence in the
        congestion dataset, reuses the true historical lookback tensor.
        Otherwise constructs the 2-step trajectory from current metrics.
        """
        # Attempt exact sequence lookup first
        if device_id and not self.dataset_df.empty and "device_id" in self.dataset_df.columns:
            dev_rows = self.dataset_df[self.dataset_df["device_id"] == device_id]
            if not dev_rows.empty and timestamp and "prediction_timestamp" in dev_rows.columns:
                try:
                    target_dt = pd.to_datetime(timestamp)
                    pred_dts = pd.to_datetime(dev_rows["prediction_timestamp"])
                    time_diffs = (pred_dts - target_dt).abs().dt.total_seconds()
                    closest_idx = time_diffs.idxmin()
                    if time_diffs.loc[closest_idx] <= 5.0:
                        matched_row = dev_rows.loc[closest_idx:closest_idx]
                        matrix = matched_row[self.feature_columns].fillna(0.0).to_numpy(dtype=np.float32)
                        scaled_matrix = self.scaler.transform(matrix)
                        return reshape_to_sequences(scaled_matrix, feature_cols=self.feature_columns, timesteps=self.timesteps)
                except Exception as e:
                    logger.debug("Sequence lookup exception: %s", e)

        # Fallback to direct feature dictionary reconstruction
        row_dict = {}
        for col in self.recurrent_feature_names:
            val = float(features_dict.get(col, 0.0))
            row_dict[col] = val
            hist_col = f"hist_mean_{col}"
            row_dict[hist_col] = float(features_dict.get(hist_col, val))

        df = pd.DataFrame([row_dict])
        matrix = df[self.feature_columns].fillna(0.0).to_numpy(dtype=np.float32)
        scaled_matrix = self.scaler.transform(matrix)
        tensor = reshape_to_sequences(scaled_matrix, feature_cols=self.feature_columns, timesteps=self.timesteps)
        return tensor

    def prepare_background_dataset(
        self,
        sample_size: int = BACKGROUND_SAMPLE_SIZE,
        dataset_path: Optional[Path] = None,
    ) -> np.ndarray:
        """Load background sequence tensor from congestion dataset for SHAP reference.

        Args:
            sample_size: Maximum number of background samples.
            dataset_path: Path to dataset CSV. Defaults to congestion_dataset.csv or test_dataset.csv.

        Returns:
            3D numpy array of shape (samples, 2, 11).
        """
        path = dataset_path or (
            DEFAULT_CONGESTION_DATASET_PATH
            if DEFAULT_CONGESTION_DATASET_PATH.exists()
            else DEFAULT_TEST_DATASET_PATH
        )

        if not path.exists():
            # Fallback synthetic neutral baseline
            logger.warning("Dataset not found at %s. Using neutral zero background.", path)
            return np.zeros((1, self.timesteps, FEATURES_PER_STEP), dtype=np.float32)

        df = pd.read_csv(path)
        if df.empty:
            return np.zeros((1, self.timesteps, FEATURES_PER_STEP), dtype=np.float32)

        # Ensure all 21 scaler columns exist
        for col in self.feature_columns:
            if col not in df.columns:
                if col.startswith("hist_mean_"):
                    base = col.replace("hist_mean_", "")
                    df[col] = df[base] if base in df.columns else 0.0
                else:
                    df[col] = 0.0

        if len(df) > sample_size:
            df = df.sample(n=sample_size, random_state=RANDOM_SEED).reset_index(drop=True)

        matrix = df[self.feature_columns].fillna(0.0).to_numpy(dtype=np.float32)
        scaled_matrix = self.scaler.transform(matrix)
        sequence_tensor = reshape_to_sequences(scaled_matrix, feature_cols=self.feature_columns, timesteps=self.timesteps)
        return sequence_tensor.astype(np.float32)
