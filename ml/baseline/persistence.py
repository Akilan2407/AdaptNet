"""Persistence (Naive) Congestion Prediction Baseline.

Predicts future congestion score using the most recent valid observed congestion value:
    C_pred(t + H) = C(t)
"""

import logging
from typing import Any, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("ml.baseline.persistence")


def predict_persistence(
    history: Union[Sequence[float], np.ndarray, pd.Series],
    default_value: float = 0.0,
) -> float:
    """Predict future congestion using the most recent observed value.

    Args:
        history: Sequence of historical congestion scores in chronological order.
        default_value: Value returned when history is empty or contains only NaNs.

    Returns:
        Predicted future congestion score bounded in [0.0, 1.0].
    """
    if history is None:
        logger.warning("History is None; returning default value %.4f", default_value)
        return float(np.clip(default_value, 0.0, 1.0))

    # Convert to 1D numpy array
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

    if len(valid_history) == 0:
        logger.warning("No valid observations found in history; returning default %.4f", default_value)
        return float(np.clip(default_value, 0.0, 1.0))

    # Take the latest observation
    latest_val = valid_history[-1]
    prediction = float(np.clip(latest_val, 0.0, 1.0))

    logger.debug("Persistence prediction: latest=%.4f -> pred=%.4f", latest_val, prediction)
    return prediction
