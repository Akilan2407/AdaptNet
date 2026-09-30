"""Policy validation and reporting visualizations for Phase 13 QoS Policy Engine.

Validates policy decision integrity and generates 3 publication-ready visual diagnostics:
1. Priority Distribution (data/policy/priority_distribution.png)
2. Priority by Traffic Class (data/policy/priority_by_traffic_class.png)
3. Priority by Congestion Level (data/policy/priority_by_congestion.png)
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ml.policy.config import (
    DEFAULT_OUTPUT_DIR,
    QOS_DECISIONS_PATH,
    POLICY_SUMMARY_PATH,
    PRIORITY_DISTRIBUTION_PLOT,
    PRIORITY_BY_TRAFFIC_CLASS_PLOT,
    PRIORITY_BY_CONGESTION_PLOT,
    PRIORITY_LEVELS,
    TRAFFIC_CLASSES,
    CONGESTION_CLASSES,
)
from ml.policy.qos_policy_engine import QoSPolicyEngine

# Palette for priority labels
PRIORITY_COLORS = {
    "HIGH": "#e74c3c",    # Crimson / High preference
    "MEDIUM": "#f39c12",  # Amber / Moderate preference
    "NORMAL": "#3498db",  # Sky Blue / Default handling
    "LOW": "#95a5a6",     # Slate Gray / Low preference
}


def validate_decisions(decisions_df: pd.DataFrame) -> Dict[str, Any]:
    """Validate policy decision consistency and completeness against specifications.

    Validation Rules:
        1. Priority: Must strictly belong to PRIORITY_LEVELS (LOW, NORMAL, MEDIUM, HIGH).
        2. Traffic class: Must be recognized from Phase 12 (TRAFFIC_CLASSES).
        3. Congestion class: Must belong to CONGESTION_CLASSES (LOW, MEDIUM, HIGH, UNKNOWN).
        4. Priority consistency: Same input must produce the same priority decision.
        5. Rule consistency: Every decision must possess a valid, non-empty rule ID.
        6. Reason consistency: Every decision must possess a valid, non-empty reason string.

    Args:
        decisions_df: DataFrame of evaluated QoS policy decisions.

    Returns:
        Dictionary containing validation results and status.
    """
    total = len(decisions_df)
    errors: List[str] = []

    # 1. Priority Validation
    invalid_pri = decisions_df[~decisions_df["final_priority"].isin(PRIORITY_LEVELS)]
    if not invalid_pri.empty:
        errors.append(f"Found {len(invalid_pri)} decisions with invalid priority values: {invalid_pri['final_priority'].unique().tolist()}")

    # 2. Traffic Class Validation
    invalid_tc = decisions_df[~decisions_df["traffic_class"].isin(TRAFFIC_CLASSES)]
    if not invalid_tc.empty:
        errors.append(f"Found {len(invalid_tc)} decisions with unrecognized traffic classes: {invalid_tc['traffic_class'].unique().tolist()}")

    # 3. Congestion Class Validation
    invalid_cc = decisions_df[~decisions_df["predicted_congestion_class"].isin(CONGESTION_CLASSES)]
    if not invalid_cc.empty:
        errors.append(f"Found {len(invalid_cc)} decisions with unrecognized congestion classes: {invalid_cc['predicted_congestion_class'].unique().tolist()}")

    # 4. Deterministic Consistency Check
    engine = QoSPolicyEngine()
    inconsistent_count = 0
    for _, row in decisions_df.head(20).iterrows():
        ctx = {
            "device_id": row["device_id"],
            "flow_id": row["flow_id"],
            "traffic_class": row["traffic_class"],
            "predicted_congestion_class": row["predicted_congestion_class"],
            "cluster_id": row["cluster_id"],
            "classification_confidence": row["classification_confidence"],
        }
        re_eval = engine.evaluate(ctx)
        if re_eval["final_priority"] != row["final_priority"] or re_eval["policy_rule_id"] != row["policy_rule_id"]:
            inconsistent_count += 1
    if inconsistent_count > 0:
        errors.append(f"Priority evaluation was non-deterministic on {inconsistent_count} checked samples")

    # 5. Rule Consistency Check
    empty_rules = decisions_df[decisions_df["policy_rule_id"].isna() | (decisions_df["policy_rule_id"] == "")]
    if not empty_rules.empty:
        errors.append(f"Found {len(empty_rules)} decisions with empty policy_rule_id")

    # 6. Reason Consistency Check
    empty_reasons = decisions_df[decisions_df["policy_reason"].isna() | (decisions_df["policy_reason"] == "")]
    if not empty_reasons.empty:
        errors.append(f"Found {len(empty_reasons)} decisions with empty policy_reason")

    is_valid = len(errors) == 0
    return {
        "is_valid": is_valid,
        "total_checked": total,
        "errors": errors,
    }


def plot_priority_distribution(decisions_df: pd.DataFrame, output_path: Path) -> None:
    """Plot the overall frequency of generated priority levels."""
    plt.figure(figsize=(7, 5))
    counts = decisions_df["final_priority"].value_counts()
    
    # Ensure all priority levels appear in canonical order
    pri_counts = [counts.get(pri, 0) for pri in PRIORITY_LEVELS]
    colors = [PRIORITY_COLORS[pri] for pri in PRIORITY_LEVELS]

    bars = plt.bar(PRIORITY_LEVELS, pri_counts, color=colors, edgecolor="#2c3e50", linewidth=1.2, width=0.55)
    
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2.0, height + 0.5, f"{int(height)}", ha="center", va="bottom", fontsize=11, fontweight="bold")

    plt.title("QoS Priority Decision Distribution (Phase 13)", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Assigned QoS Priority Level", fontsize=11, labelpad=8)
    plt.ylabel("Flow Count", fontsize=11, labelpad=8)
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.ylim(0, max(pri_counts, default=10) * 1.15 + 2)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_priority_by_traffic_class(decisions_df: pd.DataFrame, output_path: Path) -> None:
    """Plot assigned priorities segmented across recognized traffic classes."""
    plt.figure(figsize=(9, 5.5))
    
    # Cross-tabulate traffic_class and final_priority
    crosstab = pd.crosstab(decisions_df["traffic_class"], decisions_df["final_priority"])
    for pri in PRIORITY_LEVELS:
        if pri not in crosstab.columns:
            crosstab[pri] = 0
    crosstab = crosstab[PRIORITY_LEVELS]

    bottom = pd.Series(0, index=crosstab.index)
    for pri in PRIORITY_LEVELS:
        values = crosstab[pri]
        plt.bar(crosstab.index, values, bottom=bottom, label=pri, color=PRIORITY_COLORS[pri], edgecolor="#2c3e50", linewidth=0.8, width=0.5)
        bottom += values

    plt.title("QoS Priority Distribution by Traffic Category", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Traffic Class", fontsize=11, labelpad=8)
    plt.ylabel("Number of Flows", fontsize=11, labelpad=8)
    plt.legend(title="QoS Priority", frameon=True, facecolor="white", edgecolor="#bdc3c7")
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_priority_by_congestion(decisions_df: pd.DataFrame, output_path: Path) -> None:
    """Plot assigned priorities grouped by predicted congestion level."""
    plt.figure(figsize=(8, 5.5))
    
    crosstab = pd.crosstab(decisions_df["predicted_congestion_class"], decisions_df["final_priority"])
    for pri in PRIORITY_LEVELS:
        if pri not in crosstab.columns:
            crosstab[pri] = 0
    crosstab = crosstab[PRIORITY_LEVELS]

    # Reorder index to standard order
    order = [c for c in ["LOW", "MEDIUM", "HIGH", "UNKNOWN"] if c in crosstab.index]
    crosstab = crosstab.reindex(order)

    bottom = pd.Series(0, index=crosstab.index)
    for pri in PRIORITY_LEVELS:
        values = crosstab[pri]
        plt.bar(crosstab.index, values, bottom=bottom, label=pri, color=PRIORITY_COLORS[pri], edgecolor="#2c3e50", linewidth=0.8, width=0.45)
        bottom += values

    plt.title("QoS Priority Allocation Across Predicted Congestion States", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Predicted Congestion State", fontsize=11, labelpad=8)
    plt.ylabel("Number of Flows", fontsize=11, labelpad=8)
    plt.legend(title="QoS Priority", frameon=True, facecolor="white", edgecolor="#bdc3c7")
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def generate_all_plots(decisions_df: pd.DataFrame, output_dir: Optional[Path] = None) -> None:
    """Generate all 3 required visual artifacts."""
    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    plot_priority_distribution(decisions_df, out_dir / "priority_distribution.png")
    plot_priority_by_traffic_class(decisions_df, out_dir / "priority_by_traffic_class.png")
    plot_priority_by_congestion(decisions_df, out_dir / "priority_by_congestion.png")


def main() -> None:
    """CLI execution entrypoint: run validations and produce diagnostic charts."""
    if not QOS_DECISIONS_PATH.exists():
        print(f"Decisions dataset not found at {QOS_DECISIONS_PATH}. Running batch evaluator first...")
        from ml.policy.policy_evaluator import run_batch_evaluation
        run_batch_evaluation()

    decisions_df = pd.read_csv(QOS_DECISIONS_PATH)
    validation_results = validate_decisions(decisions_df)

    print("========================================")
    print("PHASE 13 — POLICY REPORT & VALIDATION")
    print("========================================")
    print(f"Decisions analyzed: {validation_results['total_checked']}")
    print(f"Validation Status: {'PASSED' if validation_results['is_valid'] else 'FAILED'}")
    if validation_results["errors"]:
        print("Validation Errors:")
        for err in validation_results["errors"]:
            print(f"  - {err}")

    generate_all_plots(decisions_df)
    print("Diagnostic plots generated:")
    print(f"  - {PRIORITY_DISTRIBUTION_PLOT}")
    print(f"  - {PRIORITY_BY_TRAFFIC_CLASS_PLOT}")
    print(f"  - {PRIORITY_BY_CONGESTION_PLOT}")
    print("========================================")


if __name__ == "__main__":
    main()
