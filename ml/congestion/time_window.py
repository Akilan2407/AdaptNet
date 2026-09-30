"""Time-Series Windowing, Future Target Generation, and Chronological Splitting.

Handles:
- Forward-looking prediction horizon alignment (t -> t + H)
- Backward-looking historical observation window extraction ([t - W, t])
- Sequence generation with strict data leakage prevention (t_hist <= t < t_future)
- Chronological dataset partitioning (Train -> Validation -> Test)
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ml.congestion.config import (
    CANDIDATE_CONGESTION_FEATURES,
    HISTORY_WINDOW_SECONDS,
    HORIZON_TOLERANCE_SECONDS,
    MIN_HISTORY_STEPS,
    PREDICTION_HORIZON_SECONDS,
    TEST_RATIO,
    TRAIN_RATIO,
    VALIDATION_RATIO,
)
from ml.congestion.congestion_labeling import (
    assign_congestion_class,
    calculate_congestion_score,
)

logger = logging.getLogger("ml.congestion.time_window")


def construct_future_targets(
    df: pd.DataFrame,
    horizon_seconds: int = PREDICTION_HORIZON_SECONDS,
    tolerance_seconds: int = HORIZON_TOLERANCE_SECONDS,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Construct future prediction targets for each telemetry record without data leakage.

    For each record at timestamp t_i, searches for a future observation at or near
    t_target = t_i + horizon_seconds (within [t_target - tol, t_target + tol]).
    Assigns future_congestion_score and future_congestion_class.

    Args:
        df: Chronologically sorted DataFrame with 'timestamp' and flow metrics
        horizon_seconds: Prediction horizon in seconds (default 10)
        tolerance_seconds: Search tolerance window around target time

    Returns:
        Tuple of (df_with_future_targets, target_construction_stats)
    """
    if df.empty or "timestamp" not in df.columns:
        logger.warning("Empty DataFrame provided to construct_future_targets.")
        return pd.DataFrame(), {"matched_targets": 0, "unmatched_targets": 0, "horizon_seconds": horizon_seconds}

    # 1. Compute instantaneous congestion score for each observation
    work_df = df.copy()
    work_df["current_congestion_score"] = calculate_congestion_score(work_df)
    work_df["current_congestion_class"] = assign_congestion_class(work_df["current_congestion_score"])

    # Ensure timestamp is datetime
    work_df["timestamp"] = pd.to_datetime(work_df["timestamp"])
    work_df = work_df.sort_values(by="timestamp").reset_index(drop=True)

    has_device = "device_id" in work_df.columns
    total_records = len(work_df)
    matched_count = 0
    unmatched_count = 0

    # Group by device if device_id is present, otherwise evaluate globally
    groups = work_df.groupby("device_id") if has_device else [("global", work_df)]

    # We will populate arrays indexed by row index in work_df
    score_arr = np.full(total_records, np.nan, dtype=np.float64)
    class_arr = np.empty(total_records, dtype=object)
    target_ts_arr = [None] * total_records
    delta_arr = np.full(total_records, np.nan, dtype=np.float64)

    for dev_id, group in groups:
        indices = group.index.to_numpy()
        ts_series = group["timestamp"].to_numpy()
        scores = group["current_congestion_score"].to_numpy()
        classes = group["current_congestion_class"].to_numpy()
        n_grp = len(indices)

        for i in range(n_grp):
            row_idx = indices[i]
            t_curr = ts_series[i]
            ideal_target_ts = t_curr + np.timedelta64(horizon_seconds, "s")
            min_target_ts = ideal_target_ts - np.timedelta64(tolerance_seconds, "s")
            max_target_ts = ideal_target_ts + np.timedelta64(tolerance_seconds, "s")

            # Look strictly ahead in time (j > i) to prevent leakage
            future_mask = (ts_series > t_curr) & (ts_series >= min_target_ts) & (ts_series <= max_target_ts)
            future_indices = np.where(future_mask)[0]

            if len(future_indices) > 0:
                # Pick the future observation closest to ideal_target_ts
                time_diffs = np.abs(ts_series[future_indices] - ideal_target_ts)
                best_match_idx = future_indices[np.argmin(time_diffs)]

                score_arr[row_idx] = scores[best_match_idx]
                class_arr[row_idx] = classes[best_match_idx]
                target_ts_arr[row_idx] = pd.Timestamp(ts_series[best_match_idx])
                delta_sec = float((ts_series[best_match_idx] - t_curr) / np.timedelta64(1, "s"))
                delta_arr[row_idx] = delta_sec
                matched_count += 1
            else:
                unmatched_count += 1

    work_df["future_congestion_score"] = score_arr
    work_df["future_congestion_class"] = class_arr
    work_df["target_timestamp"] = target_ts_arr
    work_df["actual_horizon_seconds"] = delta_arr

    # Filter only rows that have valid future targets
    valid_targets_df = work_df.dropna(subset=["future_congestion_score"]).copy().reset_index(drop=True)

    stats = {
        "horizon_seconds": horizon_seconds,
        "tolerance_seconds": tolerance_seconds,
        "total_inputs": total_records,
        "matched_targets": matched_count,
        "unmatched_targets": unmatched_count,
        "mean_actual_horizon_seconds": float(np.nanmean(delta_arr)) if matched_count > 0 else 0.0,
    }

    logger.info(
        "Target construction (horizon=%ds): matched %d/%d records (discarded %d trailing/isolated records)",
        horizon_seconds,
        matched_count,
        total_records,
        unmatched_count,
    )
    return valid_targets_df, stats


def generate_time_series_sequences(
    df: pd.DataFrame,
    history_window_seconds: int = HISTORY_WINDOW_SECONDS,
    min_history_steps: int = MIN_HISTORY_STEPS,
    feature_cols: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Generate time-series sequences of historical observations paired with future targets.

    For each record with a future target at anchor t_anchor:
    Extracts all observations within [t_anchor - history_window_seconds, t_anchor].
    Strictly verifies that no observation timestamp exceeds t_anchor.

    Args:
        df: DataFrame containing valid future targets and network features
        history_window_seconds: Historical lookback duration in seconds (default 30)
        min_history_steps: Minimum required observations in lookback window
        feature_cols: Numerical features to track

    Returns:
        Tuple of (sequences_df, sequence_generation_stats)
    """
    if df.empty or "target_timestamp" not in df.columns:
        logger.warning("No valid future targets in DataFrame. Cannot generate sequences.")
        return pd.DataFrame(), {"generated_sequences": 0, "discarded_sequences": 0}

    if feature_cols is None:
        feature_cols = [c for c in CANDIDATE_CONGESTION_FEATURES if c in df.columns]

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(by="timestamp").reset_index(drop=True)

    sequences: List[Dict[str, Any]] = []
    discarded_count = 0
    seq_counter = 0

    has_device = "device_id" in df.columns
    groups = df.groupby("device_id") if has_device else [("global", df)]

    for dev_id, group in groups:
        sorted_grp = group.sort_values(by="timestamp").reset_index(drop=True)
        n_rows = len(sorted_grp)

        for i in range(n_rows):
            anchor_row = sorted_grp.iloc[i]
            t_anchor = anchor_row["timestamp"]
            window_start = t_anchor - pd.Timedelta(seconds=history_window_seconds)

            # Lookback filter: observations in [window_start, t_anchor]
            hist_mask = (sorted_grp["timestamp"] >= window_start) & (sorted_grp["timestamp"] <= t_anchor)
            hist_obs = sorted_grp[hist_mask]

            if len(hist_obs) < min_history_steps:
                discarded_count += 1
                continue

            # Ensure strict data leakage check: all hist_obs timestamps must be <= t_anchor
            # and target_timestamp must be strictly > t_anchor
            t_target = anchor_row["target_timestamp"]
            if not (hist_obs["timestamp"].max() <= t_anchor < t_target):
                logger.error("Data leakage detected at sequence %d: %s <= %s < %s violated!", seq_counter, hist_obs["timestamp"].max(), t_anchor, t_target)
                discarded_count += 1
                continue

            seq_row: Dict[str, Any] = {
                "sequence_id": seq_counter,
                "device_id": str(dev_id),
                "sequence_start": hist_obs["timestamp"].min(),
                "sequence_end": t_anchor,
                "prediction_timestamp": t_target,
                "history_steps": len(hist_obs),
                "history_duration_seconds": float((t_anchor - hist_obs["timestamp"].min()).total_seconds()),
                "future_congestion_score": round(float(anchor_row["future_congestion_score"]), 4),
                "future_congestion_class": str(anchor_row["future_congestion_class"]),
            }

            # Include behavioral cluster_id if available
            if "cluster_id" in anchor_row and pd.notna(anchor_row["cluster_id"]):
                seq_row["cluster_id"] = int(anchor_row["cluster_id"])
            else:
                seq_row["cluster_id"] = np.nan

            # Include latest and mean historical values for key features
            for feat in feature_cols:
                if feat in hist_obs.columns:
                    seq_row[feat] = round(float(anchor_row[feat]), 4)
                    seq_row[f"hist_mean_{feat}"] = round(float(hist_obs[feat].mean()), 4)

            sequences.append(seq_row)
            seq_counter += 1

    seq_df = pd.DataFrame(sequences)
    if not seq_df.empty:
        # Sort sequences strictly chronologically by sequence_end
        seq_df = seq_df.sort_values(by=["sequence_end", "device_id"]).reset_index(drop=True)
        seq_df["sequence_id"] = np.arange(len(seq_df))

    stats = {
        "history_window_seconds": history_window_seconds,
        "min_history_steps": min_history_steps,
        "generated_sequences": len(seq_df),
        "discarded_sequences": discarded_count,
    }

    logger.info("Generated %d sequences (%d discarded for insufficient history)", len(seq_df), discarded_count)
    return seq_df, stats


def chronological_split(
    df: pd.DataFrame,
    train_ratio: float = TRAIN_RATIO,
    val_ratio: float = VALIDATION_RATIO,
    test_ratio: float = TEST_RATIO,
    time_col: str = "timestamp",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split dataset chronologically without random shuffling.

    Enforces temporal order:
    Train (earlier) -> Validation (middle) -> Test (latest).

    Args:
        df: Input DataFrame
        train_ratio: Proportion of earlier data for training (default 0.70)
        val_ratio: Proportion for validation (default 0.15)
        test_ratio: Proportion for testing (default 0.15)
        time_col: Column to use for temporal ordering

    Returns:
        Tuple of (train_df, val_df, test_df)
    """
    n_samples = len(df)
    if n_samples == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Determine sort key column
    sort_col = time_col if time_col in df.columns else ("sequence_end" if "sequence_end" in df.columns else df.columns[0])
    sorted_df = df.sort_values(by=sort_col).reset_index(drop=True)

    if n_samples < 3:
        # Edge case: Very small sample size
        logger.warning("Sample size (%d) too small for 3-way split. Allocating all to training.", n_samples)
        return sorted_df, pd.DataFrame(columns=sorted_df.columns), pd.DataFrame(columns=sorted_df.columns)

    # Calculate integer boundaries
    n_train = int(np.floor(n_samples * train_ratio))
    n_val = int(np.floor(n_samples * val_ratio))
    
    # Ensure train has at least 1 sample and val has at least 1 if n >= 3
    if n_train < 1:
        n_train = 1
    if n_val < 1 and n_samples >= 3:
        n_val = 1
    
    # Test gets the remainder
    n_test = n_samples - n_train - n_val
    if n_test < 1 and n_samples >= 3:
        # Adjust from train if possible
        if n_train > 1:
            n_train -= 1
            n_test = 1
        elif n_val > 1:
            n_val -= 1
            n_test = 1

    train_df = sorted_df.iloc[:n_train].copy().reset_index(drop=True)
    val_df = sorted_df.iloc[n_train : n_train + n_val].copy().reset_index(drop=True)
    test_df = sorted_df.iloc[n_train + n_val :].copy().reset_index(drop=True)

    logger.info(
        "Chronological split: Train=%d (%.1f%%), Val=%d (%.1f%%), Test=%d (%.1f%%)",
        len(train_df),
        (len(train_df) / n_samples) * 100,
        len(val_df),
        (len(val_df) / n_samples) * 100,
        len(test_df),
        (len(test_df) / n_samples) * 100,
    )

    return train_df, val_df, test_df
