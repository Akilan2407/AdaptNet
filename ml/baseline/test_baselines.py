"""Unit Test Suite for Phase 11: Congestion Baseline Module.

Tests 15 critical requirements:
1. Persistence prediction logic
2. Moving average prediction logic
3. Linear trend extrapolation logic
4. Output range bounded in [0.0, 1.0]
5. Empty history handling
6. NaN and invalid value handling
7. Insufficient history handling
8. Constant value handling
9. Increasing congestion trend extrapolation
10. Decreasing congestion trend extrapolation
11. Future timestamp temporal validation
12. Metric calculation correctness
13. Classification threshold conversion
14. Temporal data leakage prevention
15. Model comparison file generation
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.baseline.baseline_predictor import (
    LinearTrendBaseline,
    MovingAverageBaseline,
    PersistenceBaseline,
    score_to_class,
)
from ml.baseline.comparison import (
    build_comparison_dataframe,
    compute_metric_comparisons,
    export_model_comparison_csv,
)
from ml.baseline.config import (
    CONGESTION_CLASSES,
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
    MOVING_AVERAGE_WINDOW,
)
from ml.baseline.evaluate_baselines import (
    calculate_classification_metrics,
    calculate_regression_metrics,
    extract_history_for_sample,
)
from ml.baseline.linear_trend import predict_linear_trend
from ml.baseline.moving_average import predict_moving_average
from ml.baseline.persistence import predict_persistence


# 1. Persistence prediction
def test_persistence_prediction():
    """Verify persistence returns the latest valid observation."""
    history = [0.10, 0.25, 0.45, 0.62]
    pred = predict_persistence(history)
    assert abs(pred - 0.62) < 1e-5


# 2. Moving average prediction
def test_moving_average_prediction():
    """Verify moving average calculates the mean over the window."""
    history = [0.10, 0.20, 0.30, 0.40, 0.50]
    pred = predict_moving_average(history, window_size=3)
    # mean of [0.30, 0.40, 0.50] = 0.40
    assert abs(pred - 0.40) < 1e-5


# 3. Linear trend prediction
def test_linear_trend_prediction():
    """Verify linear trend extrapolates along the fitted slope."""
    t0 = datetime(2026, 9, 12, 16, 0, 0)
    timestamps = [t0, t0 + timedelta(seconds=10), t0 + timedelta(seconds=20)]
    history = [0.10, 0.20, 0.30]  # slope = 0.01 per second
    t_future = t0 + timedelta(seconds=30)

    pred = predict_linear_trend(history, timestamps, t_future)
    assert abs(pred - 0.40) < 1e-5


# 4. Output range bounded in [0, 1]
def test_output_range_bounded():
    """Verify all predictors clip output strictly to [0.0, 1.0]."""
    # Persistence clipping
    assert predict_persistence([1.5]) == 1.0
    assert predict_persistence([-0.5]) == 0.0

    # Moving average clipping
    assert predict_moving_average([1.2, 1.4]) == 1.0
    assert predict_moving_average([-0.2, -0.4]) == 0.0

    # Linear trend extrapolation clipping beyond bounds
    t0 = datetime(2026, 9, 12, 16, 0, 0)
    timestamps = [t0, t0 + timedelta(seconds=10)]
    t_future = t0 + timedelta(seconds=50)

    # Steep upward slope clipping to 1.0
    pred_up = predict_linear_trend([0.8, 0.95], timestamps, t_future)
    assert pred_up == 1.0

    # Steep downward slope clipping to 0.0
    pred_down = predict_linear_trend([0.5, 0.1], timestamps, t_future)
    assert pred_down == 0.0


# 5. Empty history handling
def test_empty_history():
    """Verify safe fallback when history is empty or None without crashing."""
    assert predict_persistence([]) == 0.0
    assert predict_persistence(None) == 0.0
    assert predict_moving_average([]) == 0.0
    assert predict_moving_average(None) == 0.0
    assert predict_linear_trend([], [], datetime(2026, 9, 12, 16, 1, 0)) == 0.0


# 6. NaN handling
def test_nan_handling():
    """Verify NaNs are filtered and never silently propagate."""
    history_nan = [0.2, np.nan, 0.4, np.nan, 0.6]
    assert abs(predict_persistence(history_nan) - 0.6) < 1e-5
    # Moving average of valid [0.2, 0.4, 0.6] with window 3 = 0.4
    assert abs(predict_moving_average(history_nan, window_size=3) - 0.4) < 1e-5

    # All NaNs
    assert predict_persistence([np.nan, np.nan]) == 0.0
    assert predict_moving_average([np.nan, np.nan]) == 0.0


# 7. Insufficient history handling
def test_insufficient_history():
    """Verify handling when observations are fewer than requested window."""
    # Fewer observations than window size (window=5, points=2)
    history = [0.30, 0.50]
    pred = predict_moving_average(history, window_size=5, min_points=1)
    # Uses available 2 points: mean(0.3, 0.5) = 0.4
    assert abs(pred - 0.40) < 1e-5

    # Below min_points
    pred_below = predict_moving_average(history, window_size=5, min_points=3, default_value=0.0)
    assert pred_below == 0.0


# 8. Constant values
def test_constant_values():
    """Verify linear trend works seamlessly on constant history (zero slope)."""
    t0 = datetime(2026, 9, 12, 16, 0, 0)
    timestamps = [t0, t0 + timedelta(seconds=10), t0 + timedelta(seconds=20)]
    history = [0.55, 0.55, 0.55]
    t_future = t0 + timedelta(seconds=30)

    pred = predict_linear_trend(history, timestamps, t_future)
    assert abs(pred - 0.55) < 1e-5


# 9. Increasing congestion trend
def test_increasing_trend():
    """Verify linear trend extrapolates higher future congestion on rising values."""
    t0 = datetime(2026, 9, 12, 16, 0, 0)
    timestamps = [t0, t0 + timedelta(seconds=10), t0 + timedelta(seconds=20)]
    history = [0.20, 0.35, 0.50]
    t_future = t0 + timedelta(seconds=30)

    pred = predict_linear_trend(history, timestamps, t_future)
    assert pred > 0.50
    assert abs(pred - 0.65) < 1e-5


# 10. Decreasing congestion trend
def test_decreasing_trend():
    """Verify linear trend extrapolates lower future congestion on falling values."""
    t0 = datetime(2026, 9, 12, 16, 0, 0)
    timestamps = [t0, t0 + timedelta(seconds=10), t0 + timedelta(seconds=20)]
    history = [0.60, 0.45, 0.30]
    t_future = t0 + timedelta(seconds=30)

    pred = predict_linear_trend(history, timestamps, t_future)
    assert pred < 0.30
    assert abs(pred - 0.15) < 1e-5


# 11. Future timestamp validation (temporal order check)
def test_future_timestamp_validation():
    """Verify that temporal ordering is enforced: future_timestamp must be > max(timestamps)."""
    t0 = datetime(2026, 9, 12, 16, 0, 0)
    timestamps = [t0, t0 + timedelta(seconds=10), t0 + timedelta(seconds=30)]
    history = [0.10, 0.20, 0.30]

    # Target timestamp equal to or before latest observation must raise ValueError
    with pytest.raises(ValueError, match="Temporal leakage detected"):
        predict_linear_trend(history, timestamps, future_timestamp=t0 + timedelta(seconds=30))

    with pytest.raises(ValueError, match="Temporal leakage detected"):
        predict_linear_trend(history, timestamps, future_timestamp=t0 + timedelta(seconds=20))


# 12. Metric calculation
def test_metric_calculation():
    """Verify regression metrics calculate MAE, MSE, RMSE, and R2 accurately."""
    y_true = [0.1, 0.3, 0.5]
    y_pred = [0.1, 0.3, 0.5]

    perfect_metrics = calculate_regression_metrics(y_true, y_pred)
    assert perfect_metrics["mae"] == 0.0
    assert perfect_metrics["mse"] == 0.0
    assert perfect_metrics["rmse"] == 0.0
    assert perfect_metrics["r2"] == 1.0

    offset_metrics = calculate_regression_metrics([0.0, 0.0], [0.2, 0.2])
    assert offset_metrics["mae"] == 0.20
    assert offset_metrics["mse"] == 0.04


# 13. Classification conversion
def test_classification_conversion():
    """Verify score_to_class applies exact thresholds [0.33, 0.67]."""
    assert score_to_class(0.0) == "LOW"
    assert score_to_class(0.25) == "LOW"
    assert score_to_class(0.3299) == "LOW"
    assert score_to_class(0.33) == "MEDIUM"
    assert score_to_class(0.50) == "MEDIUM"
    assert score_to_class(0.67) == "MEDIUM"
    assert score_to_class(0.6701) == "HIGH"
    assert score_to_class(1.0) == "HIGH"


# 14. Leakage prevention
def test_leakage_prevention():
    """Verify extract_history_for_sample never accesses future timestamps or scores."""
    sample_row = pd.Series({
        "device_id": "h1",
        "sequence_start": "2026-09-12 16:00:00",
        "sequence_end": "2026-09-12 16:00:30",
        "prediction_timestamp": "2026-09-12 16:01:00",
        "future_congestion_score": 0.88,  # Target should NEVER be returned as history
        "future_congestion_class": "HIGH",
    })

    telemetry_data = [
        {"device_id": "h1", "timestamp": "2026-09-12 16:00:10", "throughput_mbps": 10.0, "rtt_ms": 2.0, "packet_loss_percent": 0.0, "active_connections": 2},
        {"device_id": "h1", "timestamp": "2026-09-12 16:00:25", "throughput_mbps": 20.0, "rtt_ms": 3.0, "packet_loss_percent": 0.0, "active_connections": 3},
        {"device_id": "h1", "timestamp": "2026-09-12 16:01:05", "throughput_mbps": 90.0, "rtt_ms": 50.0, "packet_loss_percent": 10.0, "active_connections": 15},  # FUTURE
    ]
    telemetry_df = pd.DataFrame(telemetry_data)

    scores, timestamps = extract_history_for_sample(sample_row, telemetry_df)

    # Must only extract records up to sequence_end (16:00:30)
    assert len(scores) == 2
    for ts in timestamps:
        assert ts < pd.to_datetime("2026-09-12 16:01:00")
        assert ts <= pd.to_datetime("2026-09-12 16:00:30")


# 15. Comparison file generation
def test_comparison_file_generation(tmp_path):
    """Verify build_comparison_dataframe and export_model_comparison_csv."""
    gru_metrics = {
        "regression_metrics": {"mae": 0.3594, "mse": 0.1292, "rmse": 0.3594, "r2": 0.0},
        "classification_metrics": {"accuracy": 0.0, "f1_macro": 0.0},
    }
    baseline_metrics = {
        "persistence": {"mae": 0.0, "mse": 0.0, "rmse": 0.0, "r2": 0.0, "accuracy": 1.0, "f1": 0.3333},
        "moving_average": {"mae": 0.0, "mse": 0.0, "rmse": 0.0, "r2": 0.0, "accuracy": 1.0, "f1": 0.3333},
        "linear_trend": {"mae": 0.0, "mse": 0.0, "rmse": 0.0, "r2": 0.0, "accuracy": 1.0, "f1": 0.3333},
    }

    df = build_comparison_dataframe(gru_metrics, baseline_metrics)
    assert len(df) == 4
    assert list(df["model"]) == ["GRU", "Persistence", "MovingAverage", "LinearTrend"]

    out_csv = tmp_path / "model_comparison.csv"
    export_model_comparison_csv(df, out_csv)
    assert out_csv.exists()

    loaded = pd.read_csv(out_csv)
    assert "mae" in loaded.columns
    assert "rmse" in loaded.columns
    assert len(loaded) == 4
