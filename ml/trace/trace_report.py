"""Visual diagnostic reporting for Phase 15 Decision Traces."""

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

from ml.trace.config import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SUMMARY_JSON,
    DEFAULT_TRACES_CSV,
    TRACE_COMPLETENESS_PLOT,
    TRACE_STAGE_PLOT,
)

COMPLETENESS_COLORS = {
    "COMPLETE":   "#2ecc71",  # Emerald Green
    "PARTIAL":    "#f39c12",  # Amber
    "INCOMPLETE": "#e74c3c",  # Crimson
}

STAGE_COLORS = [
    "#3498db",  # Monitoring (Blue)
    "#2980b9",  # Features (Navy)
    "#9b59b6",  # Profile (Purple)
    "#e67e22",  # Congestion (Orange)
    "#1abc9c",  # Classification (Teal)
    "#f1c40f",  # Policy (Gold)
    "#e74c3c",  # Control (Red)
]


def plot_trace_completeness(summary: Dict[str, Any], output_path: Path) -> None:
    """Plot distribution of traces by completeness level."""
    plt.figure(figsize=(7, 5))
    levels = ["COMPLETE", "PARTIAL", "INCOMPLETE"]
    counts = [
        summary.get("complete_traces", 0),
        summary.get("partial_traces", 0),
        summary.get("incomplete_traces", 0),
    ]
    colors = [COMPLETENESS_COLORS[lvl] for lvl in levels]

    bars = plt.bar(levels, counts, color=colors, edgecolor="#2c3e50", linewidth=1.2, width=0.55)
    for bar in bars:
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2.0, h + 0.5, f"{int(h)}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    plt.title("Decision Trace Completeness Distribution (Phase 15)", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Completeness Level", fontsize=11, labelpad=8)
    plt.ylabel("Number of Traces", fontsize=11, labelpad=8)
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.ylim(0, max(counts, default=10) * 1.15 + 2)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_stage_availability(summary: Dict[str, Any], output_path: Path) -> None:
    """Plot horizontal bar chart of stage availability match percentages."""
    plt.figure(figsize=(8, 5.5))
    stages = [
        "1. Monitoring",
        "2. Features",
        "3. Profile",
        "4. Congestion",
        "5. Classification",
        "6. Policy",
        "7. Control",
    ]
    rates = [
        summary.get("monitoring_match_rate", 0.0),
        summary.get("feature_match_rate", 0.0),
        summary.get("profile_match_rate", 0.0),
        summary.get("congestion_match_rate", 0.0),
        summary.get("classification_match_rate", 0.0),
        summary.get("policy_match_rate", 0.0),
        summary.get("control_match_rate", 0.0),
    ]

    # Invert so Stage 1 appears at top
    stages = stages[::-1]
    rates = rates[::-1]
    colors = STAGE_COLORS[::-1]

    bars = plt.barh(stages, rates, color=colors, edgecolor="#2c3e50", linewidth=1.0, height=0.55)
    for bar in bars:
        w = bar.get_width()
        plt.text(w + 1.0, bar.get_y() + bar.get_height() / 2.0, f"{w:.1f}%", va="center", ha="left", fontsize=10, fontweight="bold")

    plt.title("Pipeline Stage Match & Availability Rates (Phase 15)", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Stage Match Rate (%)", fontsize=11, labelpad=8)
    plt.ylabel("Pipeline Stage", fontsize=11, labelpad=8)
    plt.xlim(0, 115)
    plt.grid(axis="x", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def generate_all_plots(summary: Dict[str, Any], output_dir: Optional[Path] = None) -> None:
    """Generate both required diagnostic plots."""
    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_trace_completeness(summary, out_dir / "trace_completeness.png")
    plot_stage_availability(summary, out_dir / "trace_stage_availability.png")


def main():
    if not DEFAULT_SUMMARY_JSON.exists():
        print("Trace summary JSON not found. Running trace builder first...")
        from ml.trace.trace_builder import TraceBuilder
        from ml.trace.trace_export import TraceExporter
        builder = TraceBuilder()
        traces = builder.build_traces()
        exporter = TraceExporter()
        summary = exporter.export_all(traces)
    else:
        with open(DEFAULT_SUMMARY_JSON, "r", encoding="utf-8") as f:
            summary = json.load(f)

    generate_all_plots(summary)
    print("========================================")
    print("PHASE 15 — TRACE REPORT")
    print("========================================")
    print(f"Total Traces Analyzed : {summary.get('total_traces')}")
    print(f"Plot 1 : {TRACE_COMPLETENESS_PLOT}")
    print(f"Plot 2 : {TRACE_STAGE_PLOT}")
    print("========================================")


if __name__ == "__main__":
    main()
