"""Common Object-Oriented Interface for Congestion Baselines.

Provides:
- BaseBaseline: Abstract base class with unified classification and validation
- PersistenceBaseline: Predicts latest observation
- MovingAverageBaseline: Predicts mean over rolling window
- LinearTrendBaseline: Extrapolates linear trend
"""

import abc
import logging
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from ml.baseline.config import (
    CONGESTION_CLASSES,
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
    MOVING_AVERAGE_WINDOW,
)
from ml.baseline.linear_trend import predict_linear_trend
from ml.baseline.moving_average import predict_moving_average
from ml.baseline.persistence import predict_persistence

logger = logging.getLogger("ml.baseline.baseline_predictor")


def score_to_class(
    score: float,
    low_thresh: float = LOW_THRESHOLD,
    high_thresh: float = HIGH_THRESHOLD,
) -> str:
    """Map continuous congestion score in [0.0, 1.0] to categorical class."""
    if np.isnan(score):
        return "UNKNOWN"
    if score < low_thresh:
        return "LOW"
    elif score <= high_thresh:
        return "MEDIUM"
    else:
        return "HIGH"


class BaseBaseline(abc.ABC):
    """Abstract base class for congestion prediction baselines."""

    def __init__(
        self,
        name: str,
        low_threshold: float = LOW_THRESHOLD,
        high_threshold: float = HIGH_THRESHOLD,
    ) -> None:
        self.name = name
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold

    def classify_score(self, score: float) -> str:
        """Assign categorical congestion class based on score."""
        return score_to_class(score, self.low_threshold, self.high_threshold)

    @abc.abstractmethod
    def predict(
        self,
        history: Union[Sequence[float], np.ndarray, pd.Series],
        timestamps: Optional[Union[Sequence[Any], np.ndarray, pd.Series]] = None,
        future_timestamp: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Generate prediction for a given history.

        Returns:
            Dictionary with predicted_congestion_score, predicted_congestion_class,
            model_name, and metadata.
        """
        pass


class PersistenceBaseline(BaseBaseline):
    """Persistence baseline: predicts latest valid historical observation."""

    def __init__(
        self,
        name: str = "Persistence",
        low_threshold: float = LOW_THRESHOLD,
        high_threshold: float = HIGH_THRESHOLD,
    ) -> None:
        super().__init__(name=name, low_threshold=low_threshold, high_threshold=high_threshold)

    def predict(
        self,
        history: Union[Sequence[float], np.ndarray, pd.Series],
        timestamps: Optional[Union[Sequence[Any], np.ndarray, pd.Series]] = None,
        future_timestamp: Optional[Any] = None,
    ) -> Dict[str, Any]:
        score = predict_persistence(history=history)
        cls_name = self.classify_score(score)
        valid_len = len(np.asarray(history)[~np.isnan(np.asarray(history))]) if history is not None else 0

        return {
            "model_name": self.name,
            "predicted_congestion_score": score,
            "predicted_congestion_class": cls_name,
            "history_points_used": min(1, valid_len),
            "status": "SUCCESS" if valid_len > 0 else "INSUFFICIENT_HISTORY",
        }


class MovingAverageBaseline(BaseBaseline):
    """Moving average baseline: predicts mean of recent window observations."""

    def __init__(
        self,
        name: str = "MovingAverage",
        window_size: int = MOVING_AVERAGE_WINDOW,
        low_threshold: float = LOW_THRESHOLD,
        high_threshold: float = HIGH_THRESHOLD,
    ) -> None:
        super().__init__(name=name, low_threshold=low_threshold, high_threshold=high_threshold)
        self.window_size = window_size

    def predict(
        self,
        history: Union[Sequence[float], np.ndarray, pd.Series],
        timestamps: Optional[Union[Sequence[Any], np.ndarray, pd.Series]] = None,
        future_timestamp: Optional[Any] = None,
    ) -> Dict[str, Any]:
        score = predict_moving_average(history=history, window_size=self.window_size)
        cls_name = self.classify_score(score)
        valid_len = len(np.asarray(history)[~np.isnan(np.asarray(history))]) if history is not None else 0

        return {
            "model_name": self.name,
            "predicted_congestion_score": score,
            "predicted_congestion_class": cls_name,
            "window_size": self.window_size,
            "history_points_used": min(self.window_size, valid_len),
            "status": "SUCCESS" if valid_len > 0 else "INSUFFICIENT_HISTORY",
        }


class LinearTrendBaseline(BaseBaseline):
    """Linear trend baseline: extrapolates OLS regression to future timestamp."""

    def __init__(
        self,
        name: str = "LinearTrend",
        low_threshold: float = LOW_THRESHOLD,
        high_threshold: float = HIGH_THRESHOLD,
    ) -> None:
        super().__init__(name=name, low_threshold=low_threshold, high_threshold=high_threshold)

    def predict(
        self,
        history: Union[Sequence[float], np.ndarray, pd.Series],
        timestamps: Optional[Union[Sequence[Any], np.ndarray, pd.Series]] = None,
        future_timestamp: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if timestamps is None or future_timestamp is None:
            # Fallback to persistence if timestamps are not supplied
            score = predict_persistence(history=history)
            cls_name = self.classify_score(score)
            status = "FALLBACK_NO_TIMESTAMPS"
            valid_len = len(np.asarray(history)[~np.isnan(np.asarray(history))]) if history is not None else 0
        else:
            score = predict_linear_trend(
                history=history,
                timestamps=timestamps,
                future_timestamp=future_timestamp,
            )
            cls_name = self.classify_score(score)
            valid_len = len(np.asarray(history)[~np.isnan(np.asarray(history))]) if history is not None else 0
            status = "SUCCESS" if valid_len >= 2 else "SINGLE_POINT_FALLBACK"

        return {
            "model_name": self.name,
            "predicted_congestion_score": score,
            "predicted_congestion_class": cls_name,
            "history_points_used": valid_len,
            "status": status,
        }
