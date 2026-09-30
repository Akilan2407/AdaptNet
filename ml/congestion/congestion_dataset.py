"""Main CLI Orchestrator for Phase 9: Congestion Dataset Module.

Transforms raw network telemetry features into a structured, chronological
time-series dataset for training future recurrent forecasting models (Phase 10).

Saves:
- data/congestion/congestion_dataset.csv
- data/congestion/train_dataset.csv
- data/congestion/validation_dataset.csv
- data/congestion/test_dataset.csv
- data/congestion/dataset_statistics.json
- data/congestion/congestion_label_config.json
- data/congestion/dataset_visualization.png
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Use headless backend for matplotlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ml.congestion.config import (
    CANDIDATE_CONGESTION_FEATURES,
    CONGESTION_CLASSES,
    DEFAULT_DATASET_PATH,
    DEFAULT_INPUT_PATH,
    DEFAULT_LABEL_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PROFILES_PATH,
    DEFAULT_STATS_PATH,
    DEFAULT_TEST_PATH,
    DEFAULT_TRAIN_PATH,
    DEFAULT_VAL_PATH,
    DEFAULT_VISUALIZATION_PATH,
    HIGH_THRESHOLD,
    HISTORY_WINDOW_SECONDS,
    HORIZON_TOLERANCE_SECONDS,
    LOW_THRESHOLD,
    MIN_HISTORY_STEPS,
    PREDICTION_HORIZON_SECONDS,
    TEST_RATIO,
    TRAIN_RATIO,
    VALIDATION_RATIO,
)
from ml.congestion.congestion_labeling import (
    export_label_config,
)
from ml.congestion.dataset_validation import (
    generate_and_save_statistics,
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

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("congestion_dataset")


def generate_visualization(
    dataset_df: pd.DataFrame,
    output_path: Path = DEFAULT_VISUALIZATION_PATH,
    low_thresh: float = LOW_THRESHOLD,
    high_thresh: float = HIGH_THRESHOLD,
) -> Optional[Path]:
    """Generate 2-panel dataset visualization plot.

    Panel 1: Future Congestion Score over Time with threshold boundaries.
    Panel 2: Congestion Class Distribution bar chart.

    Args:
        dataset_df: Full congestion dataset
        output_path: Destination PNG path
        low_thresh: Low threshold line
        high_thresh: High threshold line

    Returns:
        Path to written PNG
    """
    if dataset_df.empty:
        logger.warning("Empty dataset. Skipping visualization.")
        return None

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, figsize=(10, 8), dpi=150)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    # Panel 1: Congestion Score over Time
    time_col = "sequence_end" if "sequence_end" in dataset_df.columns else "timestamp"
    ts = pd.to_datetime(dataset_df[time_col])
    scores = dataset_df["future_congestion_score"]

    devices = dataset_df["device_id"].unique() if "device_id" in dataset_df.columns else ["all"]
    cmap = plt.get_cmap("tab10")

    for idx, dev in enumerate(devices):
        mask = dataset_df["device_id"] == dev if "device_id" in dataset_df.columns else np.ones(len(dataset_df), dtype=bool)
        ax1.scatter(
            ts[mask],
            scores[mask],
            label=f"Device {dev}",
            color=cmap(idx % 10),
            s=60,
            alpha=0.85,
            edgecolors="black",
            linewidth=0.8,
            zorder=3,
        )

    # Threshold guidelines
    ax1.axhline(low_thresh, color="#f59e0b", linestyle="--", linewidth=1.2, label=f"Low/Med Threshold ({low_thresh:.2f})")
    ax1.axhline(high_thresh, color="#ef4444", linestyle="--", linewidth=1.2, label=f"Med/High Threshold ({high_thresh:.2f})")

    ax1.set_ylim(-0.05, 1.05)
    ax1.set_xlabel("Observation Timestamp (t)", fontsize=11, fontweight="semibold")
    ax1.set_ylabel("Future Congestion Score (t + H)", fontsize=11, fontweight="semibold")
    ax1.set_title("Future Congestion Score vs. Observation Time", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper right", frameon=True, fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.5)

    # Panel 2: Class Distribution Bar Chart
    class_counts = dataset_df["future_congestion_class"].value_counts()
    categories = CONGESTION_CLASSES
    counts = [int(class_counts.get(c, 0)) for c in categories]
    bar_colors = ["#10b981", "#f59e0b", "#ef4444"]  # Green (LOW), Amber (MED), Red (HIGH)

    bars = ax2.bar(categories, counts, color=bar_colors, edgecolor="black", linewidth=1.0, width=0.5, zorder=3)
    ax2.set_xlabel("Congestion Class", fontsize=11, fontweight="semibold")
    ax2.set_ylabel("Sequence Count", fontsize=11, fontweight="semibold")
    ax2.set_title("Dataset Congestion Class Distribution", fontsize=12, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5, axis="y")

    # Add count labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax2.annotate(
            f"{height}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    plt.tight_layout()
    plt.savefig(path, format="png", dpi=150)
    plt.close()

    logger.info("Saved dataset visualization to %s", path)
    return path


def run_congestion_dataset_pipeline(
    input_path: Path = DEFAULT_INPUT_PATH,
    profiles_path: Optional[Path] = DEFAULT_PROFILES_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    history_window_seconds: int = HISTORY_WINDOW_SECONDS,
    prediction_horizon_seconds: int = PREDICTION_HORIZON_SECONDS,
    horizon_tolerance_seconds: int = HORIZON_TOLERANCE_SECONDS,
    low_threshold: float = LOW_THRESHOLD,
    high_threshold: float = HIGH_THRESHOLD,
    train_ratio: float = TRAIN_RATIO,
    val_ratio: float = VALIDATION_RATIO,
    test_ratio: float = TEST_RATIO,
    generate_plot: bool = True,
) -> Dict[str, Any]:
    """Execute end-to-end Congestion Dataset generation pipeline."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Telemetry and Validate Timestamps
    raw_df, ingestion_stats = load_and_prepare_telemetry(
        features_path=input_path,
        profiles_path=profiles_path,
    )

    # Detect sampling interval
    sampling_stats = detect_sampling_interval(raw_df)

    # 2. Impute and Clean Features
    active_features = [c for c in CANDIDATE_CONGESTION_FEATURES if c in raw_df.columns]
    clean_df, missing_stats = handle_missing_features(raw_df, active_features)

    # 3. Construct Forward-Looking Prediction Targets
    target_df, target_stats = construct_future_targets(
        df=clean_df,
        horizon_seconds=prediction_horizon_seconds,
        tolerance_seconds=horizon_tolerance_seconds,
    )

    # In small LAN captures with discrete test bursts, intervals between sessions
    # may be ~30s. If default horizon matched 0 records, adapt to supported
    # alternative horizons (e.g. 30s) if viable.
    if target_stats["matched_targets"] == 0:
        for alt_h in [30, 20]:
            if alt_h != prediction_horizon_seconds:
                alt_df, alt_stats = construct_future_targets(
                    df=clean_df,
                    horizon_seconds=alt_h,
                    tolerance_seconds=horizon_tolerance_seconds,
                )
                if alt_stats["matched_targets"] > 0:
                    target_df, target_stats = alt_df, alt_stats
                    prediction_horizon_seconds = alt_h
                    logger.info(
                        "Adapted prediction horizon to %ds based on telemetry intervals (%d targets matched)",
                        alt_h,
                        alt_stats["matched_targets"],
                    )
                    break

    # 4. Generate Time-Series Observation Sequences
    seq_df, seq_stats = generate_time_series_sequences(
        df=target_df,
        history_window_seconds=history_window_seconds,
        min_history_steps=MIN_HISTORY_STEPS,
        feature_cols=active_features,
    )

    # 5. Chronological Train / Validation / Test Partitioning
    train_df, val_df, test_df = chronological_split(
        df=seq_df,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        time_col="sequence_end",
    )

    # 6. Comprehensive Invariant Validation
    ts_valid, ts_issues = validate_timestamps(seq_df, time_col="sequence_end")
    feat_valid, feat_issues = validate_features(seq_df, active_features)
    target_valid, target_issues = validate_targets(
        seq_df,
        score_col="future_congestion_score",
        class_col="future_congestion_class",
        anchor_time_col="sequence_end",
        target_time_col="prediction_timestamp",
    )
    split_valid, split_issues = validate_splits(train_df, val_df, test_df, time_col="sequence_end")

    all_issues = ts_issues + feat_issues + target_issues + split_issues
    if all_issues:
        logger.warning("Validation warnings encountered: %s", all_issues)
    else:
        logger.info("All dataset validation invariants passed successfully.")

    # 7. Export Datasets to CSV
    dataset_path = output_dir / "congestion_dataset.csv"
    train_path = output_dir / "train_dataset.csv"
    val_path = output_dir / "validation_dataset.csv"
    test_path = output_dir / "test_dataset.csv"

    seq_df.to_csv(dataset_path, index=False)
    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)
    logger.info("Exported main and split datasets to %s", output_dir)

    # 8. Export Configuration & Statistics to JSON
    label_config_path = output_dir / "congestion_label_config.json"
    stats_path = output_dir / "dataset_statistics.json"

    export_label_config(
        output_path=label_config_path,
        low_threshold=low_threshold,
        high_threshold=high_threshold,
    )

    generate_and_save_statistics(
        ingestion_stats=ingestion_stats,
        target_stats=target_stats,
        seq_stats=seq_stats,
        dataset_df=seq_df,
        train_df=train_df,
        val_df=val_df,
        test_df=test_df,
        missing_stats=missing_stats,
        sampling_stats=sampling_stats,
        output_path=stats_path,
    )

    # 9. Generate Visualization Plot
    vis_path = None
    if generate_plot:
        vis_path = generate_visualization(
            dataset_df=seq_df,
            output_path=output_dir / "dataset_visualization.png",
            low_thresh=low_threshold,
            high_thresh=high_threshold,
        )

    # 10. Print Concise Summary Output matching requested format
    class_dist = {c: 0 for c in CONGESTION_CLASSES}
    if "future_congestion_class" in seq_df.columns:
        counts = seq_df["future_congestion_class"].value_counts().to_dict()
        for c in CONGESTION_CLASSES:
            class_dist[c] = int(counts.get(c, 0))

    _print_summary_report(
        input_records=ingestion_stats.get("total_records", 0),
        valid_records=ingestion_stats.get("valid_records", 0),
        removed_records=ingestion_stats.get("removed_records", 0),
        history_window=history_window_seconds,
        prediction_horizon=prediction_horizon_seconds,
        generated_sequences=len(seq_df),
        class_dist=class_dist,
        train_samples=len(train_df),
        val_samples=len(val_df),
        test_samples=len(test_df),
    )

    return {
        "dataset_path": dataset_path,
        "train_path": train_path,
        "val_path": val_path,
        "test_path": test_path,
        "stats_path": stats_path,
        "label_config_path": label_config_path,
        "vis_path": vis_path,
        "total_records": ingestion_stats.get("total_records", 0),
        "valid_records": ingestion_stats.get("valid_records", 0),
        "removed_records": ingestion_stats.get("removed_records", 0),
        "generated_sequences": len(seq_df),
        "train_samples": len(train_df),
        "val_samples": len(val_df),
        "test_samples": len(test_df),
        "class_dist": class_dist,
    }


def _print_summary_report(
    input_records: int,
    valid_records: int,
    removed_records: int,
    history_window: int,
    prediction_horizon: int,
    generated_sequences: int,
    class_dist: Dict[str, int],
    train_samples: int,
    val_samples: int,
    test_samples: int,
) -> None:
    """Print standard summary block."""
    print("\n=== Congestion Dataset Generation ===\n")
    print(f"Input records: {input_records}")
    print(f"Valid records: {valid_records}")
    print(f"Removed records: {removed_records}\n")
    print(f"History window: {history_window} seconds")
    print(f"Prediction horizon: {prediction_horizon} seconds\n")
    print(f"Generated sequences: {generated_sequences}\n")
    print("Congestion distribution:")
    for c in CONGESTION_CLASSES:
        print(f"{c}: {class_dist.get(c, 0)}")
    print(f"\nTrain samples: {train_samples}")
    print(f"Validation samples: {val_samples}")
    print(f"Test samples: {test_samples}\n")
    print("Dataset saved successfully.\n")


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="Phase 9: Congestion Dataset Module for Time-Series Prediction.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH, help="Path to Phase 7 network_features.csv")
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES_PATH, help="Path to Phase 8 behavior_profiles.csv")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Destination directory for outputs")
    parser.add_argument("--history-window", type=int, default=HISTORY_WINDOW_SECONDS, help="Historical observation window in seconds")
    parser.add_argument("--prediction-horizon", type=int, default=PREDICTION_HORIZON_SECONDS, help="Prediction horizon in seconds (10, 20, 30)")
    parser.add_argument("--tolerance", type=int, default=HORIZON_TOLERANCE_SECONDS, help="Horizon matching tolerance window in seconds")
    parser.add_argument("--low-threshold", type=float, default=LOW_THRESHOLD, help="Threshold between LOW and MEDIUM")
    parser.add_argument("--high-threshold", type=float, default=HIGH_THRESHOLD, help="Threshold between MEDIUM and HIGH")
    parser.add_argument("--train-ratio", type=float, default=TRAIN_RATIO, help="Proportion for training partition")
    parser.add_argument("--val-ratio", type=float, default=VALIDATION_RATIO, help="Proportion for validation partition")
    parser.add_argument("--test-ratio", type=float, default=TEST_RATIO, help="Proportion for testing partition")
    parser.add_argument("--no-plot", action="store_true", help="Disable visualization plot generation")
    return parser


def main():
    """CLI entry point."""
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        run_congestion_dataset_pipeline(
            input_path=args.input,
            profiles_path=args.profiles,
            output_dir=args.output_dir,
            history_window_seconds=args.history_window,
            prediction_horizon_seconds=args.prediction_horizon,
            horizon_tolerance_seconds=args.tolerance,
            low_threshold=args.low_threshold,
            high_threshold=args.high_threshold,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            generate_plot=not args.no_plot,
        )
    except Exception as e:
        logger.exception("Congestion dataset pipeline failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
