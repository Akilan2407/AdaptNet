"""Diagnostic reporting and visualizations for Phase 14 Adaptive Traffic Control."""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ml.control.config import (
    CONTROL_ACTIONS_PLOT,
    DEFAULT_ACTIONS_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SUMMARY_PATH,
    PRIORITY_CONTROL_PLOT,
)

STATUS_COLORS = {
    "DRY_RUN": "#3498db",  # Sky Blue
    "SUCCESS": "#2ecc71",  # Emerald Green
    "SKIPPED": "#95a5a6",  # Slate Gray
    "FAILED":  "#e74c3c",  # Crimson
}

CLASS_COLORS = {
    "1:10 (HIGH)":   "#e74c3c",
    "1:20 (MEDIUM)": "#f39c12",
    "1:30 (NORMAL)": "#3498db",
    "1:40 (LOW)":    "#95a5a6",
}


def plot_control_actions(df: pd.DataFrame, output_path: Path) -> None:
    """Plot distribution of control action outcomes."""
    plt.figure(figsize=(7, 5))
    counts = df["status"].value_counts()
    
    statuses = ["DRY_RUN", "SUCCESS", "SKIPPED", "FAILED"]
    status_counts = [counts.get(s, 0) for s in statuses]
    colors = [STATUS_COLORS[s] for s in statuses]

    bars = plt.bar(statuses, status_counts, color=colors, edgecolor="#2c3e50", linewidth=1.2, width=0.55)
    for bar in bars:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2.0, h + 0.5, f"{int(h)}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    plt.title("Adaptive Traffic Control Action Outcomes (Phase 14)", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Action Status", fontsize=11, labelpad=8)
    plt.ylabel("Number of Actions", fontsize=11, labelpad=8)
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.ylim(0, max(status_counts, default=10) * 1.15 + 2)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_priority_control_distribution(df: pd.DataFrame, output_path: Path) -> None:
    """Plot allocation of traffic control classes."""
    plt.figure(figsize=(7, 5))
    
    # Map classes to descriptive labels
    class_map = {
        "1:10": "1:10 (HIGH)",
        "1:20": "1:20 (MEDIUM)",
        "1:30": "1:30 (NORMAL)",
        "1:40": "1:40 (LOW)",
    }
    
    valid_actions = df[df["status"].isin(["SUCCESS", "DRY_RUN"])]
    mapped_classes = valid_actions["target_class"].map(lambda c: class_map.get(str(c), str(c)))
    counts = mapped_classes.value_counts()

    ordered_classes = ["1:10 (HIGH)", "1:20 (MEDIUM)", "1:30 (NORMAL)", "1:40 (LOW)"]
    class_counts = [counts.get(c, 0) for c in ordered_classes]
    colors = [CLASS_COLORS[c] for c in ordered_classes]

    bars = plt.bar(ordered_classes, class_counts, color=colors, edgecolor="#2c3e50", linewidth=1.2, width=0.55)
    for bar in bars:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2.0, h + 0.1, f"{int(h)}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    plt.title("Traffic Control Class Allocation (HTB Classes)", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Target Control Class", fontsize=11, labelpad=8)
    plt.ylabel("Number of Enforced Flows", fontsize=11, labelpad=8)
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.ylim(0, max(class_counts, default=5) * 1.25 + 1)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def generate_all_plots(df: pd.DataFrame, output_dir: Optional[Path] = None) -> None:
    """Generate all diagnostic visual artifacts for Phase 14."""
    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_control_actions(df, out_dir / "control_actions.png")
    plot_priority_control_distribution(df, out_dir / "priority_control_distribution.png")


def main():
    if not DEFAULT_ACTIONS_PATH.exists():
        print("Actions CSV not found. Running control bridge first...")
        from ml.control.control_bridge import ControlBridge
        ControlBridge().run_bridge()

    df = pd.read_csv(DEFAULT_ACTIONS_PATH)
    generate_all_plots(df)

    print("========================================")
    print("PHASE 14 — CONTROL REPORT")
    print("========================================")
    print(f"Total Actions Analyzed : {len(df)}")
    print(f"Plot 1 : {CONTROL_ACTIONS_PLOT}")
    print(f"Plot 2 : {PRIORITY_CONTROL_PLOT}")
    print("========================================")


if __name__ == "__main__":
    main()
