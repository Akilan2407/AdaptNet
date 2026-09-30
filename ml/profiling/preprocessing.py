"""Data Preprocessing and Device-Level Aggregation for Phase 8 Profiling.

Handles:
- Loading network feature datasets from Phase 7
- Verifying presence of required behavior features
- Aggregating multi-row flow telemetry to single device-level vectors
- Documented missing-value imputation (median with safe zero fallback)
- Feature normalization using scikit-learn StandardScaler
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from ml.profiling.config import (
    ALL_CANDIDATE_FEATURES,
    CORE_BEHAVIOR_FEATURES,
    FEATURE_ALIASES,
)

logger = logging.getLogger("ml.profiling.preprocessing")


def load_feature_dataset(filepath: Union[str, Path]) -> pd.DataFrame:
    """Load Phase 7 network features dataset from CSV.

    Args:
        filepath: Path to network_features.csv

    Returns:
        Loaded DataFrame.

    Raises:
        FileNotFoundError: If filepath does not exist.
        ValueError: If file is empty or missing 'device_id'.
    """
    path = Path(filepath)
    if not path.exists():
        logger.error("Feature dataset not found at %s", path)
        raise FileNotFoundError(f"Feature dataset not found: {path}")

    df = pd.read_csv(path)
    if df.empty:
        logger.error("Feature dataset at %s is empty", path)
        raise ValueError(f"Feature dataset at {path} is empty")

    if "device_id" not in df.columns:
        logger.error("Required column 'device_id' is missing from %s", path)
        raise ValueError("Missing required identifier column 'device_id'")

    logger.info("Successfully loaded %d records from %s", len(df), path)
    return df


def validate_required_features(
    df: pd.DataFrame,
    candidate_features: Optional[List[str]] = None,
) -> Tuple[List[str], List[str]]:
    """Validate which behavior features exist in the Phase 7 DataFrame.

    Handles documented aliases (e.g. 'flow_count' -> 'total_flow_count').

    Args:
        df: Input DataFrame
        candidate_features: List of feature names to verify

    Returns:
        Tuple of (available_features, missing_features)
    """
    if candidate_features is None:
        candidate_features = list(ALL_CANDIDATE_FEATURES)

    available: List[str] = []
    missing: List[str] = []

    # Columns present in df (or derivable like active_hours_count if 'hour' present)
    df_cols = set(df.columns)

    for feat in candidate_features:
        # Check direct column match
        if feat in df_cols:
            available.append(feat)
        # Check alias match
        elif feat in FEATURE_ALIASES and FEATURE_ALIASES[feat] in df_cols:
            resolved = FEATURE_ALIASES[feat]
            available.append(resolved)
        # Check derivable temporal feature
        elif feat == "active_hours_count" and "hour" in df_cols:
            available.append(feat)
        else:
            missing.append(feat)

    # De-duplicate while preserving order
    seen = set()
    deduped_available = []
    for f in available:
        if f not in seen:
            seen.add(f)
            deduped_available.append(f)

    logger.info("Feature validation: %d available, %d missing", len(deduped_available), len(missing))
    if missing:
        logger.warning("The following candidate features were not found in input: %s", missing)

    return deduped_available, missing


def aggregate_device_behavior(
    df: pd.DataFrame,
    feature_list: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Aggregate multi-row flow telemetry to device-level behavior vectors.

    Produces exactly one behavior profile vector per unique device_id.

    Args:
        df: Raw Phase 7 network features DataFrame
        feature_list: Optional list of validated features to retain

    Returns:
        DataFrame indexed by device_id with device-level metrics.
    """
    if df.empty or "device_id" not in df.columns:
        raise ValueError("Cannot aggregate empty DataFrame or DataFrame without 'device_id'")

    grouped = df.groupby("device_id")

    # Metrics that are already device aggregations in Phase 7
    aggregation_dict: Dict[str, Any] = {}

    potential_agg_cols = [
        "mean_throughput_mbps",
        "max_throughput_mbps",
        "min_throughput_mbps",
        "throughput_std",
        "mean_rtt_ms",
        "max_rtt_ms",
        "rtt_std",
        "mean_packet_loss_percent",
        "max_packet_loss_percent",
        "packet_loss_std",
        "mean_active_connections",
        "total_flow_count",
        "tcp_flow_count",
        "udp_flow_count",
        "tcp_flow_ratio",
        "udp_flow_ratio",
    ]

    for col in potential_agg_cols:
        if col in df.columns:
            aggregation_dict[col] = "first"

    # Fallback for raw flow metrics if device aggregates aren't pre-computed
    if "throughput_mbps" in df.columns and "mean_throughput_mbps" not in df.columns:
        aggregation_dict["throughput_mbps"] = "mean"
    if "rtt_ms" in df.columns and "mean_rtt_ms" not in df.columns:
        aggregation_dict["rtt_ms"] = "mean"
    if "packet_loss_percent" in df.columns and "mean_packet_loss_percent" not in df.columns:
        aggregation_dict["packet_loss_percent"] = "mean"
    if "active_connections" in df.columns and "mean_active_connections" not in df.columns:
        aggregation_dict["active_connections"] = "mean"

    # Perform group aggregation
    device_df = grouped.agg(aggregation_dict) if aggregation_dict else pd.DataFrame(index=grouped.groups.keys())

    # Ensure device_id is a column and sorted deterministically
    device_df = device_df.reset_index()

    # Temporal feature: active_hours_count (number of distinct hours active)
    if "hour" in df.columns:
        active_hours = grouped["hour"].nunique().reset_index()
        active_hours.rename(columns={"hour": "active_hours_count"}, inplace=True)
        device_df = device_df.merge(active_hours, on="device_id", how="left")

    # If total_flow_count is missing, compute from group row counts
    if "total_flow_count" not in device_df.columns:
        counts = grouped.size().reset_index(name="total_flow_count")
        device_df = device_df.merge(counts, on="device_id", how="left")

    # Sort by device_id for determinism
    device_df.sort_values(by="device_id", inplace=True)
    device_df.reset_index(drop=True, inplace=True)

    logger.info("Aggregated telemetry into %d unique device vectors", len(device_df))
    return device_df


def handle_missing_values(
    device_df: pd.DataFrame,
    feature_cols: List[str],
) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Handle missing values using documented median imputation with safe fallback.

    Strategy:
    1. If a feature contains missing values across some devices, impute with the
       median of the available device values.
    2. If a feature is 100% missing (e.g. UDP-only capture or latency unmeasured
       across all devices), median is NaN; impute safe baseline 0.0 and log clearly.
    3. Preserves original DataFrame without in-place mutation.

    Args:
        device_df: Device-level DataFrame
        feature_cols: List of features to process

    Returns:
        Tuple of (clean_device_df, imputation_report)
    """
    clean_df = device_df.copy()
    imputation_report: Dict[str, str] = {}

    for col in feature_cols:
        if col not in clean_df.columns:
            continue

        null_count = clean_df[col].isnull().sum()
        if null_count > 0:
            median_val = clean_df[col].median(skipna=True)
            if pd.isna(median_val):
                # 100% missing across all devices
                clean_df[col] = clean_df[col].fillna(0.0)
                strategy = f"100% missing ({null_count}/{len(clean_df)}), imputed fallback 0.0"
                logger.warning(
                    "Feature '%s' is 100%% NaN across all devices. Imputed fallback 0.0.",
                    col,
                )
            else:
                clean_df[col] = clean_df[col].fillna(median_val)
                strategy = f"imputed median {median_val:.4f} ({null_count}/{len(clean_df)} nulls)"
                logger.info(
                    "Feature '%s': imputed median %.4f for %d missing values",
                    col,
                    median_val,
                    null_count,
                )
            imputation_report[col] = strategy
        else:
            imputation_report[col] = "complete (no nulls)"

    return clean_df, imputation_report


def scale_features(
    device_df: pd.DataFrame,
    feature_cols: List[str],
    scaler: Optional[StandardScaler] = None,
) -> Tuple[np.ndarray, StandardScaler, List[str]]:
    """Normalize clustering features using scikit-learn StandardScaler.

    Standardizes features by removing the mean and scaling to unit variance.

    Args:
        device_df: Preprocessed device-level DataFrame
        feature_cols: List of numerical features to scale
        scaler: Optional pre-fitted StandardScaler

    Returns:
        Tuple of (X_scaled numpy array, fitted_scaler, validated_feature_cols)

    Raises:
        ValueError: If feature_cols is empty or dataframe has no rows.
    """
    if not feature_cols:
        raise ValueError("Cannot scale empty feature list")
    if device_df.empty:
        raise ValueError("Cannot scale empty DataFrame")

    # Verify all columns exist and are numeric
    missing = [c for c in feature_cols if c not in device_df.columns]
    if missing:
        raise KeyError(f"Columns not found in DataFrame: {missing}")

    X_raw = device_df[feature_cols].to_numpy(dtype=np.float64)

    if scaler is None:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_raw)
        logger.info("Fitted new StandardScaler on %d samples x %d features", X_raw.shape[0], X_raw.shape[1])
    else:
        X_scaled = scaler.transform(X_raw)
        logger.info("Transformed %d samples using pre-fitted StandardScaler", X_raw.shape[0])

    return X_scaled, scaler, feature_cols
