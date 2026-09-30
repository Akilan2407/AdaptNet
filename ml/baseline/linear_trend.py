"""Linear Trend Congestion Prediction Baseline.

Fits a simple ordinary least squares linear regression over recent historical
observations and extrapolates to the future prediction timestamp:
    C(t) = a * t + b
    C_pred(t_future) = a * t_future + b
"""

import logging
from datetime import datetime
from typing import Any, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("ml.baseline.linear_trend")


def _to_timestamp_seconds(ts: Union[datetime, pd.Timestamp, str, int, float]) -> float:
    """Convert arbitrary timestamp representation to float seconds."""
    if isinstance(ts, (int, float, np.floating, np.integer)):
        return float(ts)
    if isinstance(ts, str):
        parsed = pd.to_datetime(ts)
        return float(parsed.timestamp())
    if isinstance(ts, (datetime, pd.Timestamp)):
        return float(ts.timestamp())
    raise TypeError(f"Unsupported timestamp type: {type(ts)}")


def predict_linear_trend(
    history: Union[Sequence[float], np.ndarray, pd.Series],
    timestamps: Union[Sequence[Any], np.ndarray, pd.Series],
    future_timestamp: Union[datetime, pd.Timestamp, str, int, float],
    default_value: float = 0.0,
) -> float:
    """Predict future congestion by extrapolating a linear trend over historical observations.

    Args:
        history: Sequence of historical congestion scores in chronological order.
        timestamps: Sequence of timestamps corresponding to each observation.
        future_timestamp: Target timestamp at which to predict future congestion.
        default_value: Fallback score when history is empty or invalid.

    Returns:
        Predicted future congestion score bounded in [0.0, 1.0].

    Raises:
        ValueError: If length of history does not match timestamps, or if temporal
                    leakage is detected (historical timestamp >= future_timestamp).
    """
    if history is None or timestamps is None or future_timestamp is None:
        logger.warning("Input is None; returning default value %.4f", default_value)
        return float(np.clip(default_value, 0.0, 1.0))

    t_future_sec = _to_timestamp_seconds(future_timestamp)

    # Convert to 1D arrays
    h_arr = np.asarray(history, dtype=np.float64).flatten()
    if len(h_arr) == 0:
        logger.warning("Empty history provided; returning default %.4f", default_value)
        return float(np.clip(default_value, 0.0, 1.0))

    raw_ts = list(timestamps)
    if len(h_arr) != len(raw_ts):
        raise ValueError(
            f"Length mismatch: history has {len(h_arr)} elements but timestamps has {len(raw_ts)}"
        )

    t_arr = np.array([_to_timestamp_seconds(t) for t in raw_ts], dtype=np.float64)

    # Filter out NaNs and infinities
    valid_mask = ~np.isnan(h_arr) & ~np.isinf(h_arr) & ~np.isnan(t_arr) & ~np.isinf(t_arr)
    valid_h = h_arr[valid_mask]
    valid_t = t_arr[valid_mask]

    if len(valid_h) == 0:
        logger.warning("No valid observations found; returning default %.4f", default_value)
        return float(np.clip(default_value, 0.0, 1.0))

    # CRITICAL TEMPORAL LEAKAGE CHECK
    latest_input_time = float(np.max(valid_t))
    if latest_input_time >= t_future_sec:
        raise ValueError(
            f"Temporal leakage detected: latest historical observation timestamp "
            f"({latest_input_time}) is >= future prediction timestamp ({t_future_sec})"
        )

    # Single-point fallback: cannot compute slope, return single observation
    if len(valid_h) == 1:
        single_val = float(np.clip(valid_h[0], 0.0, 1.0))
        logger.debug("Only 1 observation available for trend; falling back to persistence=%.4f", single_val)
        return single_val

    # Normalize time relative to first observation to prevent large numeric overflows
    t0 = valid_t[0]
    t_rel = valid_t - t0
    t_future_rel = t_future_sec - t0

    t_mean = float(np.mean(t_rel))
    h_mean = float(np.mean(valid_h))

    denom = float(np.sum((t_rel - t_mean) ** 2))

    # Constant timestamps or zero variance: return mean
    if denom < 1e-12:
        logger.debug("Timestamps have zero variance; returning mean=%.4f", h_mean)
        return float(np.clip(h_mean, 0.0, 1.0))

    numer = float(np.sum((t_rel - t_mean) * (valid_h - h_mean)))
    slope = numer / denom
    intercept = h_mean - (slope * t_mean)

    # Extrapolate
    extrapolated = (slope * t_future_rel) + intercept
    prediction = float(np.clip(extrapolated, 0.0, 1.0))

    logger.debug(
        "Linear trend prediction: slope=%.6f, intercept=%.4f, raw=%.4f -> pred=%.4f",
        slope,
        intercept,
        extrapolated,
        prediction,
    )
    return prediction
