"""Dataset Validation and Invariant Verification for Phase 9 Congestion Dataset.

Enforces strict verification of:
1. Timestamp monotonicity and validity
2. Numerical feature boundaries and non-negativity
3. Congestion score bounds ([0.0, 1.0]) and class membership (LOW/MEDIUM/HIGH)
4. Future target forward-looking guarantee (target_ts > anchor_ts)
5. Zero data leakage in historical observation sequences
6. Chronological split boundaries (max(train) <= min(val) <= min(test))
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from ml.congestion.config import (
    CANDIDATE_CONGESTION_FEATURES,
    CONGESTION_CLASSES,
    DEFAULT_STATS_PATH,
)

logger = logging.getLogger("ml.congestion.dataset_validation")


def validate_timestamps(
    df: pd.DataFrame,
    time_col: str = "timestamp",
) -> Tuple[bool, List[str]]:
    """Verify that timestamps are valid datetimes and non-decreasing.

    Args:
        df: DataFrame to validate
        time_col: Name of the timestamp column

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    if df.empty:
        return True, issues

    if time_col not in df.columns:
        issues.append(f"Missing timestamp column '{time_col}'")
        return False, issues

    # Parse and check for invalid / NaT dates
    ts = pd.to_datetime(df[time_col], errors="coerce")
    null_ts = ts.isna().sum()
    if null_ts > 0:
        issues.append(f"Found {null_ts} invalid/null timestamps in '{time_col}'")

    # Check chronological ordering
    if not ts.is_monotonic_increasing:
        issues.append(f"Timestamps in '{time_col}' are not monotonically non-decreasing")

    return len(issues) == 0, issues


def validate_features(
    df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
) -> Tuple[bool, List[str]]:
    """Verify that numerical features contain valid non-negative values.

    Args:
        df: DataFrame to validate
        feature_cols: Feature columns to inspect

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    if df.empty:
        return True, issues

    if feature_cols is None:
        feature_cols = [c for c in CANDIDATE_CONGESTION_FEATURES if c in df.columns]

    # Non-negative metrics in networking
    non_negative_cols = [
        "throughput_mbps", "rtt_ms", "packet_loss_percent",
        "active_connections", "total_flow_count", "flow_count",
    ]

    for col in feature_cols:
        if col not in df.columns:
            continue

        series = pd.to_numeric(df[col], errors="coerce")
        null_count = series.isna().sum()
        if null_count > 0:
            logger.debug("Feature '%s' contains %d NaN/null values", col, null_count)

        if col in non_negative_cols:
            neg_count = (series < 0.0).sum()
            if neg_count > 0:
                issues.append(f"Feature '{col}' contains {neg_count} invalid negative values")

    return len(issues) == 0, issues


def validate_targets(
    df: pd.DataFrame,
    score_col: str = "future_congestion_score",
    class_col: str = "future_congestion_class",
    anchor_time_col: str = "timestamp",
    target_time_col: str = "prediction_timestamp",
) -> Tuple[bool, List[str]]:
    """Verify bounds and forward-looking guarantees of future targets.

    Checks:
    - 0.0 <= score <= 1.0
    - class in ['LOW', 'MEDIUM', 'HIGH']
    - target_timestamp > anchor_timestamp (Strict future requirement)

    Args:
        df: DataFrame with future target columns
        score_col: Column containing continuous score
        class_col: Column containing categorical class
        anchor_time_col: Timestamp of observation
        target_time_col: Timestamp of future target

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    if df.empty:
        return True, issues

    # 1. Congestion Score Range Check
    if score_col in df.columns:
        scores = pd.to_numeric(df[score_col], errors="coerce").dropna()
        if (scores < 0.0).any() or (scores > 1.0).any():
            issues.append(f"Target score '{score_col}' contains values outside [0.0, 1.0]")
    else:
        issues.append(f"Missing target score column '{score_col}'")

    # 2. Congestion Class Membership Check
    if class_col in df.columns:
        classes = df[class_col].dropna().unique()
        invalid_classes = [c for c in classes if c not in CONGESTION_CLASSES]
        if invalid_classes:
            issues.append(f"Target class '{class_col}' contains unexpected classes: {invalid_classes}")
    else:
        issues.append(f"Missing target class column '{class_col}'")

    # 3. Future Timestamp Guarantee (Strict inequality: target > anchor)
    anchor_col = anchor_time_col if anchor_time_col in df.columns else "sequence_end"
    target_col = target_time_col if target_time_col in df.columns else "target_timestamp"

    if anchor_col in df.columns and target_col in df.columns:
        t_anchor = pd.to_datetime(df[anchor_col])
        t_target = pd.to_datetime(df[target_col])
        non_future_count = (t_target <= t_anchor).sum()
        if non_future_count > 0:
            issues.append(
                f"Data leakage: Found {non_future_count} records where future target "
                f"timestamp is not strictly later than anchor timestamp ({target_col} <= {anchor_col})"
            )

    return len(issues) == 0, issues


def validate_splits(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    time_col: str = "timestamp",
) -> Tuple[bool, List[str]]:
    """Verify chronological split boundaries: max(train) <= min(val) <= min(test).

    Args:
        train_df: Training set
        val_df: Validation set
        test_df: Test set
        time_col: Timestamp column

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    t_col = time_col if time_col in train_df.columns else "sequence_end"

    if train_df.empty:
        issues.append("Training split is empty")
        return False, issues

    t_train_max = pd.to_datetime(train_df[t_col]).max()

    if not val_df.empty:
        t_val_min = pd.to_datetime(val_df[t_col]).min()
        t_val_max = pd.to_datetime(val_df[t_col]).max()

        if t_train_max > t_val_min:
            issues.append(
                f"Chronological split leak: max(train_ts) ({t_train_max}) > "
                f"min(val_ts) ({t_val_min})"
            )

        if not test_df.empty:
            t_test_min = pd.to_datetime(test_df[t_col]).min()
            if t_val_max > t_test_min:
                issues.append(
                    f"Chronological split leak: max(val_ts) ({t_val_max}) > "
                    f"min(test_ts) ({t_test_min})"
                )
    elif not test_df.empty:
        t_test_min = pd.to_datetime(test_df[t_col]).min()
        if t_train_max > t_test_min:
            issues.append(
                f"Chronological split leak: max(train_ts) ({t_train_max}) > "
                f"min(test_ts) ({t_test_min})"
            )

    return len(issues) == 0, issues


def generate_and_save_statistics(
    ingestion_stats: Dict[str, Any],
    target_stats: Dict[str, Any],
    seq_stats: Dict[str, Any],
    dataset_df: pd.DataFrame,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    missing_stats: Dict[str, Any],
    sampling_stats: Dict[str, Any],
    output_path: Union[str, Path] = DEFAULT_STATS_PATH,
) -> Path:
    """Generate detailed dataset statistics JSON and save to disk.

    Args:
        ingestion_stats: Ingestion summary
        target_stats: Target construction summary
        seq_stats: Sequence generation summary
        dataset_df: Final full dataset
        train_df: Training partition
        val_df: Validation partition
        test_df: Testing partition
        missing_stats: Missing feature statistics
        sampling_stats: Sampling interval statistics
        output_path: Target JSON file path

    Returns:
        Path to written JSON
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Class distribution
    class_dist: Dict[str, int] = {}
    if "future_congestion_class" in dataset_df.columns:
        counts = dataset_df["future_congestion_class"].value_counts().to_dict()
        for c in CONGESTION_CLASSES:
            class_dist[c] = int(counts.get(c, 0))

    feature_cols = [
        c for c in dataset_df.columns
        if c not in [
            "sequence_id", "timestamp", "sequence_start", "sequence_end",
            "prediction_timestamp", "target_timestamp", "device_id",
            "future_congestion_score", "future_congestion_class",
            "current_congestion_score", "current_congestion_class",
            "actual_horizon_seconds", "history_steps", "history_duration_seconds",
        ]
    ]

    stats_payload = {
        "total_records": ingestion_stats.get("total_records", len(dataset_df)),
        "valid_records": ingestion_stats.get("valid_records", len(dataset_df)),
        "removed_records": ingestion_stats.get("removed_records", 0),
        "sequence_count": seq_stats.get("generated_sequences", len(dataset_df)),
        "training_samples": len(train_df),
        "validation_samples": len(val_df),
        "test_samples": len(test_df),
        "feature_count": len(feature_cols),
        "features": feature_cols,
        "missing_value_statistics": missing_stats,
        "class_distribution": class_dist,
        "time_range": {
            "start": ingestion_stats.get("time_start"),
            "end": ingestion_stats.get("time_end"),
        },
        "sampling_interval": sampling_stats,
        "history_window": seq_stats.get("history_window_seconds"),
        "prediction_horizon": target_stats.get("horizon_seconds"),
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats_payload, f, indent=2)

    logger.info("Saved dataset statistics to %s", path)
    return path
