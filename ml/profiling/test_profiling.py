"""Deterministic Unit and Integration Test Suite for Phase 8 Profiling.

Verifies:
1. Feature loading from CSV
2. Required-feature validation & alias resolution
3. Device-level aggregation from multi-row flow telemetry
4. Missing-value handling (median imputation & safe zero fallback)
5. Feature scaling (StandardScaler normalization)
6. K-Means execution & deterministic reproducibility
7. Cluster assignment mapping
8. Silhouette score calculation
9. Small-dataset handling (graceful boundary adaptation)
10. Output CSV creation (behavior_profiles.csv & cluster_summary.csv)
11. Model saving & deserialization (clustering_model.pkl)
12. Scaler saving & deserialization (scaler.pkl)
"""

import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from ml.profiling.clustering import (
    evaluate_kmeans_range,
    run_dbscan_comparison,
    select_best_k,
    train_kmeans,
)
from ml.profiling.config import DEFAULT_INPUT_PATH, RANDOM_STATE
from ml.profiling.evaluation import (
    plot_cluster_visualization,
    save_evaluation_results,
    save_model_artifacts,
)
from ml.profiling.preprocessing import (
    aggregate_device_behavior,
    handle_missing_values,
    load_feature_dataset,
    scale_features,
    validate_required_features,
)
from ml.profiling.profile_definitions import (
    assign_descriptive_profile_labels,
    build_factual_descriptions,
    compute_cluster_summary,
)


@pytest.fixture
def sample_deterministic_flow_df() -> pd.DataFrame:
    """Fixture providing deterministic, multi-row network telemetry for 4 devices."""
    data = {
        "timestamp": [
            "2026-09-12 10:00:00", "2026-09-12 10:05:00",
            "2026-09-12 10:00:00", "2026-09-12 10:05:00",
            "2026-09-12 10:00:00", "2026-09-12 10:05:00",
            "2026-09-12 10:00:00", "2026-09-12 11:00:00",
        ],
        "device_id": ["h1", "h1", "h2", "h2", "h3", "h3", "h4", "h4"],
        "hour": [10, 10, 10, 10, 10, 10, 10, 11],
        "mean_throughput_mbps": [50.0, 50.0, 5.0, 5.0, 20.0, 20.0, 80.0, 80.0],
        "throughput_std": [2.5, 2.5, 0.5, 0.5, 1.2, 1.2, 4.0, 4.0],
        "mean_rtt_ms": [2.1, 2.1, 15.4, 15.4, 8.0, 8.0, 1.8, 1.8],
        "rtt_std": [0.3, 0.3, 1.2, 1.2, 0.8, 0.8, 0.2, 0.2],
        "mean_packet_loss_percent": [0.0, 0.0, 1.5, 1.5, 0.2, 0.2, 0.0, 0.0],
        "mean_active_connections": [5.0, 5.0, 1.0, 1.0, 2.0, 2.0, 12.0, 12.0],
        "total_flow_count": [40, 40, 10, 10, 25, 25, 90, 90],
        "tcp_flow_ratio": [0.9, 0.9, 0.2, 0.2, 0.8, 0.8, 0.95, 0.95],
        "udp_flow_ratio": [0.1, 0.1, 0.8, 0.8, 0.2, 0.2, 0.05, 0.05],
    }
    return pd.DataFrame(data)


# 1. Feature Loading
def test_feature_loading_success(tmp_path: Path, sample_deterministic_flow_df: pd.DataFrame):
    csv_file = tmp_path / "valid_features.csv"
    sample_deterministic_flow_df.to_csv(csv_file, index=False)

    loaded = load_feature_dataset(csv_file)
    assert len(loaded) == len(sample_deterministic_flow_df)
    assert "device_id" in loaded.columns


def test_feature_loading_missing_file():
    with pytest.raises(FileNotFoundError):
        load_feature_dataset("non_existent_features_12345.csv")


def test_feature_loading_missing_device_id(tmp_path: Path):
    csv_file = tmp_path / "no_device_id.csv"
    pd.DataFrame({"metric": [1, 2]}).to_csv(csv_file, index=False)
    with pytest.raises(ValueError, match="Missing required identifier column 'device_id'"):
        load_feature_dataset(csv_file)


# 2. Required-Feature Validation
def test_required_feature_validation(sample_deterministic_flow_df: pd.DataFrame):
    available, missing = validate_required_features(sample_deterministic_flow_df)
    assert "mean_throughput_mbps" in available
    assert "total_flow_count" in available
    assert "active_hours_count" in available  # derived from 'hour'
    assert isinstance(missing, list)


# 3. Device-Level Aggregation
def test_device_level_aggregation(sample_deterministic_flow_df: pd.DataFrame):
    device_df = aggregate_device_behavior(sample_deterministic_flow_df)
    # Must aggregate exactly to 4 distinct devices
    assert len(device_df) == 4
    assert list(device_df["device_id"]) == ["h1", "h2", "h3", "h4"]
    # Check temporal active_hours_count for h4 (active across 10 and 11 -> 2 hours)
    h4_row = device_df[device_df["device_id"] == "h4"].iloc[0]
    assert h4_row["active_hours_count"] == 2
    # Check h1 active_hours_count (only hour 10 -> 1 hour)
    h1_row = device_df[device_df["device_id"] == "h1"].iloc[0]
    assert h1_row["active_hours_count"] == 1


# 4. Missing-Value Handling
def test_missing_value_handling_partial_nan():
    data = {
        "device_id": ["h1", "h2", "h3"],
        "mean_throughput_mbps": [10.0, np.nan, 30.0],
        "mean_rtt_ms": [2.0, 4.0, 6.0],
    }
    df = pd.DataFrame(data)
    clean_df, report = handle_missing_values(df, ["mean_throughput_mbps", "mean_rtt_ms"])
    # Median of [10.0, 30.0] is 20.0
    assert clean_df.loc[1, "mean_throughput_mbps"] == 20.0
    assert "median" in report["mean_throughput_mbps"]


def test_missing_value_handling_all_nan_fallback():
    data = {
        "device_id": ["h1", "h2", "h3"],
        "mean_packet_loss_percent": [np.nan, np.nan, np.nan],
    }
    df = pd.DataFrame(data)
    clean_df, report = handle_missing_values(df, ["mean_packet_loss_percent"])
    # Safe 0.0 fallback when 100% missing
    assert clean_df["mean_packet_loss_percent"].tolist() == [0.0, 0.0, 0.0]
    assert "fallback 0.0" in report["mean_packet_loss_percent"]


# 5. Feature Scaling
def test_feature_scaling():
    data = {
        "device_id": ["h1", "h2", "h3", "h4"],
        "f1": [10.0, 20.0, 30.0, 40.0],
        "f2": [100.0, 200.0, 300.0, 400.0],
    }
    df = pd.DataFrame(data)
    X_scaled, scaler, features = scale_features(df, ["f1", "f2"])

    assert X_scaled.shape == (4, 2)
    assert isinstance(scaler, StandardScaler)
    assert features == ["f1", "f2"]
    # Check standardized properties: mean approx 0, std approx 1
    assert pytest.approx(float(np.mean(X_scaled[:, 0])), abs=1e-5) == 0.0
    assert pytest.approx(float(np.std(X_scaled[:, 0])), abs=1e-5) == 1.0


# 6. K-Means Execution & Reproducibility
def test_kmeans_execution_reproducibility():
    X = np.array([
        [1.0, 2.0], [1.1, 2.1], [1.2, 1.9],
        [10.0, 15.0], [10.5, 14.8], [9.8, 15.2],
    ], dtype=np.float64)

    model1, labels1 = train_kmeans(X, n_clusters=2, random_state=RANDOM_STATE)
    model2, labels2 = train_kmeans(X, n_clusters=2, random_state=RANDOM_STATE)

    assert np.array_equal(labels1, labels2)
    assert model1.inertia_ == pytest.approx(model2.inertia_)
    assert len(set(labels1)) == 2


# 7. Cluster Assignment
def test_cluster_assignment(sample_deterministic_flow_df: pd.DataFrame):
    device_df = aggregate_device_behavior(sample_deterministic_flow_df)
    features = ["mean_throughput_mbps", "total_flow_count"]
    clean_df, _ = handle_missing_values(device_df, features)
    X_scaled, _, _ = scale_features(clean_df, features)

    model, labels = train_kmeans(X_scaled, n_clusters=2, random_state=RANDOM_STATE)
    assert len(labels) == len(device_df)
    for cid in labels:
        assert isinstance(int(cid), int)
        assert cid in [0, 1]


# 8. Silhouette Calculation
def test_silhouette_calculation():
    # Two well-separated tight clusters
    X = np.array([
        [0.0, 0.0], [0.1, 0.1], [0.0, 0.2],
        [10.0, 10.0], [10.1, 10.1], [9.9, 10.0],
    ], dtype=np.float64)

    eval_df = evaluate_kmeans_range(X, min_k=2, max_k=3, random_state=RANDOM_STATE)
    assert not eval_df.empty
    row_k2 = eval_df[eval_df["k"] == 2].iloc[0]
    assert pd.notna(row_k2["silhouette_score"])
    assert row_k2["silhouette_score"] > 0.8  # Very high separation


# 9. Small-Dataset Handling
def test_small_dataset_handling():
    # Only 3 devices
    X_small = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    eval_df = evaluate_kmeans_range(X_small, min_k=2, max_k=5, random_state=RANDOM_STATE)
    # Must not crash! Should restrict evaluation to k=2
    assert len(eval_df) == 1
    assert eval_df.iloc[0]["k"] == 2

    # Single device case
    X_single = np.array([[1.0, 2.0]])
    eval_single = evaluate_kmeans_range(X_single, min_k=2, max_k=3)
    assert eval_single.iloc[0]["k"] == 1


# 10. Output CSV Creation
def test_output_csv_creation(tmp_path: Path, sample_deterministic_flow_df: pd.DataFrame):
    device_df = aggregate_device_behavior(sample_deterministic_flow_df)
    features = ["mean_throughput_mbps", "total_flow_count"]
    clean_df, _ = handle_missing_values(device_df, features)
    labels = np.array([0, 1, 0, 1])

    summary_df = compute_cluster_summary(clean_df, labels, features)
    summary_path = tmp_path / "cluster_summary.csv"
    summary_df.to_csv(summary_path, index=False)
    assert summary_path.exists()
    assert summary_path.stat().st_size > 0

    profiles_df = clean_df.copy()
    profiles_df["cluster_id"] = labels
    profiles_path = tmp_path / "behavior_profiles.csv"
    profiles_df.to_csv(profiles_path, index=False)
    assert profiles_path.exists()
    assert profiles_path.stat().st_size > 0


# 11. Model Saving and Deserialization
def test_model_saving_and_loading(tmp_path: Path):
    X = np.array([[1.0, 2.0], [1.1, 2.2], [10.0, 12.0], [10.2, 11.8]])
    model, _ = train_kmeans(X, n_clusters=2, random_state=RANDOM_STATE)
    scaler = StandardScaler().fit(X)

    m_path = tmp_path / "clustering_model.pkl"
    s_path = tmp_path / "scaler.pkl"
    f_path = tmp_path / "clustering_features.json"

    save_model_artifacts(model, scaler, ["feat1", "feat2"], m_path, s_path, f_path)

    loaded_model = joblib.load(m_path)
    assert isinstance(loaded_model, KMeans)
    assert loaded_model.n_clusters == 2
    assert np.array_equal(loaded_model.cluster_centers_, model.cluster_centers_)


# 12. Scaler Saving and Deserialization
def test_scaler_saving_and_loading(tmp_path: Path):
    X = np.array([[1.0, 10.0], [3.0, 30.0], [5.0, 50.0]])
    scaler = StandardScaler().fit(X)

    m_path = tmp_path / "clustering_model.pkl"
    s_path = tmp_path / "scaler.pkl"
    f_path = tmp_path / "clustering_features.json"
    dummy_model = KMeans(n_clusters=2, random_state=42).fit(X)

    save_model_artifacts(dummy_model, scaler, ["f1", "f2"], m_path, s_path, f_path)

    loaded_scaler = joblib.load(s_path)
    assert isinstance(loaded_scaler, StandardScaler)
    assert np.allclose(loaded_scaler.mean_, scaler.mean_)
    assert np.allclose(loaded_scaler.scale_, scaler.scale_)


# End-to-End Real Dataset Test
def test_end_to_end_real_phase7_dataset():
    if not DEFAULT_INPUT_PATH.exists():
        pytest.skip(f"Phase 7 dataset {DEFAULT_INPUT_PATH} not found.")

    raw_df = load_feature_dataset(DEFAULT_INPUT_PATH)
    assert len(raw_df) > 0

    device_df = aggregate_device_behavior(raw_df)
    assert len(device_df) >= 2

    available, _ = validate_required_features(raw_df)
    features = [f for f in available if f in device_df.columns]
    assert len(features) >= 4

    clean_df, _ = handle_missing_values(device_df, features)
    X_scaled, scaler, _ = scale_features(clean_df, features)

    eval_df = evaluate_kmeans_range(X_scaled, min_k=2, max_k=4)
    assert not eval_df.empty

    best_k = select_best_k(eval_df)
    assert 2 <= best_k <= len(device_df)

    model, labels = train_kmeans(X_scaled, n_clusters=best_k)
    assert len(labels) == len(device_df)
