"""Model Evaluation and Benchmark Pipeline for Congestion Forecasting.

Evaluates trained GRU model on test_dataset.csv, comparing against
naive persistence and mean baselines. Exports:
- model_evaluation.json
- baseline_evaluation.json
- test_predictions.csv
- actual_vs_predicted.png
- prediction_error.png
- congestion_confusion_matrix.png
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import joblib
import numpy as np
import pandas as pd
from tensorflow import keras

from ml.congestion.config import (
    CONGESTION_CLASSES,
    DEFAULT_ACTUAL_VS_PRED_PLOT,
    DEFAULT_BASELINE_EVAL_FILE,
    DEFAULT_CONFUSION_MATRIX_PLOT,
    DEFAULT_ERROR_PLOT,
    DEFAULT_EVALUATION_FILE,
    DEFAULT_METADATA_FILE,
    DEFAULT_MODEL_FILE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PREDICTIONS_FILE,
    DEFAULT_SCALER_FILE,
    DEFAULT_TIMESTEPS,
)
from ml.congestion.metrics import (
    calculate_classification_metrics,
    calculate_regression_metrics,
    evaluate_naive_baseline,
    score_to_class,
)
from ml.congestion.preprocessing import load_phase9_datasets, reshape_to_sequences
from ml.congestion.visualization import (
    plot_actual_vs_predicted,
    plot_confusion_matrix,
    plot_prediction_error,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml.congestion.evaluate")


def evaluate_congestion_model(
    data_dir: Path = DEFAULT_OUTPUT_DIR,
    model_path: Path = DEFAULT_MODEL_FILE,
    scaler_path: Path = DEFAULT_SCALER_FILE,
    metadata_path: Path = DEFAULT_METADATA_FILE,
    eval_output: Path = DEFAULT_EVALUATION_FILE,
    baseline_output: Path = DEFAULT_BASELINE_EVAL_FILE,
    predictions_output: Path = DEFAULT_PREDICTIONS_FILE,
    actual_pred_plot: Path = DEFAULT_ACTUAL_VS_PRED_PLOT,
    error_plot: Path = DEFAULT_ERROR_PLOT,
    cm_plot: Path = DEFAULT_CONFUSION_MATRIX_PLOT,
) -> Dict[str, Any]:
    """Evaluate trained GRU model against test set and naive baselines.

    Args:
        data_dir: Directory with Phase 9 CSVs.
        model_path: Path to trained .keras model.
        scaler_path: Path to fitted .pkl scaler.
        metadata_path: Path to model_metadata.json.
        eval_output: Path to write model_evaluation.json.
        baseline_output: Path to write baseline_evaluation.json.
        predictions_output: Path to write test_predictions.csv.
        actual_pred_plot: Path for actual_vs_predicted.png.
        error_plot: Path for prediction_error.png.
        cm_plot: Path for congestion_confusion_matrix.png.

    Returns:
        Dictionary of evaluation results.
    """
    logger.info("Loading test dataset and trained artifacts...")
    train_df, val_df, test_df = load_phase9_datasets(data_dir)

    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found at {model_path}. Train the model first.")
    if not scaler_path.exists():
        raise FileNotFoundError(f"Scaler file not found at {scaler_path}. Train the model first.")

    model = keras.models.load_model(str(model_path))
    scaler = joblib.load(str(scaler_path))

    # Read feature columns and timesteps from metadata if available
    feature_cols = None
    timesteps = DEFAULT_TIMESTEPS
    if metadata_path.exists():
        with open(metadata_path, "r") as f:
            meta = json.load(f)
            feature_cols = meta.get("feature_columns")
            timesteps = meta.get("timesteps", DEFAULT_TIMESTEPS)

    if feature_cols is None:
        if hasattr(scaler, "feature_names_in_"):
            feature_cols = list(scaler.feature_names_in_)
        else:
            raise ValueError("Could not determine feature columns for scaling.")

    # 1. Transform test features
    test_features = test_df[feature_cols].copy().fillna(0.0).to_numpy(dtype=np.float32)
    scaled_test = scaler.transform(test_features)
    X_test = reshape_to_sequences(scaled_test, feature_cols=feature_cols, timesteps=timesteps)

    y_test_true = test_df["future_congestion_score"].to_numpy(dtype=np.float32)
    y_test_class_true = test_df["future_congestion_class"].to_numpy(dtype=str)

    # 2. Run Inference
    logger.info("Predicting on %d test samples...", len(X_test))
    raw_predictions = model.predict(X_test, verbose=0)
    y_pred_score = np.clip(raw_predictions.flatten(), 0.0, 1.0).astype(np.float64)
    y_pred_class = score_to_class(y_pred_score)

    # 3. Compute Metrics
    reg_metrics = calculate_regression_metrics(y_test_true, y_pred_score)
    cls_metrics = calculate_classification_metrics(y_test_class_true, y_pred_class)
    baseline_eval = evaluate_naive_baseline(train_df, test_df)

    persistence_metrics = baseline_eval["persistence_baseline"]["regression"]
    mean_metrics = baseline_eval["mean_baseline"]["regression"]

    # 4. Generate Diagnostic Plots
    plot_actual_vs_predicted(y_test_true, y_pred_score, y_test_class_true, actual_pred_plot)
    plot_prediction_error(y_test_true, y_pred_score, error_plot)
    plot_confusion_matrix(cls_metrics["confusion_matrix"], classes=CONGESTION_CLASSES, output_path=cm_plot)

    # 5. Export Predictions CSV
    pred_df = pd.DataFrame({
        "sequence_id": test_df.get("sequence_id", range(len(test_df))),
        "device_id": test_df.get("device_id", ["unknown"] * len(test_df)),
        "prediction_timestamp": test_df.get("prediction_timestamp", ["N/A"] * len(test_df)),
        "actual_score": [round(float(s), 4) for s in y_test_true],
        "predicted_score": [round(float(s), 4) for s in y_pred_score],
        "actual_class": y_test_class_true,
        "predicted_class": y_pred_class,
        "absolute_error": [round(float(abs(a - p)), 4) for a, p in zip(y_test_true, y_pred_score)],
    })
    predictions_output.parent.mkdir(parents=True, exist_ok=True)
    pred_df.to_csv(predictions_output, index=False)
    logger.info("Saved test predictions table to %s", predictions_output)

    # 6. Save JSON Summaries
    model_eval_summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": 10,
        "model_name": model.name,
        "test_sample_count": len(X_test),
        "regression_metrics": reg_metrics,
        "classification_metrics": cls_metrics,
        "comparison_vs_persistence": {
            "gru_mae": reg_metrics["mae"],
            "persistence_mae": persistence_metrics["mae"],
            "mae_delta": round(reg_metrics["mae"] - persistence_metrics["mae"], 4),
            "gru_mse": reg_metrics["mse"],
            "persistence_mse": persistence_metrics["mse"],
            "gru_better_than_persistence": bool(reg_metrics["mae"] <= persistence_metrics["mae"]),
        },
        "comparison_vs_mean_baseline": {
            "gru_mae": reg_metrics["mae"],
            "mean_mae": mean_metrics["mae"],
            "mae_delta": round(reg_metrics["mae"] - mean_metrics["mae"], 4),
            "gru_better_than_mean": bool(reg_metrics["mae"] <= mean_metrics["mae"]),
        },
    }

    eval_output.parent.mkdir(parents=True, exist_ok=True)
    with open(eval_output, "w") as f:
        json.dump(model_eval_summary, f, indent=2)
    logger.info("Saved model evaluation summary to %s", eval_output)

    baseline_output.parent.mkdir(parents=True, exist_ok=True)
    with open(baseline_output, "w") as f:
        json.dump(baseline_eval, f, indent=2)
    logger.info("Saved baseline evaluation summary to %s", baseline_output)

    # 7. Print Comparative Evaluation Table
    print("\n" + "=" * 70)
    print("           PHASE 10: CONGESTION MODEL EVALUATION REPORT")
    print("=" * 70)
    print(f" Test Set Size:          {len(X_test)} samples")
    print("-" * 70)
    print(f" {'Metric':<25} | {'GRU Model':<12} | {'Persistence':<12} | {'Mean Baseline':<12}")
    print("-" * 70)
    print(f" {'Mean Absolute Error (MAE)':<25} | {reg_metrics['mae']:<12.4f} | {persistence_metrics['mae']:<12.4f} | {mean_metrics['mae']:<12.4f}")
    print(f" {'Mean Squared Error (MSE)':<25}  | {reg_metrics['mse']:<12.4f} | {persistence_metrics['mse']:<12.4f} | {mean_metrics['mse']:<12.4f}")
    print(f" {'Root Mean Sq Error (RMSE)':<25}| {reg_metrics['rmse']:<12.4f} | {persistence_metrics['rmse']:<12.4f} | {mean_metrics['rmse']:<12.4f}")
    print(f" {'R-Squared (R²)':<25}           | {reg_metrics['r2']:<12.4f} | {persistence_metrics['r2']:<12.4f} | {mean_metrics['r2']:<12.4f}")
    print(f" {'Max Absolute Error':<25}     | {reg_metrics['max_error']:<12.4f} | {persistence_metrics['max_error']:<12.4f} | {mean_metrics['max_error']:<12.4f}")
    print("-" * 70)
    print(" Discrete Classification Performance (LOW / MEDIUM / HIGH):")
    print(f"   Accuracy:        {cls_metrics['accuracy'] * 100:.2f}%")
    print(f"   Precision Macro: {cls_metrics['precision_macro']:.4f}")
    print(f"   Recall Macro:    {cls_metrics['recall_macro']:.4f}")
    print(f"   F1 Macro:        {cls_metrics['f1_macro']:.4f}")
    print(f"   Confusion Matrix: {cls_metrics['confusion_matrix']}")
    print("-" * 70)
    print(" Artifacts Generated:")
    print(f"   Predictions:     {predictions_output}")
    print(f"   Model Eval JSON: {eval_output}")
    print(f"   Base Eval JSON:  {baseline_output}")
    print(f"   Plots:           {actual_pred_plot.name}, {error_plot.name}, {cm_plot.name}")
    print("=" * 70 + "\n")

    return model_eval_summary


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for evaluation."""
    parser = argparse.ArgumentParser(
        description="Phase 10: Evaluate Congestion Prediction Model."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory containing datasets (default: data/congestion)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    evaluate_congestion_model(data_dir=args.data_dir)
