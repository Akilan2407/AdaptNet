"""Baseline Evaluation and Benchmarking Pipeline for Congestion Forecasting.

Evaluates non-ML baselines (Persistence, Moving Average, Linear Trend) on the
Phase 9 test dataset, comparing results directly against the Phase 10 GRU model.

Generates:
- persistence_predictions.csv
- moving_average_predictions.csv
- linear_trend_predictions.csv
- baseline_evaluation.json
- model_comparison.csv
- baseline_summary.json
- mae_comparison.png
- rmse_comparison.png
- baseline_predictions.png
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    load_gru_evaluation,
)
from ml.baseline.config import (
    BASELINE_EVALUATION_PATH,
    BASELINE_PREDICTIONS_PLOT,
    BASELINE_SUMMARY_PATH,
    CONGESTION_CLASSES,
    DEFAULT_BASELINE_OUTPUT_DIR,
    DEFAULT_MODEL_EVAL_PATH,
    DEFAULT_NETWORK_FEATURES_PATH,
    DEFAULT_TEST_DATASET_PATH,
    DEFAULT_TEST_PREDICTIONS_PATH,
    HIGH_THRESHOLD,
    LINEAR_TREND_PREDICTIONS_PATH,
    LOW_THRESHOLD,
    MAE_COMPARISON_PLOT,
    MODEL_COMPARISON_PATH,
    MOVING_AVERAGE_PREDICTIONS_PATH,
    MOVING_AVERAGE_WINDOW,
    PERSISTENCE_PREDICTIONS_PATH,
    RMSE_COMPARISON_PLOT,
)
from ml.baseline.visualization import (
    plot_baseline_predictions,
    plot_mae_comparison,
    plot_rmse_comparison,
)
from ml.congestion.congestion_labeling import calculate_congestion_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml.baseline.evaluate")


def calculate_regression_metrics(
    y_true: Sequence[float],
    y_pred: Sequence[float],
) -> Dict[str, float]:
    """Calculate MAE, MSE, RMSE, R2, and Max Error."""
    y_t = np.asarray(y_true, dtype=np.float64).flatten()
    y_p = np.asarray(y_pred, dtype=np.float64).flatten()

    if len(y_t) == 0:
        return {"mae": 0.0, "mse": 0.0, "rmse": 0.0, "r2": 0.0, "max_error": 0.0}

    mae = float(mean_absolute_error(y_t, y_p))
    mse = float(mean_squared_error(y_t, y_p))
    rmse = float(np.sqrt(mse))
    max_err = float(np.max(np.abs(y_t - y_p)))

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
    y_true: Sequence[str],
    y_pred: Sequence[str],
    classes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Calculate Accuracy, Precision, Recall, F1, and Confusion Matrix."""
    if classes is None:
        classes = CONGESTION_CLASSES

    y_t = np.asarray(y_true, dtype=str).flatten()
    y_p = np.asarray(y_pred, dtype=str).flatten()

    if len(y_t) == 0:
        return {
            "accuracy": 0.0,
            "precision_macro": 0.0,
            "recall_macro": 0.0,
            "f1": 0.0,
            "f1_macro": 0.0,
            "confusion_matrix": [[0 for _ in classes] for _ in classes],
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
        "f1": round(f1, 4),
        "f1_macro": round(f1, 4),
        "confusion_matrix": cm.tolist(),
    }


def extract_history_for_sample(
    sample_row: pd.Series,
    telemetry_df: Optional[pd.DataFrame] = None,
) -> Tuple[List[float], List[pd.Timestamp]]:
    """Extract chronological historical observations strictly prior to prediction time.

    Enforces zero data leakage:
      t_obs <= sequence_end < prediction_timestamp

    Args:
        sample_row: Single row from test_dataset.csv.
        telemetry_df: Optional full telemetry DataFrame with raw observations.

    Returns:
        Tuple of (historical_scores, historical_timestamps).

    Raises:
        ValueError: If any observation timestamp >= prediction_timestamp.
    """
    pred_time = pd.to_datetime(sample_row["prediction_timestamp"])
    seq_end = pd.to_datetime(sample_row.get("sequence_end", sample_row["prediction_timestamp"]))
    dev_id = sample_row.get("device_id")

    scores: List[float] = []
    timestamps: List[pd.Timestamp] = []

    if telemetry_df is not None and not telemetry_df.empty and dev_id in telemetry_df["device_id"].values:
        dev_telemetry = telemetry_df[telemetry_df["device_id"] == dev_id].copy()
        dev_telemetry["ts"] = pd.to_datetime(dev_telemetry["timestamp"])
        dev_telemetry = dev_telemetry.sort_values(by="ts")

        # Select observations strictly <= sequence_end
        mask = dev_telemetry["ts"] <= seq_end
        hist_rows = dev_telemetry[mask]

        if not hist_rows.empty:
            for _, r in hist_rows.iterrows():
                obs_ts = r["ts"]
                # STRICT TEMPORAL LEAKAGE CHECK
                if obs_ts >= pred_time:
                    raise ValueError(
                        f"Temporal leakage detected: observation time ({obs_ts}) "
                        f"is >= prediction target time ({pred_time})"
                    )
                # Compute instantaneous score
                row_score = float(calculate_congestion_score(pd.DataFrame([r])).iloc[0])
                scores.append(row_score)
                timestamps.append(obs_ts)

    # Fallback to anchor observation if telemetry_df did not produce history
    if not scores:
        anchor_score = float(calculate_congestion_score(pd.DataFrame([sample_row])).iloc[0])
        anchor_ts = seq_end
        if anchor_ts >= pred_time:
            # If sequence_end equals prediction_timestamp, offset slightly to preserve valid ordering
            anchor_ts = pred_time - pd.Timedelta(seconds=1)
        scores.append(anchor_score)
        timestamps.append(anchor_ts)

    return scores, timestamps


def evaluate_all_baselines(
    test_path: Path = DEFAULT_TEST_DATASET_PATH,
    telemetry_path: Path = DEFAULT_NETWORK_FEATURES_PATH,
    model_eval_path: Path = DEFAULT_MODEL_EVAL_PATH,
    output_dir: Path = DEFAULT_BASELINE_OUTPUT_DIR,
    ma_window: int = MOVING_AVERAGE_WINDOW,
) -> Dict[str, Any]:
    """Run full baseline prediction, evaluation, comparison, and plotting workflow.

    Args:
        test_path: Path to test_dataset.csv.
        telemetry_path: Path to network_features.csv.
        model_eval_path: Path to Phase 10 model_evaluation.json.
        output_dir: Output directory for baseline artifacts.
        ma_window: Moving average window size.

    Returns:
        Dictionary of complete evaluation and comparison summary.
    """
    if not test_path.exists():
        raise FileNotFoundError(f"Test dataset not found at {test_path}")

    test_df = pd.read_csv(test_path)
    total_test_samples = len(test_df)

    if total_test_samples == 0:
        raise ValueError(f"Test dataset at {test_path} is empty.")

    # Load raw telemetry if available
    telemetry_df = None
    if telemetry_path.exists():
        try:
            telemetry_df = pd.read_csv(telemetry_path)
            logger.info("Loaded telemetry dataset (%d rows) from %s", len(telemetry_df), telemetry_path)
        except Exception as e:
            logger.warning("Could not load telemetry from %s: %s", telemetry_path, e)

    # Instantiate baseline predictors
    p_model = PersistenceBaseline()
    ma_model = MovingAverageBaseline(window_size=ma_window)
    lt_model = LinearTrendBaseline()

    y_true_score = test_df["future_congestion_score"].to_numpy(dtype=np.float64)
    y_true_class = test_df["future_congestion_class"].to_numpy(dtype=str)

    p_scores, p_classes = [], []
    ma_scores, ma_classes = [], []
    lt_scores, lt_classes = [], []

    valid_samples = 0
    discarded_samples = 0

    # Generate predictions row-by-row with strict leakage validation
    for i, row in test_df.iterrows():
        try:
            hist_scores, hist_ts = extract_history_for_sample(row, telemetry_df)
            future_ts = pd.to_datetime(row["prediction_timestamp"])

            # 1. Persistence
            res_p = p_model.predict(history=hist_scores)
            p_scores.append(res_p["predicted_congestion_score"])
            p_classes.append(res_p["predicted_congestion_class"])

            # 2. Moving Average
            res_ma = ma_model.predict(history=hist_scores)
            ma_scores.append(res_ma["predicted_congestion_score"])
            ma_classes.append(res_ma["predicted_congestion_class"])

            # 3. Linear Trend
            res_lt = lt_model.predict(
                history=hist_scores,
                timestamps=hist_ts,
                future_timestamp=future_ts,
            )
            lt_scores.append(res_lt["predicted_congestion_score"])
            lt_classes.append(res_lt["predicted_congestion_class"])

            valid_samples += 1
        except Exception as e:
            logger.error("Failed to generate prediction for test row %d: %s", i, e)
            discarded_samples += 1

    # Compute metrics for each baseline
    p_reg = calculate_regression_metrics(y_true_score, p_scores)
    p_cls = calculate_classification_metrics(y_true_class, p_classes)

    ma_reg = calculate_regression_metrics(y_true_score, ma_scores)
    ma_cls = calculate_classification_metrics(y_true_class, ma_classes)

    lt_reg = calculate_regression_metrics(y_true_score, lt_scores)
    lt_cls = calculate_classification_metrics(y_true_class, lt_classes)

    baseline_results = {
        "persistence": {
            "name": "Persistence",
            "regression": p_reg,
            "classification": p_cls,
            "mae": p_reg["mae"],
            "mse": p_reg["mse"],
            "rmse": p_reg["rmse"],
            "r2": p_reg["r2"],
            "accuracy": p_cls["accuracy"],
            "f1": p_cls["f1"],
        },
        "moving_average": {
            "name": "MovingAverage",
            "window_size": ma_window,
            "regression": ma_reg,
            "classification": ma_cls,
            "mae": ma_reg["mae"],
            "mse": ma_reg["mse"],
            "rmse": ma_reg["rmse"],
            "r2": ma_reg["r2"],
            "accuracy": ma_cls["accuracy"],
            "f1": ma_cls["f1"],
        },
        "linear_trend": {
            "name": "LinearTrend",
            "regression": lt_reg,
            "classification": lt_cls,
            "mae": lt_reg["mae"],
            "mse": lt_reg["mse"],
            "rmse": lt_reg["rmse"],
            "r2": lt_reg["r2"],
            "accuracy": lt_cls["accuracy"],
            "f1": lt_cls["f1"],
        },
    }

    # Save Prediction CSVs
    output_dir.mkdir(parents=True, exist_ok=True)

    def _export_pred_csv(scores, classes, filename):
        df = pd.DataFrame({
            "timestamp": test_df.get("prediction_timestamp", range(len(test_df))),
            "device_id": test_df.get("device_id", ["unknown"] * len(test_df)),
            "actual_congestion_score": [round(float(s), 4) for s in y_true_score],
            "predicted_congestion_score": [round(float(s), 4) for s in scores],
            "actual_congestion_class": y_true_class,
            "predicted_congestion_class": classes,
            "absolute_error": [round(float(abs(a - p)), 4) for a, p in zip(y_true_score, scores)],
        })
        p = output_dir / filename
        df.to_csv(p, index=False)
        logger.info("Saved prediction CSV to %s", p)
        return p

    _export_pred_csv(p_scores, p_classes, "persistence_predictions.csv")
    _export_pred_csv(ma_scores, ma_classes, "moving_average_predictions.csv")
    _export_pred_csv(lt_scores, lt_classes, "linear_trend_predictions.csv")

    # Save Baseline Evaluation JSON
    eval_json_p = output_dir / "baseline_evaluation.json"
    with open(eval_json_p, "w") as f:
        json.dump(baseline_results, f, indent=2)
    logger.info("Saved baseline evaluation JSON to %s", eval_json_p)

    # Load GRU evaluation for comparison
    gru_eval = load_gru_evaluation(model_eval_path)
    comparisons = compute_metric_comparisons(gru_eval, baseline_results)
    comparison_df = build_comparison_dataframe(gru_eval, baseline_results)

    # Export Model Comparison CSV
    comp_csv_p = export_model_comparison_csv(comparison_df, output_dir / "model_comparison.csv")

    # Generate Visualizations
    plot_mae_comparison(comparison_df, output_dir / "mae_comparison.png")
    plot_rmse_comparison(comparison_df, output_dir / "rmse_comparison.png")

    gru_preds = None
    if DEFAULT_TEST_PREDICTIONS_PATH.exists():
        try:
            gru_pred_df = pd.read_csv(DEFAULT_TEST_PREDICTIONS_PATH)
            if "predicted_score" in gru_pred_df.columns:
                gru_preds = gru_pred_df["predicted_score"].to_numpy(dtype=np.float64)
        except Exception as e:
            logger.warning("Could not read GRU predictions for plot: %s", e)

    plot_baseline_predictions(
        test_df=test_df,
        predictions_dict={
            "Persistence": p_scores,
            "MovingAverage": ma_scores,
            "LinearTrend": lt_scores,
        },
        gru_predictions=gru_preds,
        output_path=output_dir / "baseline_predictions.png",
    )

    # Save Baseline Summary JSON
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": 11,
        "total_test_samples": total_test_samples,
        "valid_samples": valid_samples,
        "discarded_samples": discarded_samples,
        "prediction_horizon_seconds": 30,
        "history_window_seconds": 30,
        "moving_average_window": ma_window,
        "baseline_predictions_count": {
            "persistence": len(p_scores),
            "moving_average": len(ma_scores),
            "linear_trend": len(lt_scores),
        },
        "metrics": baseline_results,
        "gru_comparison": comparisons,
    }

    summary_json_p = output_dir / "baseline_summary.json"
    with open(summary_json_p, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info("Saved baseline summary JSON to %s", summary_json_p)

    # Print Formatted Console Output matching Section 28
    gru_reg = gru_eval.get("regression_metrics", {})
    print("\n" + "=" * 40)
    print("PHASE 11 — BASELINE EVALUATION")
    print("=" * 40 + "\n")
    print(f"Test samples: {total_test_samples}\n")
    print(f"Prediction horizon: 30 seconds")
    print(f"History window: 30 seconds\n")
    print("Persistence:")
    print(f"    MAE:  {p_reg['mae']:.4f}")
    print(f"    RMSE: {p_reg['rmse']:.4f}")
    print(f"    R2:   {p_reg['r2']:.4f}\n")
    print("Moving Average:")
    print(f"    MAE:  {ma_reg['mae']:.4f}")
    print(f"    RMSE: {ma_reg['rmse']:.4f}")
    print(f"    R2:   {ma_reg['r2']:.4f}\n")
    print("Linear Trend:")
    print(f"    MAE:  {lt_reg['mae']:.4f}")
    print(f"    RMSE: {lt_reg['rmse']:.4f}")
    print(f"    R2:   {lt_reg['r2']:.4f}\n")
    print("GRU:")
    print(f"    MAE:  {float(gru_reg.get('mae', 0.0)):.4f}")
    print(f"    RMSE: {float(gru_reg.get('rmse', 0.0)):.4f}")
    print(f"    R2:   {float(gru_reg.get('r2', 0.0)):.4f}\n")
    print("Comparison files generated successfully.\n")
    print("Phase 11 Status: COMPLETED")
    print("=" * 40 + "\n")

    return summary


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Phase 11: Evaluate Non-ML Congestion Baselines.")
    parser.add_argument(
        "--test-path",
        type=Path,
        default=DEFAULT_TEST_DATASET_PATH,
        help="Path to test_dataset.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_BASELINE_OUTPUT_DIR,
        help="Directory to save baseline outputs",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=MOVING_AVERAGE_WINDOW,
        help=f"Moving average window size (default: {MOVING_AVERAGE_WINDOW})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate_all_baselines(
        test_path=args.test_path,
        output_dir=args.output_dir,
        ma_window=args.window,
    )
