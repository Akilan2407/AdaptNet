"""Diagnostic Reporting, Schema Validation, and Visualizations for Traffic Classification.

Generates:
1. traffic_class_distribution.png
2. protocol_distribution.png
3. class_by_protocol.png

Validates:
- Valid classes (one of the 6 defined classes)
- Valid confidence range [0.0, 1.0]
- Valid ports [1, 65535]
- Valid protocol handling
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ml.classification.classification_rules import is_valid_port
from ml.classification.config import (
    CLASS_BY_PROTOCOL_PLOT,
    CLASS_DISTRIBUTION_PLOT,
    CLASSIFIED_FLOWS_PATH,
    DEFAULT_OUTPUT_DIR,
    PROTOCOL_DISTRIBUTION_PLOT,
    TRAFFIC_CLASSES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml.classification.report")


def validate_classified_flows(df: pd.DataFrame) -> Dict[str, Any]:
    """Validate data integrity, class membership, confidence bounds, and port ranges.

    Args:
        df: DataFrame of classified flows.

    Returns:
        Validation results dictionary.
    """
    total = len(df)
    if total == 0:
        return {"valid": False, "total_records": 0, "errors": ["DataFrame is empty"]}

    errors = []

    # 1. Validate Classes
    invalid_classes = df[~df["traffic_class"].isin(TRAFFIC_CLASSES)]
    if len(invalid_classes) > 0:
        errors.append(f"Found {len(invalid_classes)} rows with invalid traffic_class values")

    # 2. Validate Confidence Bounds [0.0, 1.0]
    invalid_conf = df[(df["classification_confidence"] < 0.0) | (df["classification_confidence"] > 1.0)]
    if len(invalid_conf) > 0:
        errors.append(f"Found {len(invalid_conf)} rows with confidence out of bounds [0.0, 1.0]")

    # 3. Validate Ports
    invalid_ports_count = 0
    for _, row in df.iterrows():
        src_p = row.get("src_port")
        dst_p = row.get("dst_port")
        # If port is given, it must be valid or NaN
        if pd.notna(src_p) and not is_valid_port(src_p):
            invalid_ports_count += 1
        if pd.notna(dst_p) and not is_valid_port(dst_p):
            invalid_ports_count += 1

    if invalid_ports_count > 0:
        errors.append(f"Found {invalid_ports_count} invalid port values outside [1, 65535]")

    # 4. Check Required Output Columns
    required_cols = [
        "timestamp", "device_id", "flow_id", "src_ip", "dst_ip", "src_port", "dst_port",
        "protocol", "throughput_mbps", "rtt_ms", "packet_loss_percent", "active_connections",
        "traffic_class", "classification_confidence", "classification_reason"
    ]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required output columns: {missing_cols}")

    is_valid = len(errors) == 0
    return {
        "valid": is_valid,
        "total_records": total,
        "errors": errors,
        "class_counts": df["traffic_class"].value_counts().to_dict(),
        "avg_confidence": float(df["classification_confidence"].mean()),
    }


def plot_traffic_class_distribution(
    df: pd.DataFrame,
    output_path: Path = CLASS_DISTRIBUTION_PLOT,
) -> Path:
    """Generate bar chart showing the frequency and percentage of each traffic category."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))

    total = len(df)
    counts = [int((df["traffic_class"] == c).sum()) for c in TRAFFIC_CLASSES]
    percentages = [(c / total) * 100.0 if total > 0 else 0.0 for c in counts]

    colors = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#64748b"]

    bars = ax.bar(TRAFFIC_CLASSES, counts, color=colors, width=0.55, edgecolor="#1e293b", linewidth=1.0)

    for bar, pct in zip(bars, percentages):
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            h + max(max(counts) * 0.02, 0.5),
            f"{int(h)}\n({pct:.1f}%)",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    ax.set_title("Traffic Category Distribution (Metadata Classification)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Traffic Category", fontsize=11)
    ax.set_ylabel("Flow Count", fontsize=11)
    ax.set_ylim(0, max(counts) * 1.25 if max(counts) > 0 else 10)
    ax.grid(axis="y", linestyle=":", alpha=0.6)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

    logger.info("Saved traffic class distribution plot to %s", output_path)
    return output_path


def plot_protocol_distribution(
    df: pd.DataFrame,
    output_path: Path = PROTOCOL_DISTRIBUTION_PLOT,
) -> Path:
    """Generate breakdown of transport protocols (TCP vs. UDP)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 5))

    proto_counts = df["protocol"].value_counts().to_dict() if "protocol" in df.columns else {"TCP": len(df)}
    labels = list(proto_counts.keys())
    values = list(proto_counts.values())

    colors = ["#2563eb", "#f59e0b", "#10b981", "#64748b"][:len(labels)]

    if len(labels) == 1:
        # Bar chart if only one protocol present
        bars = ax.bar(labels, values, color=colors, width=0.4, edgecolor="#1e293b", linewidth=1.0)
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2.0, bar.get_height() / 2.0,
                    f"{bar.get_height()} (100%)", ha="center", va="center", color="white", fontweight="bold")
        ax.set_ylim(0, max(values) * 1.2)
    else:
        ax.pie(values, labels=labels, autopct="%1.1f%%", colors=colors, startangle=140,
               textprops={"fontsize": 11, "fontweight": "bold"})

    ax.set_title("Flow Transport Protocol Breakdown", fontsize=13, fontweight="bold", pad=12)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

    logger.info("Saved protocol distribution plot to %s", output_path)
    return output_path


def plot_class_by_protocol(
    df: pd.DataFrame,
    output_path: Path = CLASS_BY_PROTOCOL_PLOT,
) -> Path:
    """Generate stacked bar chart showing traffic classes partitioned by protocol."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))

    protocols = sorted(df["protocol"].dropna().unique().tolist()) if "protocol" in df.columns else ["TCP"]
    if not protocols:
        protocols = ["TCP"]

    proto_class_counts: Dict[str, List[int]] = {p: [] for p in protocols}

    for cat in TRAFFIC_CLASSES:
        for p in protocols:
            c = int(((df["traffic_class"] == cat) & (df["protocol"] == p)).sum())
            proto_class_counts[p].append(c)

    x = np.arange(len(TRAFFIC_CLASSES))
    width = 0.35 if len(protocols) > 1 else 0.5

    proto_colors = {"TCP": "#2563eb", "UDP": "#f59e0b", "OTHER": "#64748b"}

    if len(protocols) == 1:
        p = protocols[0]
        ax.bar(x, proto_class_counts[p], width=width, color=proto_colors.get(p, "#2563eb"),
               label=p, edgecolor="#1e293b", linewidth=1.0)
    else:
        for idx, p in enumerate(protocols):
            offset = (idx - len(protocols) / 2.0 + 0.5) * width
            ax.bar(x + offset, proto_class_counts[p], width=width,
                   color=proto_colors.get(p, "#6366f1"), label=p, edgecolor="#1e293b", linewidth=1.0)

    ax.set_xticks(x)
    ax.set_xticklabels(TRAFFIC_CLASSES, fontsize=10)
    ax.set_title("Traffic Category Breakdown by Transport Protocol", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("Traffic Category", fontsize=11)
    ax.set_ylabel("Flow Count", fontsize=11)
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    ax.legend(frameon=True, facecolor="#f8fafc")

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

    logger.info("Saved class-by-protocol plot to %s", output_path)
    return output_path


def run_classification_report(
    classified_path: Path = CLASSIFIED_FLOWS_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Dict[str, Any]:
    """Validate classified dataset and generate 3 diagnostic visualizations."""
    if not classified_path.exists():
        raise FileNotFoundError(f"Classified dataset not found at {classified_path}. Run traffic_classifier.py first.")

    df = pd.read_csv(classified_path)
    validation_results = validate_classified_flows(df)

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_traffic_class_distribution(df, output_dir / "traffic_class_distribution.png")
    plot_protocol_distribution(df, output_dir / "protocol_distribution.png")
    plot_class_by_protocol(df, output_dir / "class_by_protocol.png")

    print("\n" + "=" * 45)
    print("PHASE 12 — CLASSIFICATION VALIDATION")
    print("=" * 45)
    print(f"Total Flows Validated: {validation_results['total_records']}")
    print(f"Validation Status:     {'PASSED' if validation_results['valid'] else 'FAILED'}")
    print(f"Average Confidence:    {validation_results['avg_confidence']:.4f}")
    if validation_results["errors"]:
        print("\nErrors Found:")
        for err in validation_results["errors"]:
            print(f"  - {err}")
    print("\nVisualizations Generated:")
    print(f"  - {output_dir / 'traffic_class_distribution.png'}")
    print(f"  - {output_dir / 'protocol_distribution.png'}")
    print(f"  - {output_dir / 'class_by_protocol.png'}")
    print("=" * 45 + "\n")

    return validation_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 12: Generate Traffic Classification Diagnostic Report.")
    parser.add_argument(
        "--input",
        type=Path,
        default=CLASSIFIED_FLOWS_PATH,
        help="Path to classified_flows.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to save plots",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_classification_report(classified_path=args.input, output_dir=args.output_dir)
