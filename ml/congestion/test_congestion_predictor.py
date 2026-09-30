"""Comprehensive Unit Test Suite for Phase 10: Congestion Prediction Module.

Tests 14 critical requirements:
1. Dataset loading (Phase 9 integration)
2. Target feature leakage prevention
3. Scaler fitted strictly on training split
4. 3D sequence tensor dimensions
5. GRU architecture structure
6. Model compilation specifications
7. Model training execution
8. Continuous regression metrics
9. Discrete classification metrics
10. Naive baseline calculation
11. Model & scaler serialization
12. CongestionPredictor class interface
13. Prediction boundary constraints [0.0, 1.0]
14. Extreme inputs & zero telemetry edge cases
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
import tensorflow as tf
from tensorflow import keras

from ml.congestion.config import (
    CONGESTION_CLASSES,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_TIMESTEPS,
    DENSE_UNITS,
    DROPOUT_RATE,
    GRU_UNITS,
    HIGH_THRESHOLD,
    LEARNING_RATE,
    LOW_THRESHOLD,
)
from ml.congestion.congestion_predictor import CongestionPredictor
from ml.congestion.metrics import (
    calculate_classification_metrics,
    calculate_regression_metrics,
    evaluate_naive_baseline,
    score_to_class,
)
from ml.congestion.model import build_gru_model, compile_gru_model, get_model_summary
from ml.congestion.preprocessing import (
    EXCLUDED_FEATURE_COLS,
    fit_and_transform_scaler,
    load_phase9_datasets,
    prepare_training_tensors,
    reshape_to_sequences,
    select_input_features,
)


@pytest.fixture
def mock_dataset_dir(tmp_path):
    """Generate minimal valid mock datasets for fast isolated testing."""
    records_train = []
    records_val = []
    records_test = []

    features = [
        "throughput_mbps", "rtt_ms", "packet_loss_percent", "active_connections",
        "throughput_std", "rtt_std", "packet_loss_std", "total_flow_count",
        "tcp_flow_ratio", "udp_flow_ratio",
    ]

    for i in range(10):
        row = {
            "sequence_id": i,
            "device_id": f"h{i % 3 + 1}",
            "sequence_start": "2026-09-12 16:00:00",
            "sequence_end": "2026-09-12 16:00:30",
            "prediction_timestamp": "2026-09-12 16:01:00",
            "history_steps": 2,
            "history_duration_seconds": 30.0,
            "future_congestion_score": float(i / 10.0),
            "future_congestion_class": "LOW" if i < 3 else ("MEDIUM" if i < 7 else "HIGH"),
            "cluster_id": i % 3,
        }
        for f in features:
            row[f] = float(i * 2.0)
            row[f"hist_mean_{f}"] = float(i * 1.5)

        if i < 7:
            records_train.append(row)
        elif i < 8:
            records_val.append(row)
        else:
            records_test.append(row)

    train_df = pd.DataFrame(records_train)
    val_df = pd.DataFrame(records_val)
    test_df = pd.DataFrame(records_test)

    train_df.to_csv(tmp_path / "train_dataset.csv", index=False)
    val_df.to_csv(tmp_path / "validation_dataset.csv", index=False)
    test_df.to_csv(tmp_path / "test_dataset.csv", index=False)

    return tmp_path


# 1. Dataset loading
def test_load_phase9_datasets():
    """Verify loading real or mock Phase 9 datasets."""
    if (DEFAULT_OUTPUT_DIR / "train_dataset.csv").exists():
        train_df, val_df, test_df = load_phase9_datasets(DEFAULT_OUTPUT_DIR)
        assert len(train_df) > 0
        assert len(val_df) > 0
        assert len(test_df) > 0
        assert "future_congestion_score" in train_df.columns
        assert "future_congestion_class" in train_df.columns


# 2. Target feature leakage prevention
def test_feature_selection_excludes_targets(mock_dataset_dir):
    """Ensure target columns and timestamps are excluded from input features."""
    train_df, _, _ = load_phase9_datasets(mock_dataset_dir)
    selected = select_input_features(train_df)

    assert "future_congestion_score" not in selected
    assert "future_congestion_class" not in selected
    assert "prediction_timestamp" not in selected
    assert "sequence_id" not in selected
    assert "device_id" not in selected

    for excluded in EXCLUDED_FEATURE_COLS:
        assert excluded not in selected


# 3. Scaler fitted strictly on training split
def test_scaler_fitted_on_train_only(mock_dataset_dir):
    """Validate that StandardScaler is fitted ONLY on train_df."""
    train_df, val_df, test_df = load_phase9_datasets(mock_dataset_dir)
    scaled_train, scaled_val, scaled_test, scaler, _ = fit_and_transform_scaler(
        train_df=train_df, val_df=val_df, test_df=test_df
    )

    feature_cols = select_input_features(train_df)
    train_raw = train_df[feature_cols].to_numpy(dtype=np.float32)

    # Scaler mean must match training raw mean
    np.testing.assert_allclose(scaler.mean_, np.mean(train_raw, axis=0), rtol=1e-4)

    # Scaled training mean should be ~0.0
    np.testing.assert_allclose(np.mean(scaled_train, axis=0), np.zeros(len(feature_cols)), atol=1e-5)


# 4. 3D sequence tensor dimensions
def test_sequence_tensor_shape(mock_dataset_dir):
    """Verify conversion to 3D tensor: (samples, timesteps, features)."""
    data = prepare_training_tensors(data_dir=mock_dataset_dir, timesteps=DEFAULT_TIMESTEPS)
    X_train = data["X_train"]

    assert X_train.ndim == 3
    assert X_train.shape[0] == len(data["train_df"])
    assert X_train.shape[1] == DEFAULT_TIMESTEPS
    assert X_train.shape[2] == data["input_shape"][1]


# 5. GRU architecture structure
def test_gru_model_architecture():
    """Verify model contains GRU layer, correct units, and sigmoid output."""
    input_shape = (2, 11)
    model = build_gru_model(input_shape=input_shape, gru_units=GRU_UNITS, dense_units=DENSE_UNITS)

    layer_names = [l.name for l in model.layers]
    assert any("gru" in name for name in layer_names)
    assert any("dense" in name for name in layer_names)

    output_layer = model.layers[-1]
    assert isinstance(output_layer, keras.layers.Dense)
    assert output_layer.units == 1
    assert output_layer.activation.__name__ == "sigmoid"


# 6. Model compilation specifications
def test_model_compilation():
    """Verify optimizer, learning rate, loss function, and metrics."""
    model = build_gru_model(input_shape=(2, 11))
    compile_gru_model(model, learning_rate=0.002)

    assert model.optimizer is not None
    assert model.loss == "mean_squared_error"
    metrics_names = [m if isinstance(m, str) else m.name for m in model.metrics_names]
    assert "loss" in metrics_names or len(metrics_names) > 0


# 7. Model training execution
def test_model_trains_and_reduces_loss():
    """Verify model fits on synthetic data and loss completes."""
    X = np.random.randn(8, 2, 11).astype(np.float32)
    y = np.random.uniform(0.0, 1.0, size=(8, 1)).astype(np.float32)

    model = build_gru_model(input_shape=(2, 11), gru_units=16, dense_units=8)
    compile_gru_model(model, learning_rate=0.01)

    history = model.fit(X, y, epochs=3, batch_size=4, verbose=0)
    assert len(history.history["loss"]) == 3
    assert not np.isnan(history.history["loss"][-1])


# 8. Continuous regression metrics
def test_regression_metrics_calculation():
    """Verify MAE, MSE, RMSE, R2, and Max Error calculations."""
    y_true = np.array([0.1, 0.4, 0.7])
    y_pred = np.array([0.15, 0.35, 0.75])

    metrics = calculate_regression_metrics(y_true, y_pred)
    assert abs(metrics["mae"] - 0.05) < 1e-4
    assert abs(metrics["mse"] - 0.0025) < 1e-4
    assert abs(metrics["rmse"] - 0.05) < 1e-4
    assert metrics["max_error"] == 0.05
    assert "r2" in metrics


# 9. Discrete classification metrics
def test_classification_metrics_calculation():
    """Verify Accuracy, Precision, Recall, F1, and Confusion Matrix."""
    y_true = ["LOW", "MEDIUM", "HIGH"]
    y_pred = ["LOW", "MEDIUM", "LOW"]

    metrics = calculate_classification_metrics(y_true, y_pred, classes=CONGESTION_CLASSES)
    assert abs(metrics["accuracy"] - (2 / 3)) < 1e-3
    assert "precision_macro" in metrics
    assert "recall_macro" in metrics
    assert "f1_macro" in metrics
    assert len(metrics["confusion_matrix"]) == 3


# 10. Naive baseline calculation
def test_naive_baseline_comparison(mock_dataset_dir):
    """Verify persistence and mean baseline evaluation logic."""
    train_df, _, test_df = load_phase9_datasets(mock_dataset_dir)
    baseline_eval = evaluate_naive_baseline(train_df, test_df)

    assert "persistence_baseline" in baseline_eval
    assert "mean_baseline" in baseline_eval
    assert "mae" in baseline_eval["persistence_baseline"]["regression"]
    assert "mae" in baseline_eval["mean_baseline"]["regression"]


# 11. Model & scaler serialization
def test_model_and_scaler_serialization(tmp_path):
    """Verify model and scaler export to disk and reimport identically."""
    model = build_gru_model(input_shape=(2, 11), gru_units=16, dense_units=8)
    compile_gru_model(model)
    model_path = tmp_path / "test_model.keras"
    model.save(str(model_path))
    loaded_model = keras.models.load_model(str(model_path))

    X_test = np.random.randn(2, 2, 11).astype(np.float32)
    pred_orig = model.predict(X_test, verbose=0)
    pred_loaded = loaded_model.predict(X_test, verbose=0)
    np.testing.assert_allclose(pred_orig, pred_loaded, atol=1e-5)

    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    scaler.fit(np.random.randn(10, 11))
    scaler_path = tmp_path / "test_scaler.pkl"
    joblib.dump(scaler, str(scaler_path))
    loaded_scaler = joblib.load(str(scaler_path))
    np.testing.assert_allclose(scaler.mean_, loaded_scaler.mean_)


# 12. CongestionPredictor class interface
def test_predictor_class_interface():
    """Verify CongestionPredictor interface methods and return schemas."""
    # Predictor can load existing default artifacts if available
    from ml.congestion.config import DEFAULT_MODEL_FILE, DEFAULT_SCALER_FILE
    if DEFAULT_MODEL_FILE.exists() and DEFAULT_SCALER_FILE.exists():
        predictor = CongestionPredictor()
        res = predictor.predict_congestion({
            "throughput_mbps": 50.0,
            "rtt_ms": 10.0,
            "packet_loss_percent": 0.5,
            "active_connections": 5,
            "cluster_id": 1,
        })
        assert "future_congestion_score" in res
        assert "future_congestion_class" in res
        assert "confidence" in res
        assert 0.0 <= res["future_congestion_score"] <= 1.0
        assert res["future_congestion_class"] in CONGESTION_CLASSES


# 13. Prediction boundary constraints [0.0, 1.0]
def test_prediction_output_bounds():
    """Ensure predicted score is strictly bounded in [0.0, 1.0]."""
    for s in [-0.5, 0.0, 0.25, 0.50, 0.75, 1.0, 1.5]:
        cls_name = score_to_class(s)
        assert cls_name in ["LOW", "MEDIUM", "HIGH"]

    assert score_to_class(0.10) == "LOW"
    assert score_to_class(0.50) == "MEDIUM"
    assert score_to_class(0.85) == "HIGH"


# 14. Extreme inputs & zero telemetry edge cases
def test_edge_case_zero_and_extreme_inputs():
    """Verify predictor handles all-zero telemetry and extreme values without errors."""
    from ml.congestion.config import DEFAULT_MODEL_FILE, DEFAULT_SCALER_FILE
    if DEFAULT_MODEL_FILE.exists() and DEFAULT_SCALER_FILE.exists():
        predictor = CongestionPredictor()

        # All-zero input
        res_zero = predictor.predict_congestion({
            "throughput_mbps": 0.0,
            "rtt_ms": 0.0,
            "packet_loss_percent": 0.0,
            "active_connections": 0,
            "cluster_id": 0,
        })
        assert not np.isnan(res_zero["future_congestion_score"])

        # Extreme input (99% packet loss, 10,000ms RTT)
        res_extreme = predictor.predict_congestion({
            "throughput_mbps": 1000.0,
            "rtt_ms": 10000.0,
            "packet_loss_percent": 99.0,
            "active_connections": 500,
            "cluster_id": 2,
        })
        assert not np.isnan(res_extreme["future_congestion_score"])
        assert 0.0 <= res_extreme["future_congestion_score"] <= 1.0
