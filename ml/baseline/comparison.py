"""Factual Model Comparison Pipeline for Congestion Forecasting.

Compares Phase 10 GRU model against non-ML baselines (Persistence,
Moving Average, Linear Trend) based strictly on calculated metrics.

Important Constraint:
No subjective classifications ('best', 'worst', 'winner', 'rank').
Only numerical differences and mathematically valid percentage changes.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from ml.baseline.config import (
    DEFAULT_MODEL_EVAL_PATH,
    MODEL_COMPARISON_PATH,
)

logger = logging.getLogger("ml.baseline.comparison")


def load_gru_evaluation(
    eval_path: Union[str, Path] = DEFAULT_MODEL_EVAL_PATH,
) -> Dict[str, Any]:
    """Load Phase 10 GRU evaluation results from JSON.

    Args:
        eval_path: Path to model_evaluation.json.

    Returns:
        Dictionary of GRU evaluation results.

    Raises:
        FileNotFoundError: If evaluation file does not exist.
    """
    p = Path(eval_path)
    if not p.exists():
        logger.error("GRU evaluation file not found at %s", p)
        raise FileNotFoundError(f"GRU evaluation file not found at {p}")

    with open(p, "r") as f:
        data = json.load(f)

    logger.info("Loaded Phase 10 GRU evaluation metrics from %s", p)
    return data


def compute_metric_comparisons(
    gru_metrics: Dict[str, Any],
    baseline_metrics: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute numerical differences and percentage improvements for each baseline.

    Formulas:
      - Error Difference = GRU_error - Baseline_error
      - Percentage Error Reduction = ((Baseline_error - GRU_error) / Baseline_error) * 100
        (Reported negative if GRU has higher error, or 'N/A' if Baseline_error == 0)
      - R2 Difference = GRU_r2 - Baseline_r2
      - Accuracy Difference = GRU_accuracy - Baseline_accuracy

    Args:
        gru_metrics: Dictionary containing GRU regression and classification metrics.
        baseline_metrics: Dictionary mapping baseline names to their metrics.

    Returns:
        Structured dictionary of factual comparative statistics.
    """
    gru_reg = gru_metrics.get("regression_metrics", {})
    gru_cls = gru_metrics.get("classification_metrics", {})

    gru_mae = float(gru_reg.get("mae", 0.0))
    gru_mse = float(gru_reg.get("mse", 0.0))
    gru_rmse = float(gru_reg.get("rmse", 0.0))
    gru_r2 = float(gru_reg.get("r2", 0.0))
    gru_acc = float(gru_cls.get("accuracy", 0.0))
    gru_f1 = float(gru_cls.get("f1_macro", 0.0))

    comparisons: Dict[str, Any] = {}

    for name, b_data in baseline_metrics.items():
        b_reg = b_data.get("regression", b_data)
        b_cls = b_data.get("classification", b_data)

        b_mae = float(b_reg.get("mae", 0.0))
        b_mse = float(b_reg.get("mse", 0.0))
        b_rmse = float(b_reg.get("rmse", 0.0))
        b_r2 = float(b_reg.get("r2", 0.0))
        b_acc = float(b_cls.get("accuracy", 0.0))
        b_f1 = float(b_cls.get("f1_macro", 0.0))

        # Absolute difference: GRU - Baseline
        delta_mae = round(gru_mae - b_mae, 4)
        delta_mse = round(gru_mse - b_mse, 4)
        delta_rmse = round(gru_rmse - b_rmse, 4)
        delta_r2 = round(gru_r2 - b_r2, 4)
        delta_acc = round(gru_acc - b_acc, 4)
        delta_f1 = round(gru_f1 - b_f1, 4)

        # Percentage improvement in MAE: ((Baseline - GRU) / Baseline) * 100
        if b_mae > 1e-6:
            pct_improvement_mae = round(((b_mae - gru_mae) / b_mae) * 100.0, 2)
        else:
            pct_improvement_mae = None  # Undefined when baseline error is 0.0

        if b_rmse > 1e-6:
            pct_improvement_rmse = round(((b_rmse - gru_rmse) / b_rmse) * 100.0, 2)
        else:
            pct_improvement_rmse = None

        comparisons[name] = {
            "delta_mae_gru_minus_baseline": delta_mae,
            "delta_mse_gru_minus_baseline": delta_mse,
            "delta_rmse_gru_minus_baseline": delta_rmse,
            "delta_r2_gru_minus_baseline": delta_r2,
            "delta_accuracy_gru_minus_baseline": delta_acc,
            "delta_f1_gru_minus_baseline": delta_f1,
            "pct_mae_improvement_over_baseline": pct_improvement_mae,
            "pct_rmse_improvement_over_baseline": pct_improvement_rmse,
            "baseline_metrics": {
                "mae": b_mae,
                "mse": b_mse,
                "rmse": b_rmse,
                "r2": b_r2,
                "accuracy": b_acc,
                "f1": b_f1,
            },
        }

    return comparisons


def build_comparison_dataframe(
    gru_metrics: Dict[str, Any],
    baseline_metrics: Dict[str, Dict[str, Any]],
) -> pd.DataFrame:
    """Build standardized tabular comparison DataFrame for export to CSV.

    Columns: model,mae,mse,rmse,r2,accuracy,f1

    Args:
        gru_metrics: Dict with GRU performance results.
        baseline_metrics: Dict with baseline performance results.

    Returns:
        pd.DataFrame containing comparison rows.
    """
    rows = []

    # GRU Row
    gru_reg = gru_metrics.get("regression_metrics", {})
    gru_cls = gru_metrics.get("classification_metrics", {})
    rows.append({
        "model": "GRU",
        "mae": float(gru_reg.get("mae", 0.0)),
        "mse": float(gru_reg.get("mse", 0.0)),
        "rmse": float(gru_reg.get("rmse", 0.0)),
        "r2": float(gru_reg.get("r2", 0.0)),
        "accuracy": float(gru_cls.get("accuracy", 0.0)),
        "f1": float(gru_cls.get("f1_macro", 0.0)),
    })

    # Baseline Rows in deterministic order
    baseline_order = [
        (["persistence", "Persistence"], "Persistence"),
        (["moving_average", "MovingAverage", "movingaverage"], "MovingAverage"),
        (["linear_trend", "LinearTrend", "lineartrend"], "LinearTrend"),
    ]

    for possible_keys, display_name in baseline_order:
        b_data = {}
        for k in possible_keys:
            if k in baseline_metrics:
                b_data = baseline_metrics[k]
                break
        b_reg = b_data.get("regression", b_data)
        b_cls = b_data.get("classification", b_data)
        rows.append({
            "model": display_name,
            "mae": float(b_reg.get("mae", 0.0)),
            "mse": float(b_reg.get("mse", 0.0)),
            "rmse": float(b_reg.get("rmse", 0.0)),
            "r2": float(b_reg.get("r2", 0.0)),
            "accuracy": float(b_cls.get("accuracy", 0.0)),
            "f1": float(b_cls.get("f1_macro", b_cls.get("f1", 0.0))),
        })

    df = pd.DataFrame(rows)
    return df


def export_model_comparison_csv(
    comparison_df: pd.DataFrame,
    output_path: Union[str, Path] = MODEL_COMPARISON_PATH,
) -> Path:
    """Export comparison DataFrame to CSV file."""
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    comparison_df.to_csv(out_p, index=False)
    logger.info("Saved model comparison CSV to %s", out_p)
    return out_p
