"""Batch Policy Evaluator for Phase 13 QoS Policy Engine.

Joins Classified Flows (Phase 12), Congestion Predictions (Phase 10), and
User Behavior Profiles (Phase 8) using robust domain identifiers (device_id, timestamp),
evaluates deterministic QoS policy decisions, and exports structured results.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.policy.config import (
    DEFAULT_CLASSIFIED_FLOWS_PATH,
    DEFAULT_TEST_PREDICTIONS_PATH,
    DEFAULT_BEHAVIOR_PROFILES_PATH,
    DEFAULT_OUTPUT_DIR,
    QOS_DECISIONS_PATH,
    POLICY_SUMMARY_PATH,
    TIME_MATCH_TOLERANCE_SECONDS,
)
from ml.policy.qos_policy_engine import QoSPolicyEngine

logger = logging.getLogger(__name__)


def load_input_datasets(
    flows_path: Optional[Path] = None,
    predictions_path: Optional[Path] = None,
    profiles_path: Optional[Path] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the required input datasets from Phase 8, 10, and 12.

    Args:
        flows_path: Path to classified flows CSV.
        predictions_path: Path to congestion predictions CSV.
        profiles_path: Path to user behavior profiles CSV.

    Returns:
        Tuple of (flows_df, predictions_df, profiles_df).
    """
    f_path = flows_path or DEFAULT_CLASSIFIED_FLOWS_PATH
    pred_path = predictions_path or DEFAULT_TEST_PREDICTIONS_PATH
    prof_path = profiles_path or DEFAULT_BEHAVIOR_PROFILES_PATH

    if not Path(f_path).exists():
        raise FileNotFoundError(f"Classified flows dataset not found at {f_path}")
    if not Path(pred_path).exists():
        raise FileNotFoundError(f"Congestion predictions dataset not found at {pred_path}")
    if not Path(prof_path).exists():
        raise FileNotFoundError(f"User behavior profiles dataset not found at {prof_path}")

    flows_df = pd.read_csv(f_path)
    predictions_df = pd.read_csv(pred_path)
    profiles_df = pd.read_csv(prof_path)

    return flows_df, predictions_df, profiles_df


def match_flow_contexts(
    flows_df: pd.DataFrame,
    predictions_df: pd.DataFrame,
    profiles_df: pd.DataFrame,
    time_tolerance_seconds: float = TIME_MATCH_TOLERANCE_SECONDS,
) -> List[Dict[str, Any]]:
    """Join flows with profiles and congestion predictions using reliable identifiers.

    Joining Strategy:
        1. Device Profile Join: Exact match on `device_id`.
           Retrieves device's `cluster_id` from behavior profiling (Phase 8).
        2. Congestion Prediction Join: Matches by `device_id` and temporal proximity.
           For each flow, searches predictions for the same `device_id`. If a prediction exists
           whose `prediction_timestamp` is within `time_tolerance_seconds` of the flow's
           `timestamp`, it is matched. If no prediction is within tolerance or device was not
           in test predictions, congestion attributes default to None / 'UNKNOWN'.
        3. Never joins solely by row index or arbitrary row numbering.

    Args:
        flows_df: DataFrame of classified network flows.
        predictions_df: DataFrame of congestion predictions.
        profiles_df: DataFrame of device behavior profiles.
        time_tolerance_seconds: Maximum allowable time difference for temporal alignment.

    Returns:
        List of merged flow context dictionaries ready for policy evaluation.
    """
    # Build device behavior profile lookup: device_id -> dict
    profile_lookup: Dict[str, Dict[str, Any]] = {}
    for _, row in profiles_df.iterrows():
        dev_id = str(row["device_id"]).strip()
        profile_lookup[dev_id] = {
            "cluster_id": int(row["cluster_id"]) if pd.notna(row["cluster_id"]) else None,
            "profile_label": str(row["profile_label"]) if pd.notna(row.get("profile_label")) else "Unknown",
        }

    # Prepare predictions with parsed datetime
    pred_records = []
    if "prediction_timestamp" in predictions_df.columns:
        for _, row in predictions_df.iterrows():
            dev_id = str(row["device_id"]).strip()
            ts_str = str(row["prediction_timestamp"]).strip()
            try:
                ts_dt = pd.to_datetime(ts_str)
            except Exception:
                ts_dt = None

            pred_records.append({
                "device_id": dev_id,
                "timestamp_dt": ts_dt,
                "predicted_score": float(row["predicted_score"]) if pd.notna(row.get("predicted_score")) else None,
                "predicted_class": str(row["predicted_class"]).strip().upper() if pd.notna(row.get("predicted_class")) else None,
            })

    # Build flow contexts
    contexts: List[Dict[str, Any]] = []

    for _, flow_row in flows_df.iterrows():
        dev_id = str(flow_row.get("device_id", "")).strip()
        flow_id = str(flow_row.get("flow_id", "")).strip()
        ts_str = str(flow_row.get("timestamp", "")).strip() if pd.notna(flow_row.get("timestamp")) else None

        flow_dt = None
        if ts_str:
            try:
                flow_dt = pd.to_datetime(ts_str)
            except Exception:
                flow_dt = None

        # 1. Behavior Profile Lookup
        profile_info = profile_lookup.get(dev_id, {})
        cluster_id = profile_info.get("cluster_id")

        # 2. Congestion Prediction Matching (Temporal alignment per device)
        matched_pred = None
        best_delta = float("inf")

        if flow_dt is not None:
            for p in pred_records:
                if p["device_id"] == dev_id and p["timestamp_dt"] is not None:
                    delta = abs((flow_dt - p["timestamp_dt"]).total_seconds())
                    if delta <= time_tolerance_seconds and delta < best_delta:
                        best_delta = delta
                        matched_pred = p

        pred_score = matched_pred["predicted_score"] if matched_pred else None
        pred_class = matched_pred["predicted_class"] if matched_pred else None

        ctx: Dict[str, Any] = {
            "timestamp": ts_str,
            "device_id": dev_id,
            "flow_id": flow_id,
            "traffic_class": flow_row.get("traffic_class"),
            "classification_confidence": flow_row.get("classification_confidence", 1.0),
            "predicted_congestion_score": pred_score,
            "predicted_congestion_class": pred_class,
            "cluster_id": cluster_id,
            "throughput_mbps": flow_row.get("throughput_mbps") if pd.notna(flow_row.get("throughput_mbps")) else None,
            "rtt_ms": flow_row.get("rtt_ms") if pd.notna(flow_row.get("rtt_ms")) else None,
            "packet_loss_percent": flow_row.get("packet_loss_percent") if pd.notna(flow_row.get("packet_loss_percent")) else None,
            "active_connections": flow_row.get("active_connections") if pd.notna(flow_row.get("active_connections")) else None,
        }
        contexts.append(ctx)

    return contexts


def evaluate_batch(
    contexts: List[Dict[str, Any]],
    engine: Optional[QoSPolicyEngine] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Evaluate QoS policy for a batch of flow contexts.

    Args:
        contexts: List of flow context dictionaries.
        engine: QoSPolicyEngine instance (creates default if None).

    Returns:
        Tuple of (decisions_dataframe, summary_statistics_dictionary).
    """
    policy_engine = engine or QoSPolicyEngine()
    decision_records: List[Dict[str, Any]] = []

    for ctx in contexts:
        decision = policy_engine.evaluate(ctx)
        decision_records.append(decision)

    # Format into DataFrame with canonical columns (Section 22)
    output_columns = [
        "timestamp",
        "device_id",
        "flow_id",
        "cluster_id",
        "traffic_class",
        "classification_confidence",
        "predicted_congestion_score",
        "predicted_congestion_class",
        "base_priority",
        "congestion_adjustment",
        "user_profile_adjustment",
        "final_priority",
        "policy_rule_id",
        "policy_reason",
        "input_completeness",
    ]

    decisions_df = pd.DataFrame(decision_records)
    # Ensure all required columns exist
    for col in output_columns:
        if col not in decisions_df.columns:
            decisions_df[col] = None
    decisions_df = decisions_df[output_columns]

    # Generate Summary Statistics (Section 23)
    total_decisions = len(decisions_df)
    priority_dist = decisions_df["final_priority"].value_counts().to_dict()
    traffic_dist = decisions_df["traffic_class"].value_counts().to_dict()
    congestion_dist = decisions_df["predicted_congestion_class"].value_counts().to_dict()
    rule_usage = decisions_df["policy_rule_id"].value_counts().to_dict()
    completeness_dist = decisions_df["input_completeness"].value_counts().to_dict()

    summary: Dict[str, Any] = {
        "total_decisions": total_decisions,
        "priority_distribution": priority_dist,
        "traffic_class_distribution": traffic_dist,
        "congestion_distribution": congestion_dist,
        "rule_usage": rule_usage,
        "input_completeness": completeness_dist,
    }

    return decisions_df, summary


def run_batch_evaluation(
    output_dir: Optional[Path] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Execute end-to-end batch evaluation, export CSV and summary JSON.

    Args:
        output_dir: Directory to save generated artifacts (defaults to data/policy/).

    Returns:
        Tuple of (decisions_dataframe, summary_dictionary).
    """
    out_dir = output_dir or DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    flows_df, predictions_df, profiles_df = load_input_datasets()
    contexts = match_flow_contexts(flows_df, predictions_df, profiles_df)
    decisions_df, summary = evaluate_batch(contexts)

    # Export CSV
    csv_path = out_dir / "qos_decisions.csv"
    decisions_df.to_csv(csv_path, index=False)

    # Export JSON Summary
    json_path = out_dir / "policy_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return decisions_df, summary
