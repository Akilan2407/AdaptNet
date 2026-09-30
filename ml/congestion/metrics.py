"""Evaluation Metrics and Baseline Benchmarks for Congestion Forecasting.

Calculates:
- Primary continuous regression metrics: MAE, MSE, RMSE, R²
- Secondary discrete classification metrics: Accuracy, Precision, Recall, F1, Confusion Matrix
- Naive persistence and mean baseline benchmarks
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)

from ml.congestion.config import (
    CONGESTION_CLASSES,
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
)
from ml.congestion.congestion_labeling import calculate_congestion_score

logger = logging.getLogger("ml.congestion.metrics")


def score_to_class(
    score: Union[float, np.ndarray, pd.Series],
    low_thresh: float = LOW_THRESHOLD,
    high_thresh: float = HIGH_THRESHOLD,
) -> Union[str, np.ndarray]:
    """Map continuous congestion score in [0.0, 1.0] to categorical class.

    Mapping:
      - score < low_thresh: LOW
      - low_thresh <= score <= high_thresh: MEDIUM
      - score > high_thresh: HIGH

    Args:
        score: Single float or array-like of scores.
        low_thresh: Cutoff between LOW and MEDIUM.
        high_thresh: Cutoff between MEDIUM and HIGH.

    Returns:
        String class or numpy array of class strings.
    """
    if isinstance(score, (int, float, np.floating)):
        if score < low_thresh:
            return "LOW"
        elif score <= high_thresh:
            return "MEDIUM"
        else:
            return "HIGH"

    arr = np.asarray(score, dtype=np.float32)
    classes = np.empty(arr.shape, dtype=object)
    classes[arr < low_thresh] = "LOW"
    classes[(arr >= low_thresh) & (arr <= high_thresh)] = "MEDIUM"
    classes[arr > high_thresh] = "HIGH"
    return classes


def calculate_regression_metrics(
    y_true: Union[np.ndarray, List[float]],
    y_pred: Union[np.ndarray, List[float]],
) -> Dict[str, float]:
    """Calculate continuous regression performance metrics.

    Args:
        y_true: Ground truth target scores.
        y_pred: Predicted target scores.

    Returns:
        Dictionary containing MAE, MSE, RMSE, R2, and Max Error.
    """
    y_t = np.asarray(y_true, dtype=np.float64).flatten()
    y_p = np.asarray(y_pred, dtype=np.float64).flatten()

    if len(y_t) == 0:
        return {"mae": 0.0, "mse": 0.0, "rmse": 0.0, "r2": 0.0, "max_error": 0.0}

    mae = float(mean_absolute_error(y_t, y_p))
    mse = float(mean_squared_error(y_t, y_p))
    rmse = float(np.sqrt(mse))
    max_err = float(np.max(np.abs(y_t - y_p)))

    # Handle single-sample or zero-variance edge cases for R2
    if len(y_t) > 1 and np.var(y_t) > 1e-9:
        r2 = float(r2_score(y_t, y_p))
    else:
        r2 = 0.0

    return {
        "mae": round(mae, 4),
        "mse": round(mse, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "max_error": round(max_err, 4),
    }


def calculate_classification_metrics(
    y_true: Union[np.ndarray, List[str]],
    y_pred: Union[np.ndarray, List[str]],
    classes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Calculate discrete classification metrics for congestion levels.

    Args:
        y_true: Ground truth class labels (LOW, MEDIUM, HIGH).
        y_pred: Predicted class labels.
        classes: Ordered class names.

    Returns:
        Dictionary containing Accuracy, Precision, Recall, F1, and Confusion Matrix.
    """
    if classes is None:
        classes = CONGESTION_CLASSES

    y_t = np.asarray(y_true, dtype=str).flatten()
    y_p = np.asarray(y_pred, dtype=str).flatten()

    if len(y_t) == 0:
        return {
            "accuracy": 0.0,
            "precision_macro": 0.0,
            "recall_macro": 0.0,
            "f1_macro": 0.0,
            "confusion_matrix": [[0 for _ in classes] for _ in classes],
            "classes": classes,
        }

    acc = float(accuracy_score(y_t, y_p))
    prec = float(precision_score(y_t, y_p, labels=classes, average="macro", zero_division=0))
    rec = float(recall_score(y_t, y_p, labels=classes, average="macro", zero_division=0))
    f1 = float(f1_score(y_t, y_p, labels=classes, average="macro", zero_division=0))

    cm = confusion_matrix(y_t, y_p, labels=classes)

    return {
        "accuracy": round(acc, 4),
        "precision_macro": round(prec, 4),
        "recall_macro": round(rec, 4),
        "f1_macro": round(f1, 4),
        "confusion_matrix": cm.tolist(),
        "classes": classes,
    }


def evaluate_naive_baseline(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> Dict[str, Any]:
    """Evaluate naive baseline forecasting heuristics on the test set.

    Benchmarks:
    1. Persistence Baseline: Predicts current anchor congestion score as the future score.
    2. Historical Mean Baseline: Predicts training set mean congestion score as the future score.

    Args:
        train_df: Training DataFrame with future_congestion_score.
        test_df: Test DataFrame with ground truth future_congestion_score and current metrics.

    Returns:
        Dictionary summarizing baseline performances.
    """
    y_test_true = test_df["future_congestion_score"].to_numpy(dtype=np.float32)
    y_test_class_true = test_df["future_congestion_class"].to_numpy(dtype=str)

    # 1. Persistence Baseline (Current telemetry score)
    try:
        y_persistence_score = calculate_congestion_score(test_df).to_numpy(dtype=np.float32)
    except Exception:
        # Fallback to historical mean throughput/loss if columns differ
        y_persistence_score = np.zeros_like(y_test_true)

    y_persistence_class = score_to_class(y_persistence_score)
    persistence_reg = calculate_regression_metrics(y_test_true, y_persistence_score)
    persistence_cls = calculate_classification_metrics(y_test_class_true, y_persistence_class)

    # 2. Historical Mean Baseline
    train_mean = float(train_df["future_congestion_score"].mean())
    y_mean_score = np.full_like(y_test_true, fill_value=train_mean)
    y_mean_class = score_to_class(y_mean_score)
    mean_reg = calculate_regression_metrics(y_test_true, y_mean_score)
    mean_cls = calculate_classification_metrics(y_test_class_true, y_mean_class)

    logger.info(
        "Baseline evaluation: Persistence MAE=%.4f, Mean MAE=%.4f",
        persistence_reg["mae"],
        mean_reg["mae"],
    )

    return {
        "persistence_baseline": {
            "regression": persistence_reg,
            "classification": persistence_cls,
            "description": "Predicts current anchor congestion score as future score.",
        },
        "mean_baseline": {
            "train_mean_score": round(train_mean, 4),
            "regression": mean_reg,
            "classification": mean_cls,
            "description": "Predicts historical training mean score as future score.",
        },
    }
