"""Pytest test suite for Phase 7 Feature Extraction Module.

Verifies end-to-end integration, real dataset extraction from Phase 6 outputs,
and boundary cases.
"""

from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from ml.features.config import DEFAULT_INPUT_PATH, DEFAULT_OUTPUT_PATH
from ml.features.feature_extractor import (
    extract_all_features,
    extract_flow_features,
    extract_time_features,
    extract_device_aggregations,
    extract_traffic_mix_features,
    validate_features,
)
from ml.features.preprocessing import load_network_data, prepare_scaled_features
from ml.features.feature_definitions import FEATURE_CATALOG, list_features, get_feature_info


def test_feature_catalog_coverage():
    """Verify that all core features have entries in the feature definitions catalog."""
    features = list_features()
    expected_core = [
        "device_id",
        "flow_id",
        "throughput_mbps",
        "rtt_ms",
        "packet_loss_percent",
        "active_connections",
        "protocol_numeric",
        "hour",
        "minute",
        "day_of_week",
        "is_weekend",
        "time_of_day",
        "mean_throughput_mbps",
        "max_throughput_mbps",
        "min_throughput_mbps",
        "throughput_std",
        "tcp_flow_ratio",
        "udp_flow_ratio",
        "rolling_mean_throughput_5m",
    ]
    for feat in expected_core:
        assert feat in features, f"Core feature {feat} missing from FEATURE_CATALOG"
        info = get_feature_info(feat)
        assert "description" in info and len(info["description"]) > 0


def test_real_dataset_extraction_if_available(tmp_path):
    """Run full feature extraction pipeline against Phase 6 network_metrics.csv."""
    if not DEFAULT_INPUT_PATH.exists():
        pytest.skip(f"Input dataset not found at {DEFAULT_INPUT_PATH}")

    df_raw = load_network_data(DEFAULT_INPUT_PATH)
    assert len(df_raw) > 0, "Phase 6 network_metrics.csv is empty"

    features_df = extract_all_features(df_raw, window_seconds=300)
    assert 0 < len(features_df) <= len(df_raw)
    assert "flow_id" in features_df.columns
    assert "tcp_flow_ratio" in features_df.columns
    assert "udp_flow_ratio" in features_df.columns

    is_valid, issues = validate_features(features_df)
    assert is_valid, f"Feature quality validation failed with issues: {issues}"

    out_file = tmp_path / "test_out_features.csv"
    features_df.to_csv(out_file, index=False)
    assert out_file.exists()
    assert out_file.stat().st_size > 0


def test_empty_dataframe_handling():
    """Verify clean behavior when handling empty dataframe."""
    cols = [
        "timestamp",
        "device_id",
        "src_ip",
        "dst_ip",
        "src_port",
        "dst_port",
        "protocol",
        "throughput",
        "rtt",
        "packet_loss",
        "active_connections",
    ]
    empty_df = pd.DataFrame(columns=cols)
    out_df = extract_all_features(empty_df)
    assert len(out_df) == 0


def test_traffic_mix_bounds():
    """Verify that tcp_flow_ratio and udp_flow_ratio always sum to 1.0 per device."""
    data = {
        "timestamp": ["2026-09-12 10:00:00", "2026-09-12 10:01:00", "2026-09-12 10:02:00"],
        "device_id": ["h1", "h1", "h1"],
        "src_ip": ["192.168.1.10", "192.168.1.10", "192.168.1.10"],
        "dst_ip": ["192.168.1.11", "192.168.1.11", "192.168.1.11"],
        "src_port": [5000, 5001, 5002],
        "dst_port": [5201, 5201, 5201],
        "protocol": ["TCP", "TCP", "UDP"],
        "throughput": [10.0, 20.0, 30.0],
        "rtt": [2.0, 4.0, np.nan],
        "packet_loss": [0.0, 0.0, 1.0],
        "active_connections": [1, 2, 1],
    }
    df = pd.DataFrame(data)
    features_df = extract_all_features(df)

    assert len(features_df) == 3
    h1_rows = features_df[features_df["device_id"] == "h1"]
    tcp_ratio = h1_rows.iloc[0]["tcp_flow_ratio"]
    udp_ratio = h1_rows.iloc[0]["udp_flow_ratio"]

    assert pytest.approx(tcp_ratio, 0.001) == 2.0 / 3.0
    assert pytest.approx(udp_ratio, 0.001) == 1.0 / 3.0
    assert pytest.approx(tcp_ratio + udp_ratio, 0.001) == 1.0
