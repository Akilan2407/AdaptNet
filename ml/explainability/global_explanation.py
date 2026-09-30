"""Global Feature Importance Service using SHAP (Phase 16).

Aggregates SHAP feature attributions across an entire evaluation split,
computing mean absolute impact, signed directions, and feature rankings.
"""

import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explainability.config import (
    DEFAULT_GLOBAL_CSV,
    EXPLANATION_SAMPLE_SIZE,
    FEATURES_PER_STEP,
    RANDOM_SEED,
    RECURRENT_FEATURE_NAMES,
    SHAP_TIME_AGGREGATION,
)
from ml.explainability.model_loader import ModelLoader
from ml.explainability.shap_explainer import SHAPExplainerWrapper

logger = logging.getLogger("ml.explainability.global_explanation")


class GlobalExplainer:
    """Computes population-level SHAP feature importance across evaluation datasets."""

    def __init__(
        self,
        shap_explainer: Optional[SHAPExplainerWrapper] = None,
        output_csv: Optional[Path] = None,
    ):
        self.explainer = shap_explainer or SHAPExplainerWrapper()
        self.output_csv = output_csv or DEFAULT_GLOBAL_CSV
        self.feature_names = self.explainer.loader.recurrent_feature_names

    def compute_global_importance(
        self,
        evaluation_tensors: Optional[np.ndarray] = None,
        sample_size: int = EXPLANATION_SAMPLE_SIZE,
    ) -> pd.DataFrame:
        """Compute global feature importance across evaluation samples.

        Args:
            evaluation_tensors: Optional 3D tensor of shape (N, 2, 11). If None, loads
                                from Phase 10 congestion dataset.
            sample_size: Maximum samples to explain.

        Returns:
            DataFrame containing feature_name, mean_absolute_shap, mean_signed_shap,
            median_absolute_shap, sample_count, rank.
        """
        if evaluation_tensors is None:
            evaluation_tensors = self.explainer.loader.prepare_background_dataset(
                sample_size=sample_size
            )

        n_samples = len(evaluation_tensors)
        if n_samples == 0:
            logger.warning("Empty evaluation dataset. Cannot compute global importance.")
            return pd.DataFrame()

        logger.info("Computing global SHAP importance over %d samples...", n_samples)

        all_signed = []
        all_abs = []

        for i in range(n_samples):
            sample = evaluation_tensors[i:i + 1]
            res = self.explainer.explain_sample(sample, time_agg_mode=SHAP_TIME_AGGREGATION)
            # Reconstruct vector in canonical feature order
            contribs = {c["feature_name"]: c for c in res["feature_contributions"]}
            s_vec = [contribs[name]["shap_value"] for name in self.feature_names]
            a_vec = [contribs[name]["absolute_shap_value"] for name in self.feature_names]
            all_signed.append(s_vec)
            all_abs.append(a_vec)

        signed_mat = np.array(all_signed, dtype=np.float32)  # (N, 11)
        abs_mat = np.array(all_abs, dtype=np.float32)        # (N, 11)

        mean_abs = np.mean(abs_mat, axis=0)
        mean_signed = np.mean(signed_mat, axis=0)
        median_abs = np.median(abs_mat, axis=0)

        records = []
        for idx, feat_name in enumerate(self.feature_names):
            records.append({
                "feature_name": feat_name,
                "mean_absolute_shap": round(float(mean_abs[idx]), 6),
                "mean_signed_shap": round(float(mean_signed[idx]), 6),
                "median_absolute_shap": round(float(median_abs[idx]), 6),
                "sample_count": n_samples,
            })

        df = pd.DataFrame(records)
        df = df.sort_values(by="mean_absolute_shap", ascending=False).reset_index(drop=True)
        df["rank"] = df.index + 1

        # Export to CSV
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.output_csv, index=False)
        logger.info("Global SHAP importance exported to %s", self.output_csv)

        return df
