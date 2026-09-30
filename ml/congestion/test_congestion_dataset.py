"""Unit and Integration Tests for Phase 9: Congestion Dataset Module.

Verifies:
1. Timestamp parsing & chronological sorting
2. History-window generation
3. Prediction horizon generation
4. Congestion score range ([0.0, 1.0])
5. Congestion class generation (LOW, MEDIUM, HIGH)
6. Future-target correctness (target_ts > anchor_ts)
7. Missing-value handling
8. Sequence generation & format
9. Chronological train/validation/test split
10. Data leakage prevention
11. Empty & small dataset handling
12. End-to-end dataset creation pipeline
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from ml.congestion.config import (
    DEFAULT_INPUT_PATH,
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
)
from ml.congestion.congestion_dataset import run_congestion_dataset_pipeline
from ml.congestion.congestion_labeling import (
    assign_congestion_class,
    calculate_congestion_score,
)
from ml.congestion.dataset_validation import (
    validate_features,
    validate_splits,
    validate_targets,
    validate_timestamps,
)
from ml.congestion.preprocessing import (
    detect_sampling_interval,
    handle_missing_features,
    load_and_prepare_telemetry,
)
from ml.congestion.time_window import (
    chronological_split,
    construct_future_targets,
    generate_time_series_sequences,
)


@pytest.fixture
def sample_timeseries_df() -> pd.DataFrame:
    """Deterministic synthetic multi-device network telemetry time series (1s steps)."""
    rows = []
    base_time = pd.Timestamp("2026-09-12 12:00:00")
    for sec in range(60):  # 60 seconds
        t = base_time + pd.Timedelta(seconds=sec)
        for dev in ["h1", "h2"]:
            # Gradual increase in throughput and latency
            tp = (sec * 1.5) if dev == "h1" else 5.0
            rtt = (2.0 + sec * 0.8) if dev == "h1" else 2.5
            loss = (0.2 * sec / 10.0) if sec > 30 and dev == "h1" else 0.0
            conn = int(1 + (sec // 10))
            rows.append({
                "timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
                "device_id": dev,
                "throughput_mbps": tp,
                "rtt_ms": rtt,
                "packet_loss_percent": loss,
                "active_connections": conn,
                "total_flow_count": 10 + sec,
                "tcp_flow_ratio": 1.0,
                "udp_flow_ratio": 0.0,
            })
    return pd.DataFrame(rows)


# 1. Timestamp Parsing & Chronological Sorting
def test_timestamp_parsing_and_sorting(tmp_path: Path):
    disordered_data = {
        "timestamp": [
            "2026-09-12 12:00:30",
            "2026-09-12 12:00:10",
            "2026-09-12 12:00:20",
            "invalid-date-string",
        ],
        "device_id": ["h1", "h1", "h1", "h1"],
        "throughput_mbps": [10.0, 5.0, 8.0, 0.0],
    }
    csv_file = tmp_path / "disordered.csv"
    pd.DataFrame(disordered_data).to_csv(csv_file, index=False)

    df, stats = load_and_prepare_telemetry(csv_file, profiles_path=None)
    assert stats["total_records"] == 4
    assert stats["valid_records"] == 3
    assert stats["removed_records"] == 1
    # Check sorted order
    assert df["timestamp"].is_monotonic_increasing
    assert df.iloc[0]["throughput_mbps"] == 5.0
    assert df.iloc[-1]["throughput_mbps"] == 10.0


# 2. History-Window Generation
def test_history_window_generation(sample_timeseries_df: pd.DataFrame):
    target_df, _ = construct_future_targets(sample_timeseries_df, horizon_seconds=10, tolerance_seconds=2)
    seq_df, stats = generate_time_series_sequences(
        target_df,
        history_window_seconds=20,
        min_history_steps=2,
    )
    assert not seq_df.empty
    assert stats["generated_sequences"] > 0
    # Every sequence must satisfy history_duration_seconds <= 20
    assert (seq_df["history_duration_seconds"] <= 20.0).all()
    # History steps must be at least min_history_steps
    assert (seq_df["history_steps"] >= 2).all()


# 3. Prediction Horizon Generation
def test_prediction_horizon_generation(sample_timeseries_df: pd.DataFrame):
    for horizon in [10, 20, 30]:
        target_df, stats = construct_future_targets(
            sample_timeseries_df,
            horizon_seconds=horizon,
            tolerance_seconds=2,
        )
        assert stats["matched_targets"] > 0
        # Check actual horizon is approximately the requested horizon
        mean_h = stats["mean_actual_horizon_seconds"]
        assert pytest.approx(mean_h, abs=3.0) == horizon


# 4. Congestion Score Range ([0.0, 1.0])
def test_congestion_score_range():
    test_cases = pd.DataFrame({
        "throughput_mbps": [0.0, 50.0, 100.0, 200.0],
        "rtt_ms": [2.0, 20.0, 100.0, 250.0],
        "packet_loss_percent": [0.0, 2.0, 10.0, 50.0],
        "active_connections": [0, 5, 20, 100],
    })
    scores = calculate_congestion_score(test_cases)
    assert len(scores) == 4
    # All scores strictly within [0.0, 1.0]
    assert (scores >= 0.0).all()
    assert (scores <= 1.0).all()
    # Zero baseline case produces 0.0
    assert pytest.approx(scores.iloc[0], abs=1e-5) == 0.0
    # High congestion case is close to or equal to 1.0
    assert scores.iloc[-1] >= 0.95


# 5. Congestion Class Generation (LOW, MEDIUM, HIGH)
def test_congestion_class_generation():
    scores = pd.Series([0.10, 0.32, 0.33, 0.50, 0.66, 0.67, 0.95])
    classes = assign_congestion_class(scores, low_threshold=0.33, high_threshold=0.67)
    assert classes.iloc[0] == "LOW"
    assert classes.iloc[1] == "LOW"
    assert classes.iloc[2] == "MEDIUM"
    assert classes.iloc[3] == "MEDIUM"
    assert classes.iloc[4] == "MEDIUM"
    assert classes.iloc[5] == "HIGH"
    assert classes.iloc[6] == "HIGH"


# 6. Future-Target Correctness
def test_future_target_correctness(sample_timeseries_df: pd.DataFrame):
    target_df, _ = construct_future_targets(sample_timeseries_df, horizon_seconds=10, tolerance_seconds=2)
    assert not target_df.empty
    # Target timestamp must be strictly in the future compared to anchor timestamp
    t_anchor = pd.to_datetime(target_df["timestamp"])
    t_target = pd.to_datetime(target_df["target_timestamp"])
    assert (t_target > t_anchor).all()
    # Score must be bounded in [0.0, 1.0]
    assert (target_df["future_congestion_score"] >= 0.0).all()
    assert (target_df["future_congestion_score"] <= 1.0).all()


# 7. Missing-Value Handling
def test_missing_value_handling():
    data = {
        "timestamp": ["2026-09-12 12:00:00", "2026-09-12 12:00:01", "2026-09-12 12:00:02"],
        "device_id": ["h1", "h1", "h1"],
        "throughput_mbps": [10.0, np.nan, 30.0],
        "packet_loss_percent": [np.nan, np.nan, np.nan],  # 100% missing
    }
    df = pd.DataFrame(data)
    clean_df, stats = handle_missing_features(df, ["throughput_mbps", "packet_loss_percent"])

    # Partial missing throughput should be median (20.0)
    assert clean_df.loc[1, "throughput_mbps"] == 20.0
    # 100% missing packet loss should be safe baseline 0.0
    assert (clean_df["packet_loss_percent"] == 0.0).all()
    assert stats["throughput_mbps"]["null_count"] == 1
    assert stats["packet_loss_percent"]["null_count"] == 3


# 8. Sequence Generation & Format
def test_sequence_generation(sample_timeseries_df: pd.DataFrame):
    target_df, _ = construct_future_targets(sample_timeseries_df, horizon_seconds=10, tolerance_seconds=2)
    seq_df, _ = generate_time_series_sequences(target_df, history_window_seconds=15)

    required_cols = [
        "sequence_id", "device_id", "sequence_start", "sequence_end",
        "prediction_timestamp", "history_steps", "future_congestion_score",
        "future_congestion_class",
    ]
    for col in required_cols:
        assert col in seq_df.columns, f"Missing required sequence column: {col}"
    assert seq_df["sequence_id"].is_monotonic_increasing


# 9. Chronological Train / Validation / Test Split
def test_chronological_split(sample_timeseries_df: pd.DataFrame):
    target_df, _ = construct_future_targets(sample_timeseries_df, horizon_seconds=10, tolerance_seconds=2)
    seq_df, _ = generate_time_series_sequences(target_df)

    train_df, val_df, test_df = chronological_split(seq_df, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    assert len(train_df) + len(val_df) + len(test_df) == len(seq_df)
    assert len(train_df) > 0
    assert len(val_df) > 0
    assert len(test_df) > 0

    # Test chronological boundaries
    is_valid, issues = validate_splits(train_df, val_df, test_df, time_col="sequence_end")
    assert is_valid, f"Chronological split failed validation: {issues}"


# 10. Data Leakage Prevention
def test_data_leakage_prevention(sample_timeseries_df: pd.DataFrame):
    target_df, _ = construct_future_targets(sample_timeseries_df, horizon_seconds=10, tolerance_seconds=2)
    seq_df, _ = generate_time_series_sequences(target_df, history_window_seconds=30)

    # For each sequence:
    # 1. sequence_start <= sequence_end
    # 2. sequence_end < prediction_timestamp
    start_ts = pd.to_datetime(seq_df["sequence_start"])
    end_ts = pd.to_datetime(seq_df["sequence_end"])
    pred_ts = pd.to_datetime(seq_df["prediction_timestamp"])

    assert (start_ts <= end_ts).all(), "Sequence start exceeds sequence end"
    assert (end_ts < pred_ts).all(), "Future data leakage: sequence_end is not strictly before prediction_timestamp"


# 11. Empty & Small Dataset Handling
def test_empty_and_small_dataset_handling():
    empty_df = pd.DataFrame(columns=["timestamp", "device_id", "throughput_mbps"])
    target_df, stats = construct_future_targets(empty_df)
    assert target_df.empty
    assert stats["matched_targets"] == 0

    # Single-record dataset
    single_df = pd.DataFrame([{
        "timestamp": "2026-09-12 12:00:00",
        "device_id": "h1",
        "throughput_mbps": 10.0,
    }])
    single_target, s_stats = construct_future_targets(single_df)
    # Cannot have future target with only 1 point
    assert single_target.empty
    assert s_stats["unmatched_targets"] == 1


# 12. End-to-End Pipeline Execution
def test_end_to_end_pipeline_execution(tmp_path: Path):
    if not DEFAULT_INPUT_PATH.exists():
        pytest.skip("Phase 7 dataset not found.")

    out_dir = tmp_path / "congestion_out"
    results = run_congestion_dataset_pipeline(
        input_path=DEFAULT_INPUT_PATH,
        output_dir=out_dir,
        history_window_seconds=30,
        prediction_horizon_seconds=10,
        generate_plot=True,
    )

    assert results["dataset_path"].exists()
    assert results["train_path"].exists()
    assert results["val_path"].exists()
    assert results["test_path"].exists()
    assert results["stats_path"].exists()
    assert results["label_config_path"].exists()
    if results["vis_path"]:
        assert results["vis_path"].exists()
