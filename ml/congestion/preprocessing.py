"""Preprocessing and Telemetry Preparation for Phase 9 Congestion Dataset.

Handles:
- Loading Phase 7 network features
- Correct timestamp parsing and chronological sorting (no random shuffling)
- Contextual enrichment with Phase 8 behavior cluster IDs
- Sampling interval detection and irregular timestamp characterization
- Documented missing-feature imputation and tracking
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler

from ml.congestion.config import (
    CANDIDATE_CONGESTION_FEATURES,
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PROFILES_PATH,
    DEFAULT_TEST_PATH,
    DEFAULT_TIMESTEPS,
    DEFAULT_TRAIN_PATH,
    DEFAULT_VAL_PATH,
)

logger = logging.getLogger("ml.congestion.preprocessing")


def load_and_prepare_telemetry(
    features_path: Union[str, Path] = DEFAULT_INPUT_PATH,
    profiles_path: Optional[Union[str, Path]] = DEFAULT_PROFILES_PATH,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Load Phase 7 network features, parse timestamps, and sort chronologically.

    Optionally merges Phase 8 behavior cluster IDs (by device_id) as contextual
    behavioral features.

    Args:
        features_path: Path to Phase 7 network_features.csv
        profiles_path: Optional path to Phase 8 behavior_profiles.csv

    Returns:
        Tuple of (prepared_df, ingestion_stats)

    Raises:
        FileNotFoundError: If features_path does not exist.
        ValueError: If dataset is empty or lacks 'timestamp'.
    """
    f_path = Path(features_path)
    if not f_path.exists():
        logger.error("Features dataset not found at %s", f_path)
        raise FileNotFoundError(f"Features dataset not found: {f_path}")

    raw_df = pd.read_csv(f_path)
    total_records = len(raw_df)

    if total_records == 0:
        logger.error("Dataset at %s is empty", f_path)
        raise ValueError(f"Dataset at {f_path} is empty")

    if "timestamp" not in raw_df.columns:
        logger.error("Required 'timestamp' column is missing from %s", f_path)
        raise ValueError("Missing required column 'timestamp'")

    # 1. Parse timestamps and identify invalid dates
    df = raw_df.copy()
    parsed_timestamps = pd.to_datetime(df["timestamp"], errors="coerce")
    invalid_mask = parsed_timestamps.isna()
    invalid_records = int(invalid_mask.sum())

    if invalid_records > 0:
        logger.warning("Found %d records with unparseable timestamps; discarding.", invalid_records)
        df = df[~invalid_mask].copy()
        df["timestamp"] = parsed_timestamps[~invalid_mask]
    else:
        df["timestamp"] = parsed_timestamps

    # 2. Strict Chronological Sort (Never random shuffle)
    df = df.sort_values(by="timestamp", ascending=True).reset_index(drop=True)

    # 3. Contextual Enrichment with Phase 8 Cluster IDs (if available)
    cluster_merged = False
    if profiles_path:
        p_path = Path(profiles_path)
        if p_path.exists():
            try:
                profiles_df = pd.read_csv(p_path)
                if "device_id" in profiles_df.columns and "cluster_id" in profiles_df.columns:
                    cluster_map = profiles_df.set_index("device_id")["cluster_id"].to_dict()
                    df["cluster_id"] = df["device_id"].map(cluster_map)
                    cluster_merged = True
                    logger.info("Successfully merged Phase 8 cluster IDs for %d devices", len(cluster_map))
            except Exception as e:
                logger.warning("Could not merge Phase 8 profiles from %s: %s", p_path, e)

    if not cluster_merged and "cluster_id" not in df.columns:
        df["cluster_id"] = np.nan

    valid_records = len(df)
    logger.info(
        "Prepared telemetry: %d total, %d valid, %d removed. Time range: %s to %s",
        total_records,
        valid_records,
        invalid_records,
        df["timestamp"].min() if valid_records > 0 else "N/A",
        df["timestamp"].max() if valid_records > 0 else "N/A",
    )

    ingestion_stats = {
        "total_records": total_records,
        "valid_records": valid_records,
        "removed_records": invalid_records,
        "time_start": str(df["timestamp"].min()) if valid_records > 0 else None,
        "time_end": str(df["timestamp"].max()) if valid_records > 0 else None,
        "cluster_info_present": cluster_merged,
    }

    return df, ingestion_stats


def detect_sampling_interval(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze time gaps between consecutive telemetry reports.

    Calculates per-device intervals and network-wide median sampling step.

    Args:
        df: Chronologically sorted DataFrame with 'timestamp' and 'device_id'

    Returns:
        Dictionary summarizing detected sampling characteristics.
    """
    if len(df) < 2 or "timestamp" not in df.columns:
        return {
            "median_interval_seconds": 1.0,
            "min_interval_seconds": 1.0,
            "max_interval_seconds": 1.0,
            "is_regular": True,
            "note": "Insufficient data to measure interval; defaulted to 1.0s",
        }

    # Calculate intervals per device
    intervals = []
    if "device_id" in df.columns:
        for _, group in df.groupby("device_id"):
            sorted_ts = group["timestamp"].sort_values()
            diffs = sorted_ts.diff().dropna().dt.total_seconds()
            intervals.extend(diffs[diffs > 0].tolist())

    if not intervals:
        # Fallback to global consecutive differences
        diffs = df["timestamp"].diff().dropna().dt.total_seconds()
        intervals = diffs[diffs > 0].tolist()

    if not intervals:
        intervals = [1.0]

    intervals_arr = np.array(intervals, dtype=np.float64)
    med_interval = float(np.median(intervals_arr))
    min_interval = float(np.min(intervals_arr))
    max_interval = float(np.max(intervals_arr))

    # Regularity check: are 90% of intervals within 20% of median?
    near_median = np.abs(intervals_arr - med_interval) <= (0.2 * med_interval)
    is_regular = bool(np.mean(near_median) >= 0.90)

    logger.info(
        "Detected sampling interval: median=%.2fs (min=%.2fs, max=%.2fs, regular=%s)",
        med_interval,
        min_interval,
        max_interval,
        is_regular,
    )

    return {
        "median_interval_seconds": round(med_interval, 2),
        "min_interval_seconds": round(min_interval, 2),
        "max_interval_seconds": round(max_interval, 2),
        "is_regular": is_regular,
    }


def handle_missing_features(
    df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Impute missing numerical telemetry values using a documented strategy.

    Strategy:
    1. If a column has partial missing values, impute using the median of available values.
    2. If a column is 100% NaN (e.g. UDP flows with no RTT, or test run with 0 packet drops),
       impute 0.0 baseline and document clearly.
    3. Preserves original DataFrame.

    Args:
        df: Input DataFrame
        feature_cols: Features to verify and clean

    Returns:
        Tuple of (cleaned_df, missing_stats_dict)
    """
    if feature_cols is None:
        feature_cols = [c for c in CANDIDATE_CONGESTION_FEATURES if c in df.columns]

    cleaned_df = df.copy()
    missing_stats: Dict[str, Any] = {}

    for col in feature_cols:
        if col not in cleaned_df.columns:
            continue

        null_count = int(cleaned_df[col].isnull().sum())
        total_count = len(cleaned_df)

        if null_count > 0:
            median_val = cleaned_df[col].median(skipna=True)
            if pd.isna(median_val):
                # 100% missing across all records
                cleaned_df[col] = cleaned_df[col].fillna(0.0)
                strategy = "100% missing, imputed baseline 0.0"
                logger.warning("Feature '%s' is 100%% NaN. Imputed safe baseline 0.0.", col)
            else:
                cleaned_df[col] = cleaned_df[col].fillna(median_val)
                strategy = f"imputed median {median_val:.4f}"
                logger.debug("Feature '%s': imputed median %.4f for %d nulls", col, median_val, null_count)

            missing_stats[col] = {
                "null_count": null_count,
                "null_percentage": round((null_count / total_count) * 100, 2),
                "strategy": strategy,
            }
        else:
            missing_stats[col] = {
                "null_count": 0,
                "null_percentage": 0.0,
                "strategy": "complete (no nulls)",
            }

    return cleaned_df, missing_stats


# ==============================================================================
# PHASE 10: SEQUENCE DATASET & TENSOR PREPARATION
# ==============================================================================

EXCLUDED_FEATURE_COLS = {
    "sequence_id",
    "device_id",
    "sequence_start",
    "sequence_end",
    "prediction_timestamp",
    "target_timestamp",
    "timestamp",
    "window_start",
    "window_end",
    "history_steps",
    "history_duration_seconds",
    "future_congestion_score",
    "future_congestion_class",
}


def load_phase9_datasets(
    data_dir: Union[str, Path] = DEFAULT_OUTPUT_DIR,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load Phase 9 train, validation, and test datasets.

    Validates file existence, non-emptiness, and chronological ordering.

    Args:
        data_dir: Directory containing train_dataset.csv, validation_dataset.csv,
                  and test_dataset.csv.

    Returns:
        Tuple of (train_df, val_df, test_df)

    Raises:
        FileNotFoundError: If any of the 3 required dataset CSVs is missing.
        ValueError: If any dataset file is empty.
    """
    base_dir = Path(data_dir)
    train_path = base_dir / "train_dataset.csv"
    val_path = base_dir / "validation_dataset.csv"
    test_path = base_dir / "test_dataset.csv"

    for path, name in [
        (train_path, "train_dataset.csv"),
        (val_path, "validation_dataset.csv"),
        (test_path, "test_dataset.csv"),
    ]:
        if not path.exists():
            logger.error("Phase 9 dataset '%s' not found at %s", name, path)
            raise FileNotFoundError(f"Dataset file '{name}' not found at {path}")

    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(test_path)

    for df, name in [(train_df, "train"), (val_df, "validation"), (test_df, "test")]:
        if len(df) == 0:
            logger.error("Dataset '%s' is empty", name)
            raise ValueError(f"Dataset '{name}' is empty")

    logger.info(
        "Successfully loaded Phase 9 datasets: Train=%d, Val=%d, Test=%d samples",
        len(train_df),
        len(val_df),
        len(test_df),
    )
    return train_df, val_df, test_df


def select_input_features(df: pd.DataFrame) -> List[str]:
    """Select input feature column names for the congestion prediction model.

    Strictly excludes target columns (future_congestion_score,
    future_congestion_class), timestamp identifiers, and metadata columns.

    Args:
        df: Input DataFrame containing candidate features and metadata.

    Returns:
        List of selected feature column names in deterministic order.
    """
    selected: List[str] = []

    # Priority 1: Contextual behavioral feature from Phase 8
    if "cluster_id" in df.columns:
        selected.append("cluster_id")

    # Priority 2: Instantaneous candidate features from Phase 7
    for col in CANDIDATE_CONGESTION_FEATURES:
        if col in df.columns and col not in selected and col not in EXCLUDED_FEATURE_COLS:
            selected.append(col)

    # Priority 3: Historical summary aggregate features from Phase 9
    for col in df.columns:
        if col.startswith("hist_mean_") and col not in selected and col not in EXCLUDED_FEATURE_COLS:
            selected.append(col)

    # Priority 4: Any other numeric feature not excluded
    for col in df.columns:
        if col not in selected and col not in EXCLUDED_FEATURE_COLS:
            if pd.api.types.is_numeric_dtype(df[col]):
                selected.append(col)

    logger.debug("Selected %d input features: %s", len(selected), selected)
    return selected


def fit_and_transform_scaler(
    train_df: pd.DataFrame,
    val_df: Optional[pd.DataFrame] = None,
    test_df: Optional[pd.DataFrame] = None,
    feature_cols: Optional[List[str]] = None,
) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], StandardScaler, List[str]]:
    """Fit StandardScaler strictly on training dataset and transform all splits.

    Guarantees no data leakage from validation or test splits.

    Args:
        train_df: Training DataFrame
        val_df: Optional validation DataFrame
        test_df: Optional test DataFrame
        feature_cols: Optional explicit list of feature columns. If None,
                      determined via select_input_features(train_df).

    Returns:
        Tuple of (scaled_train, scaled_val, scaled_test, scaler, feature_cols)
    """
    if feature_cols is None:
        feature_cols = select_input_features(train_df)

    if not feature_cols:
        raise ValueError("No input features selected for scaling.")

    # Fill NaNs with 0.0 for safety
    train_features = train_df[feature_cols].copy().fillna(0.0).to_numpy(dtype=np.float32)

    # CRITICAL: Fit scaler ONLY on training data
    scaler = StandardScaler()
    scaled_train = scaler.fit_transform(train_features)

    scaled_val: Optional[np.ndarray] = None
    if val_df is not None and len(val_df) > 0:
        val_features = val_df[feature_cols].copy().fillna(0.0).to_numpy(dtype=np.float32)
        scaled_val = scaler.transform(val_features)

    scaled_test: Optional[np.ndarray] = None
    if test_df is not None and len(test_df) > 0:
        test_features = test_df[feature_cols].copy().fillna(0.0).to_numpy(dtype=np.float32)
        scaled_test = scaler.transform(test_features)

    logger.info(
        "StandardScaler fitted strictly on %d training samples across %d features.",
        len(train_features),
        len(feature_cols),
    )
    return scaled_train, scaled_val, scaled_test, scaler, feature_cols


def reshape_to_sequences(
    scaled_data: np.ndarray,
    feature_cols: Optional[List[str]] = None,
    timesteps: int = DEFAULT_TIMESTEPS,
) -> np.ndarray:
    """Format scaled features into 3D sequence tensors (samples, timesteps, features).

    If the dataset contains paired historical and current features
    (e.g., cluster_id, base metrics, hist_mean metrics):
      Timestep 0: Historical lookback summary state
      Timestep 1: Current anchor state
      Yielding shape: (samples, 2, num_base_features)

    Otherwise (or if timesteps != 2), repeats features along the temporal axis
    to preserve 3D sequential recurrent input dimensions.

    Args:
        scaled_data: 2D array of shape (samples, num_features) or 3D array
        feature_cols: Optional list of feature column names corresponding to columns
        timesteps: Target sequence length (default: 2)

    Returns:
        3D numpy array of shape (samples, timesteps, features_per_timestep)
    """
    arr = np.asarray(scaled_data, dtype=np.float32)
    if arr.ndim == 3:
        return arr
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)

    n_samples, n_features = arr.shape

    # Structured 2-timestep trajectory representation for Phase 9 datasets
    if timesteps == 2 and feature_cols is not None:
        has_cluster = "cluster_id" in feature_cols
        base_features = [
            c for c in CANDIDATE_CONGESTION_FEATURES
            if c in feature_cols and not c.startswith("hist_mean_")
        ]
        hist_features = [f"hist_mean_{c}" for c in base_features]
        all_hist_present = all(c in feature_cols for c in hist_features)

        if base_features and all_hist_present:
            col_to_idx = {name: idx for idx, name in enumerate(feature_cols)}

            cluster_idx = [col_to_idx["cluster_id"]] if has_cluster else []
            base_idx = cluster_idx + [col_to_idx[c] for c in base_features]
            hist_idx = cluster_idx + [col_to_idx[c] for c in hist_features]

            step_0 = arr[:, hist_idx]  # Historical lookback state
            step_1 = arr[:, base_idx]  # Current anchor state

            sequence_tensor = np.stack([step_0, step_1], axis=1)
            logger.debug(
                "Constructed 2-step trajectory sequence tensor with shape %s",
                sequence_tensor.shape,
            )
            return sequence_tensor

    # Generic sequential repetition along time dimension
    sequence_tensor = np.repeat(arr[:, np.newaxis, :], timesteps, axis=1)
    logger.debug(
        "Formatted generic sequence tensor with shape %s", sequence_tensor.shape
    )
    return sequence_tensor


def prepare_training_tensors(
    data_dir: Union[str, Path] = DEFAULT_OUTPUT_DIR,
    timesteps: int = DEFAULT_TIMESTEPS,
) -> Dict[str, Any]:
    """Load Phase 9 datasets, fit scaler on train only, and build sequence tensors.

    Args:
        data_dir: Directory containing train, validation, and test CSVs.
        timesteps: Recurrent sequence length.

    Returns:
        Dictionary with keys:
          - X_train, y_train_score, y_train_class
          - X_val, y_val_score, y_val_class
          - X_test, y_test_score, y_test_class
          - scaler, feature_cols, input_shape
    """
    train_df, val_df, test_df = load_phase9_datasets(data_dir)
    feature_cols = select_input_features(train_df)

    scaled_train, scaled_val, scaled_test, scaler, feature_cols = fit_and_transform_scaler(
        train_df=train_df,
        val_df=val_df,
        test_df=test_df,
        feature_cols=feature_cols,
    )

    X_train = reshape_to_sequences(scaled_train, feature_cols, timesteps=timesteps)
    X_val = reshape_to_sequences(scaled_val, feature_cols, timesteps=timesteps)
    X_test = reshape_to_sequences(scaled_test, feature_cols, timesteps=timesteps)

    y_train_score = train_df["future_congestion_score"].to_numpy(dtype=np.float32)
    y_train_class = train_df["future_congestion_class"].to_numpy()

    y_val_score = val_df["future_congestion_score"].to_numpy(dtype=np.float32)
    y_val_class = val_df["future_congestion_class"].to_numpy()

    y_test_score = test_df["future_congestion_score"].to_numpy(dtype=np.float32)
    y_test_class = test_df["future_congestion_class"].to_numpy()

    input_shape = (X_train.shape[1], X_train.shape[2])

    logger.info(
        "Prepared training tensors: X_train=%s, X_val=%s, X_test=%s, input_shape=%s",
        X_train.shape,
        X_val.shape,
        X_test.shape,
        input_shape,
    )

    return {
        "X_train": X_train,
        "y_train_score": y_train_score,
        "y_train_class": y_train_class,
        "X_val": X_val,
        "y_val_score": y_val_score,
        "y_val_class": y_val_class,
        "X_test": X_test,
        "y_test_score": y_test_score,
        "y_test_class": y_test_class,
        "train_df": train_df,
        "val_df": val_df,
        "test_df": test_df,
        "scaler": scaler,
        "feature_cols": feature_cols,
        "input_shape": input_shape,
    }
