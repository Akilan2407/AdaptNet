"""SHAP Explainer Engine wrapping TensorFlow/Keras GRU model (Phase 16).

Implements a robust compatibility layer:
- Primary: shap.GradientExplainer (natively handles recurrent gradient computation)
- Fallback: shap.KernelExplainer (model-agnostic perturbation wrapper)
Records explainer type used, base value, 3D/2D SHAP attributions, and additivity metrics.
"""

import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import shap

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explainability.config import (
    FEATURES_PER_STEP,
    RECURRENT_FEATURE_NAMES,
    SHAP_TIME_AGGREGATION,
    TIMESTEPS,
)
from ml.explainability.feature_mapper import FeatureMapper
from ml.explainability.model_loader import ModelLoader

logger = logging.getLogger("ml.explainability.shap_explainer")


class SHAPExplainerWrapper:
    """Provides a unified SHAP explanation interface for the Phase 10 GRU model."""

    def __init__(
        self,
        model_loader: Optional[ModelLoader] = None,
        background_data: Optional[np.ndarray] = None,
    ):
        self.loader = model_loader or ModelLoader()
        self.model = self.loader.model
        self.background_data = (
            background_data
            if background_data is not None
            else self.loader.prepare_background_dataset()
        )

        self.explainer: Optional[Any] = None
        self.explainer_type: str = "Unknown"
        self.base_value: float = 0.5
        self.feature_mapper = FeatureMapper(self.loader.recurrent_feature_names)

        self._initialize_explainer()

    def _initialize_explainer(self) -> None:
        """Initialize the best compatible SHAP explainer for the Keras GRU model."""
        # 1. Calculate ground-truth base value from background predictions
        try:
            bg_preds = self.model.predict(self.background_data, verbose=0).flatten()
            self.base_value = float(np.mean(bg_preds))
        except Exception as e:
            logger.warning("Could not compute empirical base value: %s", e)
            self.base_value = 0.5

        # 2. Try GradientExplainer (Primary)
        try:
            logger.info("Attempting to initialize shap.GradientExplainer...")
            self.explainer = shap.GradientExplainer(self.model, self.background_data)
            self.explainer_type = "GradientExplainer"
            logger.info("GradientExplainer successfully initialized.")
            return
        except Exception as e:
            logger.warning("GradientExplainer initialization failed: %s", e)

        # 3. Model-agnostic Fallback: KernelExplainer
        try:
            logger.info("Attempting fallback to shap.KernelExplainer...")
            timesteps = self.loader.timesteps
            features_per_step = len(self.loader.recurrent_feature_names)

            def model_predict_flat(x_flat: np.ndarray) -> np.ndarray:
                x_3d = np.asarray(x_flat, dtype=np.float32).reshape((-1, timesteps, features_per_step))
                return self.model.predict(x_3d, verbose=0).flatten()

            bg_flat = self.background_data.reshape((len(self.background_data), -1))
            self.explainer = shap.KernelExplainer(model_predict_flat, bg_flat)
            self.explainer_type = "KernelExplainer"
            logger.info("KernelExplainer successfully initialized as fallback.")
        except Exception as e:
            logger.error("All SHAP explainer initializations failed: %s", e)
            raise RuntimeError(f"Could not initialize any SHAP explainer: {e}")

    def explain_sample(
        self,
        sample_tensor: np.ndarray,
        time_agg_mode: str = SHAP_TIME_AGGREGATION,
    ) -> Dict[str, Any]:
        """Generate SHAP feature attribution for a single sequence observation.

        Args:
            sample_tensor: Sequence tensor of shape (1, 2, 11) or (2, 11).
            time_agg_mode: Temporal aggregation mode.

        Returns:
            Dictionary containing prediction score, base value, feature attributions,
            additivity difference, and ranked feature contributions.
        """
        arr = np.asarray(sample_tensor, dtype=np.float32)
        if arr.ndim == 2:
            arr = np.expand_dims(arr, axis=0)

        # Compute model prediction
        pred_arr = self.model.predict(arr, verbose=0).flatten()
        pred_score = float(pred_arr[0])

        # Compute SHAP values
        if self.explainer_type == "GradientExplainer":
            raw_shap = self.explainer.shap_values(arr)
            # Unpack list if returned
            if isinstance(raw_shap, list):
                raw_shap = raw_shap[0]
            # Output shape: (1, 2, 11, 1) or (1, 2, 11)
            raw_shap_arr = np.asarray(raw_shap, dtype=np.float32)
            if raw_shap_arr.ndim == 4 and raw_shap_arr.shape[-1] == 1:
                raw_shap_arr = np.squeeze(raw_shap_arr, axis=-1)
            shap_2step = raw_shap_arr[0]  # (2, 11)
        else:
            # KernelExplainer on flattened 1D array
            arr_flat = arr.reshape((1, -1))
            raw_shap = self.explainer.shap_values(arr_flat, nsamples=60)
            if isinstance(raw_shap, list):
                raw_shap = raw_shap[0]
            raw_shap_arr = np.asarray(raw_shap, dtype=np.float32).reshape((self.loader.timesteps, -1))
            shap_2step = raw_shap_arr  # (2, 11)

        # Temporal Aggregation
        signed_attrs, abs_mags = self.feature_mapper.aggregate_temporal_shap(
            shap_2step, mode=time_agg_mode
        )

        shap_sum = float(np.sum(signed_attrs))
        additivity_diff = abs((self.base_value + shap_sum) - pred_score)

        # Build feature contributions list
        feature_contributions = []
        for idx, feat_name in enumerate(self.loader.recurrent_feature_names):
            s_val = float(signed_attrs[idx])
            a_val = float(abs_mags[idx])
            direction = self.feature_mapper.determine_direction(s_val)
            feature_contributions.append({
                "feature_name": feat_name,
                "shap_value": s_val,
                "absolute_shap_value": a_val,
                "direction": direction,
                "index": idx,
            })

        # Rank features by absolute magnitude (highest first)
        feature_contributions.sort(key=lambda x: x["absolute_shap_value"], reverse=True)
        for rank_idx, item in enumerate(feature_contributions, start=1):
            item["feature_rank"] = rank_idx

        return {
            "predicted_congestion_score": pred_score,
            "base_value": self.base_value,
            "shap_sum": shap_sum,
            "additivity_difference": additivity_diff,
            "explainer_type": self.explainer_type,
            "feature_contributions": feature_contributions,
            "raw_shap_tensor": shap_2step.tolist(),
        }
