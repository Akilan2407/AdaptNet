"""Visualization Module for Congestion Prediction Model Performance.

Generates 4 high-resolution diagnostic plots:
1. training_loss.png: Training & validation loss curves across epochs.
2. actual_vs_predicted.png: Continuous actual vs predicted score scatter plot.
3. prediction_error.png: Residual error analysis and distribution.
4. congestion_confusion_matrix.png: Categorical confusion matrix heatmap.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from ml.congestion.config import (
    CONGESTION_CLASSES,
    DEFAULT_ACTUAL_VS_PRED_PLOT,
    DEFAULT_CONFUSION_MATRIX_PLOT,
    DEFAULT_ERROR_PLOT,
    DEFAULT_TRAINING_LOSS_PLOT,
)

logger = logging.getLogger("ml.congestion.visualization")


def plot_training_loss(
    history: Dict[str, List[float]],
    output_path: Union[str, Path] = DEFAULT_TRAINING_LOSS_PLOT,
) -> Path:
    """Plot training and validation loss progression across epochs.

    Args:
        history: Keras training history dictionary containing 'loss' and optionally 'val_loss'.
        output_path: Destination path for saving plot.

    Returns:
        Path of the saved image.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5))

    train_loss = history.get("loss", [])
    val_loss = history.get("val_loss", [])
    epochs = range(1, len(train_loss) + 1)

    ax.plot(epochs, train_loss, label="Training Loss (MSE)", color="#2563eb", linewidth=2.0)

    if val_loss and len(val_loss) == len(train_loss):
        ax.plot(epochs, val_loss, label="Validation Loss (MSE)", color="#dc2626", linewidth=2.0, linestyle="--")
        best_epoch = int(np.argmin(val_loss)) + 1
        best_val = val_loss[best_epoch - 1]
        ax.scatter([best_epoch], [best_val], color="#dc2626", s=80, zorder=5,
                   label=f"Best Val Epoch ({best_epoch}: {best_val:.4f})")

    ax.set_title("GRU Congestion Predictor: Training & Validation Loss", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Epoch", fontsize=11)
    ax.set_ylabel("Mean Squared Error (MSE)", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="#f8fafc", loc="upper right")

    plt.tight_layout()
    plt.savefig(out_p, dpi=300, bbox_inches="tight")
    plt.close(fig)

    logger.info("Saved training loss plot to %s", out_p)
    return out_p


def plot_actual_vs_predicted(
    y_true: Union[np.ndarray, List[float]],
    y_pred: Union[np.ndarray, List[float]],
    y_class: Optional[Union[np.ndarray, List[str]]] = None,
    output_path: Union[str, Path] = DEFAULT_ACTUAL_VS_PRED_PLOT,
) -> Path:
    """Plot actual vs predicted continuous congestion score with ideal diagonal.

    Args:
        y_true: Ground truth target scores.
        y_pred: Model predicted target scores.
        y_class: Optional ground truth categorical labels for color coding.
        output_path: Destination path for saving plot.

    Returns:
        Path of the saved image.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    y_t = np.asarray(y_true, dtype=np.float64).flatten()
    y_p = np.asarray(y_pred, dtype=np.float64).flatten()

    fig, ax = plt.subplots(figsize=(7, 7))

    # Reference ideal diagonal
    ax.plot([0, 1], [0, 1], color="#94a3b8", linestyle="--", linewidth=1.5, label="Ideal (y = x)")

    color_map = {"LOW": "#10b981", "MEDIUM": "#f59e0b", "HIGH": "#ef4444"}

    if y_class is not None and len(y_class) == len(y_t):
        classes = np.asarray(y_class, dtype=str)
        for cls_name in ["LOW", "MEDIUM", "HIGH"]:
            mask = classes == cls_name
            if np.any(mask):
                ax.scatter(
                    y_t[mask],
                    y_p[mask],
                    color=color_map.get(cls_name, "#6366f1"),
                    label=f"Class: {cls_name}",
                    s=70,
                    alpha=0.85,
                    edgecolors="none",
                )
    else:
        ax.scatter(y_t, y_p, color="#3b82f6", s=60, alpha=0.85, label="Test Samples")

    mae = float(np.mean(np.abs(y_t - y_p))) if len(y_t) > 0 else 0.0
    ax.text(
        0.05, 0.90,
        f"Test Samples: {len(y_t)}\nMAE: {mae:.4f}",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f1f5f9", edgecolor="#cbd5e1", alpha=0.9),
    )

    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.set_title("Actual vs. Predicted Congestion Score", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Actual Future Congestion Score", fontsize=11)
    ax.set_ylabel("Predicted Future Congestion Score", fontsize=11)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="#f8fafc", loc="lower right")

    plt.tight_layout()
    plt.savefig(out_p, dpi=300, bbox_inches="tight")
    plt.close(fig)

    logger.info("Saved actual vs predicted plot to %s", out_p)
    return out_p


def plot_prediction_error(
    y_true: Union[np.ndarray, List[float]],
    y_pred: Union[np.ndarray, List[float]],
    output_path: Union[str, Path] = DEFAULT_ERROR_PLOT,
) -> Path:
    """Plot residuals (y_true - y_pred) and error distribution.

    Args:
        y_true: Ground truth target scores.
        y_pred: Predicted target scores.
        output_path: Destination path for saving plot.

    Returns:
        Path of the saved image.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    y_t = np.asarray(y_true, dtype=np.float64).flatten()
    y_p = np.asarray(y_pred, dtype=np.float64).flatten()
    residuals = y_t - y_p

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # 1. Residuals vs Actual Score
    ax1.axhline(0, color="#ef4444", linestyle="--", linewidth=1.5, label="Zero Error")
    ax1.scatter(y_t, residuals, color="#6366f1", s=60, alpha=0.85, edgecolors="#4338ca")
    ax1.set_title("Residual Error vs. Actual Score", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Actual Congestion Score", fontsize=10)
    ax1.set_ylabel("Residual (Actual - Predicted)", fontsize=10)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper right")

    # 2. Residual Distribution Histogram
    bins = min(max(5, len(residuals) // 2), 15)
    ax2.hist(residuals, bins=bins, color="#3b82f6", edgecolor="#1e40af", alpha=0.75)
    ax2.axvline(0, color="#ef4444", linestyle="--", linewidth=1.5, label="Zero Bias")
    ax2.set_title("Prediction Error Distribution", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Residual (Actual - Predicted)", fontsize=10)
    ax2.set_ylabel("Frequency", fontsize=10)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="upper right")

    plt.tight_layout()
    plt.savefig(out_p, dpi=300, bbox_inches="tight")
    plt.close(fig)

    logger.info("Saved prediction error plot to %s", out_p)
    return out_p


def plot_confusion_matrix(
    cm: Union[np.ndarray, List[List[int]]],
    classes: Optional[List[str]] = None,
    output_path: Union[str, Path] = DEFAULT_CONFUSION_MATRIX_PLOT,
) -> Path:
    """Plot categorical congestion classification confusion matrix heatmap.

    Args:
        cm: 2D array or list of lists representing confusion counts.
        classes: Ordered list of class labels.
        output_path: Destination path for saving plot.

    Returns:
        Path of the saved image.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    if classes is None:
        classes = CONGESTION_CLASSES

    matrix = np.asarray(cm, dtype=np.int32)
    fig, ax = plt.subplots(figsize=(6, 5))

    cmap = plt.get_cmap("Blues")
    im = ax.imshow(matrix, interpolation="nearest", cmap=cmap)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax.set_xticks(np.arange(len(classes)))
    ax.set_yticks(np.arange(len(classes)))
    ax.set_xticklabels(classes, fontsize=10)
    ax.set_yticklabels(classes, fontsize=10)

    # Annotate counts inside cells
    thresh = matrix.max() / 2.0 if matrix.max() > 0 else 0.5
    for i in range(len(classes)):
        for j in range(len(classes)):
            val = matrix[i, j]
            text_color = "white" if val > thresh else "black"
            ax.text(j, i, str(val), ha="center", va="center", color=text_color,
                    fontsize=12, fontweight="bold")

    ax.set_title("Congestion Class Confusion Matrix", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Predicted Class", fontsize=11)
    ax.set_ylabel("Actual Class", fontsize=11)

    plt.tight_layout()
    plt.savefig(out_p, dpi=300, bbox_inches="tight")
    plt.close(fig)

    logger.info("Saved confusion matrix plot to %s", out_p)
    return out_p
