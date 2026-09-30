"""Visualizations for Phase 16 SHAP Explainability Module."""

import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explainability.config import (
    DEFAULT_GLOBAL_PLOT,
    DEFAULT_LOCAL_PLOTS_DIR,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SUMMARY_PLOT,
    MAX_LOCAL_EXPLANATION_PLOTS,
)

logger = logging.getLogger("ml.explainability.visualization")


class ExplainabilityVisualizer:
    """Generates publication-ready diagnostic charts for global and local SHAP explanations."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.local_plots_dir = self.output_dir / "local"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.local_plots_dir.mkdir(parents=True, exist_ok=True)

    def plot_global_feature_importance(
        self,
        global_df: pd.DataFrame,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Generate horizontal bar chart of global mean absolute SHAP values."""
        save_path = output_path or (self.output_dir / "global_feature_importance.png")
        if global_df.empty:
            logger.warning("Empty DataFrame provided for global importance plot.")
            return save_path

        # Sort from lowest to highest for horizontal bar display
        df_sorted = global_df.sort_values(by="mean_absolute_shap", ascending=True)

        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        bars = ax.barh(
            df_sorted["feature_name"],
            df_sorted["mean_absolute_shap"],
            color="#2b5c8f",
            edgecolor="#18385c",
            height=0.6,
        )

        ax.set_title("Global Feature Importance (Mean |SHAP Value|)", fontsize=14, fontweight="bold", pad=12)
        ax.set_xlabel("Mean |SHAP Value| (Impact on GRU Congestion Score)", fontsize=11)
        ax.set_ylabel("Telemetry Feature", fontsize=11)
        ax.grid(axis="x", linestyle="--", alpha=0.5)

        # Annotate bar values
        for bar in bars:
            width = bar.get_width()
            ax.text(
                width + (max(df_sorted["mean_absolute_shap"]) * 0.015),
                bar.get_y() + bar.get_height() / 2,
                f"{width:.4f}",
                va="center",
                ha="left",
                fontsize=9,
                color="#333333",
            )

        plt.tight_layout()
        plt.savefig(save_path, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved global feature importance plot to %s", save_path)
        return save_path

    def plot_shap_summary(
        self,
        global_df: pd.DataFrame,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Generate summary chart contrasting mean signed vs mean absolute SHAP impact."""
        save_path = output_path or (self.output_dir / "shap_summary.png")
        if global_df.empty:
            return save_path

        df_sorted = global_df.sort_values(by="mean_absolute_shap", ascending=True)

        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        y_pos = np.arange(len(df_sorted))

        # Plot signed impact with color-coding
        signed_vals = df_sorted["mean_signed_shap"]
        colors = ["#d9534f" if v >= 0 else "#428bca" for v in signed_vals]

        ax.barh(y_pos, signed_vals, color=colors, height=0.55, alpha=0.85)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(df_sorted["feature_name"])
        ax.axvline(0, color="black", linewidth=1.0, linestyle="--")

        ax.set_title("SHAP Feature Attribution Direction & Magnitude", fontsize=14, fontweight="bold", pad=12)
        ax.set_xlabel("Mean Signed SHAP (Positive: Increased Congestion, Negative: Decreased)", fontsize=11)
        ax.set_ylabel("Telemetry Feature", fontsize=11)
        ax.grid(axis="x", linestyle=":", alpha=0.5)

        plt.tight_layout()
        plt.savefig(save_path, bbox_inches="tight")
        plt.close(fig)
        logger.info("Saved SHAP summary plot to %s", save_path)
        return save_path

    def plot_local_waterfall(
        self,
        trace_explanation: Dict[str, Any],
        output_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Generate local diverging bar chart showing feature attributions for a single trace."""
        trace_id = trace_explanation.get("trace_id", "UNKNOWN")
        features = trace_explanation.get("features", [])
        if not features:
            return None

        target_dir = output_dir or self.local_plots_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        save_path = target_dir / f"{trace_id}.png"

        pred_score = trace_explanation["prediction"].get("score", 0.0)
        base_val = trace_explanation["prediction"].get("base_value", 0.0)

        # Sort features by shap_value ascending for horizontal display
        sorted_feats = sorted(features, key=lambda x: x["shap_value"])
        names = [f["name"] for f in sorted_feats]
        vals = [f["shap_value"] for f in sorted_feats]
        colors = ["#d9534f" if v >= 0 else "#428bca" for v in vals]

        fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
        bars = ax.barh(names, vals, color=colors, height=0.55)
        ax.axvline(0, color="#555555", linewidth=1.0, linestyle="--")

        ax.set_title(
            f"Local Explanation: {trace_id} (Pred: {pred_score:.3f}, Base: {base_val:.3f})",
            fontsize=12,
            fontweight="bold",
            pad=10,
        )
        ax.set_xlabel("SHAP Value (Contribution to Predicted Congestion Score)", fontsize=10)
        ax.grid(axis="x", linestyle=":", alpha=0.5)

        plt.tight_layout()
        plt.savefig(save_path, bbox_inches="tight")
        plt.close(fig)
        return save_path

    def generate_all_visualizations(
        self,
        global_df: pd.DataFrame,
        local_records: List[Dict[str, Any]],
        max_local: int = MAX_LOCAL_EXPLANATION_PLOTS,
    ) -> Dict[str, Any]:
        """Generate global importance, summary, and sample local plots."""
        g_plot = self.plot_global_feature_importance(global_df)
        s_plot = self.plot_shap_summary(global_df)

        local_plots = []
        successful_traces = [r for r in local_records if r.get("explanation_status") == "SUCCESS"]
        for r in successful_traces[:max_local]:
            p = self.plot_local_waterfall(r)
            if p:
                local_plots.append(str(p))

        return {
            "global_feature_importance_plot": str(g_plot),
            "shap_summary_plot": str(s_plot),
            "local_plots_generated": len(local_plots),
        }
