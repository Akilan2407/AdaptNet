"""Feature Mapping and Temporal SHAP Aggregation Service (Phase 16).

Establishes the exact index-to-name alignment with the Phase 10 GRU model input,
extracts and constructs 3D sequence tensors from raw telemetry or trace records,
and provides temporal aggregation methods to distill (timesteps, features) SHAP values.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explainability.config import (
    AGG_LAST_TIMESTEP,
    AGG_MEAN,
    AGG_MEAN_ABSOLUTE,
    AGG_SUM,
    DIRECTION_DECREASED,
    DIRECTION_INCREASED,
    DIRECTION_NEUTRAL,
    FEATURES_PER_STEP,
    RECURRENT_FEATURE_NAMES,
    SCALER_FEATURE_COLUMNS,
    SHAP_TIME_AGGREGATION,
    TIMESTEPS,
)


class FeatureMapper:
    """Manages feature order, sequence alignment, and temporal SHAP aggregation."""

    def __init__(self, feature_names: Optional[List[str]] = None):
        self.feature_names = feature_names or list(RECURRENT_FEATURE_NAMES)
        self.name_to_index = {name: idx for idx, name in enumerate(self.feature_names)}
        self.index_to_name = {idx: name for idx, name in enumerate(self.feature_names)}

    def get_feature_name(self, index: int) -> str:
        """Return feature name for given recurrent model input index."""
        return self.index_to_name.get(index, f"feature_{index}")

    def get_feature_index(self, name: str) -> Optional[int]:
        """Return index for given feature name."""
        return self.name_to_index.get(name)

    @staticmethod
    def determine_direction(shap_value: float, threshold: float = 1e-6) -> str:
        """Determine signed semantic direction from SHAP value."""
        if shap_value > threshold:
            return DIRECTION_INCREASED
        elif shap_value < -threshold:
            return DIRECTION_DECREASED
        return DIRECTION_NEUTRAL

    @classmethod
    def aggregate_temporal_shap(
        cls,
        shap_tensor: np.ndarray,
        mode: str = SHAP_TIME_AGGREGATION,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Aggregate 3D or 2D temporal SHAP values into feature importance vectors.

        Args:
            shap_tensor: Array of shape (timesteps, features) or (samples, timesteps, features).
            mode: Aggregation mode ("mean_absolute", "mean", "sum", "last_timestep").

        Returns:
            Tuple of (signed_attributions, absolute_magnitudes).
            If input had shape (samples, timesteps, features), returns arrays of shape (samples, features).
            If input had shape (timesteps, features), returns arrays of shape (features,).
        """
        arr = np.asarray(shap_tensor, dtype=np.float32)

        # Squeeze potential trailing single dimension from TF output (e.g. (..., 1))
        if arr.ndim >= 3 and arr.shape[-1] == 1 and arr.shape[-2] == FEATURES_PER_STEP:
            arr = np.squeeze(arr, axis=-1)

        single_sample = False
        if arr.ndim == 2:
            # Shape is (timesteps, features)
            single_sample = True
            arr = np.expand_dims(arr, axis=0)  # (1, timesteps, features)

        if arr.ndim != 3:
            raise ValueError(f"Expected 2D or 3D SHAP tensor, got shape {arr.shape}")

        # Compute signed aggregation across time (axis=1)
        if mode == AGG_MEAN or mode == AGG_MEAN_ABSOLUTE:
            signed = np.mean(arr, axis=1)
        elif mode == AGG_SUM:
            signed = np.sum(arr, axis=1)
        elif mode == AGG_LAST_TIMESTEP:
            signed = arr[:, -1, :]
        else:
            signed = np.mean(arr, axis=1)

        # Compute magnitude across time (axis=1)
        if mode == AGG_MEAN_ABSOLUTE:
            magnitude = np.mean(np.abs(arr), axis=1)
        elif mode == AGG_SUM:
            magnitude = np.sum(np.abs(arr), axis=1)
        else:
            magnitude = np.abs(signed)

        if single_sample:
            return signed[0], magnitude[0]

        return signed, magnitude

    @classmethod
    def extract_raw_features_from_trace(
        cls,
        trace_record: Dict[str, Any],
    ) -> Dict[str, float]:
        """Extract all 11 recurrent base feature values from a decision trace dict."""
        feat_dict = trace_record.get("stage_2_features", {})
        mon_dict = trace_record.get("stage_1_monitoring", {})
        prof_dict = trace_record.get("stage_3_user_profile", {})

        cid = prof_dict.get("cluster_id", trace_record.get("cluster_id"))
        try:
            cluster_val = float(cid) if cid is not None and pd.notna(cid) else 0.0
        except Exception:
            cluster_val = 0.0

        throughput = float(feat_dict.get("throughput_mbps", mon_dict.get("throughput", trace_record.get("throughput_mbps", 0.0)) or 0.0))
        rtt = float(feat_dict.get("rtt_ms", mon_dict.get("rtt", trace_record.get("rtt_ms", 0.0)) or 0.0))
        loss = float(feat_dict.get("packet_loss_percent", mon_dict.get("packet_loss", trace_record.get("packet_loss_percent", 0.0)) or 0.0))
        conns = float(feat_dict.get("active_connections", mon_dict.get("active_connections", trace_record.get("active_connections", 0.0)) or 0.0))

        throughput_std = float(feat_dict.get("throughput_std", trace_record.get("throughput_std", 0.0)) or 0.0)
        rtt_std = float(feat_dict.get("rtt_std", trace_record.get("rtt_std", 0.0)) or 0.0)
        loss_std = float(feat_dict.get("packet_loss_std", trace_record.get("packet_loss_std", 0.0)) or 0.0)
        total_flow = float(feat_dict.get("total_flow_count", trace_record.get("total_flow_count", 1.0)) or 1.0)
        tcp_ratio = float(feat_dict.get("tcp_flow_ratio", trace_record.get("tcp_flow_ratio", 1.0)) or 1.0)
        udp_ratio = float(feat_dict.get("udp_flow_ratio", trace_record.get("udp_flow_ratio", 0.0)) or 0.0)

        return {
            "cluster_id": cluster_val,
            "throughput_mbps": throughput,
            "rtt_ms": rtt,
            "packet_loss_percent": loss,
            "active_connections": conns,
            "throughput_std": throughput_std,
            "rtt_std": rtt_std,
            "packet_loss_std": loss_std,
            "total_flow_count": total_flow,
            "tcp_flow_ratio": tcp_ratio,
            "udp_flow_ratio": udp_ratio,
        }
