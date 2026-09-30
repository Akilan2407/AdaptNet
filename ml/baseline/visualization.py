"""Visualization Module for Baseline Models and GRU Comparison.

Generates 3 diagnostic comparison plots:
1. mae_comparison.png: Bar chart comparing MAE across GRU and baselines.
2. rmse_comparison.png: Bar chart comparing RMSE across GRU and baselines.
3. baseline_predictions.png: Chronological trajectory comparing actual congestion
   vs Persistence, Moving Average, Linear Trend, and GRU predictions.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ml.baseline.config import (
    BASELINE_PREDICTIONS_PLOT,
    MAE_COMPARISON_PLOT,
    RMSE_COMPARISON_PLOT,
)

logger = logging.getLogger("ml.baseline.visualization")


def plot_mae_comparison(
    comparison_df: pd.DataFrame,
    output_path: Union[str, Path] = MAE_COMPARISON_PLOT,
) -> Path:
    """Generate bar chart comparing MAE across models.

    Args:
        comparison_df: DataFrame with 'model' and 'mae' columns.
        output_path: Destination path.

    Returns:
        Path of the saved image.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5))

    models = comparison_df["model"].tolist()
    maes = comparison_df["mae"].tolist()

    # Color palette: distinct blue/indigo/emerald/amber
    colors = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6"][:len(models)]

    bars = ax.bar(models, maes, color=colors, width=0.5, edgecolor="#1e293b", linewidth=1.0)

    # Annotate numeric values on top of bars
    for bar in bars:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            h + max(max(maes) * 0.02, 0.005),
            f"{h:.4f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    ax.set_title("Mean Absolute Error (MAE) Comparison: GRU vs. Non-ML Baselines", fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("MAE (lower error is better)", fontsize=11)
    ax.set_ylim(0, max(max(maes) * 1.18, 0.1))
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    plt.tight_layout()
    plt.savefig(out_p, dpi=300, bbox_inches="tight")
    plt.close(fig)

    logger.info("Saved MAE comparison plot to %s", out_p)
    return out_p


def plot_rmse_comparison(
    comparison_df: pd.DataFrame,
    output_path: Union[str, Path] = RMSE_COMPARISON_PLOT,
) -> Path:
    """Generate bar chart comparing RMSE across models.

    Args:
        comparison_df: DataFrame with 'model' and 'rmse' columns.
        output_path: Destination path.

    Returns:
        Path of the saved image.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5))

    models = comparison_df["model"].tolist()
    rmses = comparison_df["rmse"].tolist()

    colors = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6"][:len(models)]
    bars = ax.bar(models, rmses, color=colors, width=0.5, edgecolor="#1e293b", linewidth=1.0)

    for bar in bars:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            h + max(max(rmses) * 0.02, 0.005),
            f"{h:.4f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    ax.set_title("Root Mean Squared Error (RMSE) Comparison: GRU vs. Non-ML Baselines", fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("RMSE (lower error is better)", fontsize=11)
    ax.set_ylim(0, max(max(rmses) * 1.18, 0.1))
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    plt.tight_layout()
    plt.savefig(out_p, dpi=300, bbox_inches="tight")
    plt.close(fig)

    logger.info("Saved RMSE comparison plot to %s", out_p)
    return out_p


def plot_baseline_predictions(
    test_df: pd.DataFrame,
    predictions_dict: Dict[str, Sequence[float]],
    gru_predictions: Optional[Sequence[float]] = None,
    output_path: Union[str, Path] = BASELINE_PREDICTIONS_PLOT,
) -> Path:
    """Generate chronological time-series plot comparing actual congestion and predictions.

    Args:
        test_df: Test DataFrame containing 'prediction_timestamp' and 'future_congestion_score'.
        predictions_dict: Dictionary mapping baseline names to predicted scores.
        gru_predictions: Optional sequence of GRU predicted scores.
        output_path: Destination path.

    Returns:
        Path of the saved image.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 5))

    n_samples = len(test_df)
    x = np.arange(n_samples)

    labels = []
    for i, row in test_df.iterrows():
        dev = row.get("device_id", f"s{i}")
        ts = str(row.get("prediction_timestamp", i)).split()[-1]
        labels.append(f"{dev}\n({ts})")

    y_actual = test_df["future_congestion_score"].to_numpy(dtype=np.float64)

    # Plot actual ground truth as solid black line with stars
    ax.plot(x, y_actual, label="Actual Future Congestion", color="#0f172a", marker="*", markersize=10,
            linewidth=2.5, zorder=5)

    # Color/style map for predictors
    style_map = {
        "Persistence": {"color": "#10b981", "marker": "o", "linestyle": "--"},
        "MovingAverage": {"color": "#f59e0b", "marker": "s", "linestyle": "-."},
        "LinearTrend": {"color": "#8b5cf6", "marker": "^", "linestyle": ":"},
    }

    for name, preds in predictions_dict.items():
        arr = np.asarray(preds, dtype=np.float64)
        style = style_map.get(name, {"color": "#64748b", "marker": "x", "linestyle": "-"})
        ax.plot(
            x,
            arr,
            label=f"{name} Baseline",
            color=style["color"],
            marker=style["marker"],
            linestyle=style["linestyle"],
            linewidth=1.8,
            alpha=0.9,
        )

    # Add GRU predictions if available
    if gru_predictions is not None and len(gru_predictions) == n_samples:
        ax.plot(
            x,
            gru_predictions,
            label="Phase 10 GRU Model",
            color="#2563eb",
            marker="D",
            linestyle="-",
            linewidth=2.0,
            alpha=0.9,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_title("Test Sample Congestion: Actual vs. Predictions", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Chronological Test Sequences (Device & Prediction Timestamp)", fontsize=11)
    ax.set_ylabel("Congestion Score [0.0, 1.0]", fontsize=11)
    ax.set_ylim(-0.05, 1.05)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="#f8fafc", loc="upper left")

    plt.tight_layout()
    plt.savefig(out_p, dpi=300, bbox_inches="tight")
    plt.close(fig)

    logger.info("Saved baseline predictions plot to %s", out_p)
    return out_p
