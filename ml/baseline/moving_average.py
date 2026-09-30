"""Moving Average Congestion Prediction Baseline.

Predicts future congestion score using the arithmetic mean of the most recent
N valid historical observations:
    C_pred(t + H) = (1 / k) * sum_{j=1..k} C(t - j + 1)
"""

import logging
from typing import Any, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from ml.baseline.config import MOVING_AVERAGE_WINDOW

logger = logging.getLogger("ml.baseline.moving_average")


def predict_moving_average(
    history: Union[Sequence[float], np.ndarray, pd.Series],
    window_size: int = MOVING_AVERAGE_WINDOW,
    min_points: int = 1,
    default_value: float = 0.0,
) -> float:
    """Predict future congestion using the moving average of recent observations.

    Args:
        history: Sequence of historical congestion scores in chronological order.
        window_size: Maximum number of recent observations to include in the average.
        min_points: Minimum number of valid observations required.
        default_value: Value returned when valid history is below min_points.

    Returns:
        Predicted future congestion score bounded in [0.0, 1.0].
    """
    if window_size <= 0:
        raise ValueError(f"window_size must be positive, got {window_size}")

    if history is None:
        logger.warning("History is None; returning default value %.4f", default_value)
        return float(np.clip(default_value, 0.0, 1.0))

    if isinstance(history, pd.Series):
        arr = history.to_numpy(dtype=np.float64)
    else:
        try:
            arr = np.asarray(history, dtype=np.float64).flatten()
        except (ValueError, TypeError):
            logger.warning("Could not cast history to float array; returning default %.4f", default_value)
            return float(np.clip(default_value, 0.0, 1.0))

    # Filter out NaNs and infinities
    valid_mask = ~np.isnan(arr) & ~np.isinf(arr)
    valid_history = arr[valid_mask]

    if len(valid_history) < min_points:
        logger.warning(
            "Insufficient history: found %d valid observations (< %d required); returning default %.4f",
            len(valid_history),
            min_points,
            default_value,
        )
        return float(np.clip(default_value, 0.0, 1.0))

    # Take the most recent window_size observations
    window_obs = valid_history[-window_size:]
    mean_score = float(np.mean(window_obs))
    prediction = float(np.clip(mean_score, 0.0, 1.0))

    logger.debug(
        "Moving average prediction (window=%d, points=%d): mean=%.4f -> pred=%.4f",
        window_size,
        len(window_obs),
        mean_score,
        prediction,
    )
    return prediction
