"""Traffic Classification Module for Phase 12.

Implements rule-based, metadata-driven flow classification without packet payload inspection.
Assigns traffic categories: DNS, REAL_TIME, WEB, INTERACTIVE, BULK_TRANSFER, OTHER.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from ml.classification.classification_rules import (
    evaluate_port_rules,
    is_valid_port,
    normalize_protocol,
)
from ml.classification.config import (
    CLASSIFICATION_RULES_PATH,
    CLASSIFICATION_SUMMARY_PATH,
    CLASSIFIED_FLOWS_PATH,
    CONFIDENCE_UNKNOWN,
    DEFAULT_FEATURES_PATH,
    DEFAULT_OUTPUT_DIR,
    PORT_RULES,
    RULE_PRIORITY,
    TRAFFIC_CLASSES,
)
from ml.classification.feature_rules import evaluate_secondary_feature_rules

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml.classification.traffic_classifier")


def generate_deterministic_flow_id(row: Union[pd.Series, Dict[str, Any]]) -> str:
    """Construct a deterministic 5-tuple + device flow identifier.

    Format: {device_id}_{src_ip}:{src_port}->{dst_ip}:{dst_port}_{protocol}
    """
    existing_id = row.get("flow_id")
    if existing_id is not None and str(existing_id).strip() and str(existing_id).strip().lower() != "nan":
        return str(existing_id).strip()

    dev = str(row.get("device_id", "unknown")).strip()
    src_ip = str(row.get("src_ip", "0.0.0.0")).strip()
    dst_ip = str(row.get("dst_ip", "0.0.0.0")).strip()
    src_p = str(row.get("src_port", "0")).strip()
    dst_p = str(row.get("dst_port", "0")).strip()
    proto = normalize_protocol(row.get("protocol", "IP"))

    return f"{dev}_{src_ip}:{src_p}->{dst_ip}:{dst_p}_{proto}"


class TrafficClassifier:
    """Metadata-based, explainable network traffic classifier."""

    def __init__(
        self,
        port_rules: Optional[Dict[str, Dict[str, Any]]] = None,
        priority: Optional[List[str]] = None,
        allowed_classes: Optional[List[str]] = None,
    ) -> None:
        self.port_rules = port_rules if port_rules is not None else PORT_RULES
        self.priority = priority if priority is not None else RULE_PRIORITY
        self.allowed_classes = allowed_classes if allowed_classes is not None else TRAFFIC_CLASSES

    def classify_flow(self, row: Union[pd.Series, Dict[str, Any]]) -> Dict[str, Any]:
        """Classify a single network flow metadata observation.

        Evaluates:
        1. Configured port/protocol rules in strict priority order.
        2. Secondary conservative feature rules if port rules do not match.
        3. Fallback to 'OTHER' if metadata is insufficient.

        Args:
            row: Flow observation with protocol, src_port, dst_port, etc.

        Returns:
            Dictionary with traffic_class, classification_confidence, classification_reason, flow_id.
        """
        proto = row.get("protocol")
        src_p = row.get("src_port")
        dst_p = row.get("dst_port")

        flow_id = generate_deterministic_flow_id(row)

        # 1. Primary Evaluation: Protocol and Port Rules
        port_match = evaluate_port_rules(
            protocol=proto,
            src_port=src_p,
            dst_port=dst_p,
            rules=self.port_rules,
            priority=self.priority,
        )

        if port_match is not None:
            t_class, conf, reason = port_match
            return {
                "flow_id": flow_id,
                "traffic_class": t_class,
                "classification_confidence": round(conf, 4),
                "classification_reason": reason,
            }

        # 2. Secondary Evaluation: Conservative Feature Rules
        feature_match = evaluate_secondary_feature_rules(pd.Series(row))
        if feature_match is not None:
            t_class, conf, reason = feature_match
            return {
                "flow_id": flow_id,
                "traffic_class": t_class,
                "classification_confidence": round(conf, 4),
                "classification_reason": reason,
            }

        # 3. Safe Fallback: OTHER
        return {
            "flow_id": flow_id,
            "traffic_class": "OTHER",
            "classification_confidence": CONFIDENCE_UNKNOWN,
            "classification_reason": "No configured metadata rule matched",
        }

    def classify_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify every flow in a DataFrame, appending classification fields.

        Preserves all existing original columns.
        """
        if df.empty:
            logger.warning("Empty DataFrame provided to classify_dataset.")
            return df.copy()

        result_df = df.copy()

        classes: List[str] = []
        confidences: List[float] = []
        reasons: List[str] = []
        flow_ids: List[str] = []

        for _, row in result_df.iterrows():
            res = self.classify_flow(row)
            classes.append(res["traffic_class"])
            confidences.append(res["classification_confidence"])
            reasons.append(res["classification_reason"])
            flow_ids.append(res["flow_id"])

        result_df["flow_id"] = flow_ids
        result_df["traffic_class"] = classes
        result_df["classification_confidence"] = confidences
        result_df["classification_reason"] = reasons

        logger.info("Classified %d flows successfully.", len(result_df))
        return result_df


def run_traffic_classification(
    input_path: Path = DEFAULT_FEATURES_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Execute end-to-end traffic classification and export required artifacts.

    Generates:
    - data/classification/classified_flows.csv
    - data/classification/classification_rules.json
    - data/classification/classification_summary.json

    Returns:
        Tuple of (classified_dataframe, summary_dictionary)
    """
    if not input_path.exists():
        logger.error("Input telemetry file not found at %s", input_path)
        raise FileNotFoundError(f"Telemetry dataset not found: {input_path}")

    raw_df = pd.read_csv(input_path)
    total_flows = len(raw_df)

    classifier = TrafficClassifier()
    classified_df = classifier.classify_dataset(raw_df)

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Export Classified Flows CSV
    csv_out = output_dir / "classified_flows.csv"
    classified_df.to_csv(csv_out, index=False)
    logger.info("Saved classified flows CSV to %s", csv_out)

    # 2. Export Rules JSON
    rules_out = output_dir / "classification_rules.json"
    rules_record = {
        "description": "Configurable port and protocol rules for traffic classification",
        "rule_priority": RULE_PRIORITY,
        "traffic_classes": TRAFFIC_CLASSES,
        "port_rules": PORT_RULES,
        "confidence_levels": {
            "exact_port": 1.0,
            "port_range": 0.85,
            "secondary_feature": 0.70,
            "unknown": 0.0,
        },
    }
    with open(rules_out, "w") as f:
        json.dump(rules_record, f, indent=2)
    logger.info("Saved classification rules JSON to %s", rules_out)

    # 3. Compute Distribution Statistics
    class_counts = classified_df["traffic_class"].value_counts().to_dict()
    class_distribution = {}
    for cls_name in TRAFFIC_CLASSES:
        count = class_counts.get(cls_name, 0)
        pct = round((count / total_flows) * 100.0, 2) if total_flows > 0 else 0.0
        class_distribution[cls_name] = {"count": count, "percentage": pct}

    proto_counts = classified_df["protocol"].value_counts().to_dict() if "protocol" in classified_df.columns else {}
    avg_confidence = float(classified_df["classification_confidence"].mean()) if total_flows > 0 else 0.0
    unknown_flows = int(class_counts.get("OTHER", 0))
    classified_count = total_flows - unknown_flows

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": 12,
        "total_flows": total_flows,
        "classified_flows": classified_count,
        "unknown_flows": unknown_flows,
        "average_confidence": round(avg_confidence, 4),
        "classification_distribution": class_distribution,
        "protocol_distribution": proto_counts,
        "output_file": str(csv_out),
    }

    summary_out = output_dir / "classification_summary.json"
    with open(summary_out, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info("Saved classification summary JSON to %s", summary_out)

    # 4. Print Required Console Summary (matching Section 29)
    print("\n" + "=" * 40)
    print("PHASE 12 — TRAFFIC CLASSIFICATION")
    print("=" * 40 + "\n")
    print(f"Input flows: {total_flows}\n")
    print(f"Classified flows: {classified_count}")
    print(f"Unknown flows: {unknown_flows}\n")
    print("Traffic distribution:\n")
    for cls_name in TRAFFIC_CLASSES:
        item = class_distribution[cls_name]
        print(f"{cls_name}: {item['count']} ({item['percentage']}%)")
    print(f"\nAverage classification confidence: {avg_confidence:.4f}\n")
    print(f"Output:\n{csv_out}\n")
    print("Phase 12 Status: COMPLETED")
    print("=" * 40 + "\n")

    return classified_df, summary


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Phase 12: Traffic Classification Module.")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_FEATURES_PATH,
        help="Path to network features CSV",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to save classification artifacts",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_traffic_classification(input_path=args.input, output_dir=args.output_dir)
