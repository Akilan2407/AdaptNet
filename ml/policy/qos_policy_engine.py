"""Core Rule-Based QoS Policy Engine for Phase 13.

Synthesizes Traffic Classification (Phase 12), Congestion Prediction (Phase 10),
and User Behavior Profiling (Phase 8) into deterministic, explainable QoS priorities.
"""

import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.policy.config import (
    DEFAULT_CONGESTION_THRESHOLDS,
    DEFAULT_PRIORITY,
    PRIORITY_LEVELS,
    PRIORITY_TO_NUMERIC,
    TRAFFIC_CLASSES,
    TRAFFIC_CLASS_PRIORITIES,
    CONGESTION_CLASSES,
    CONGESTION_ADJUSTMENTS,
    CLUSTER_ADJUSTMENTS,
    DEFAULT_OUTPUT_DIR,
    QOS_DECISIONS_PATH,
    POLICY_SUMMARY_PATH,
)
from ml.policy.priority import (
    priority_to_numeric,
    numeric_to_priority,
    apply_priority_adjustment,
    clamp_numeric,
)
from ml.policy.policy_rules import find_matching_rule, POLICY_RULES
from ml.policy.decision_reason import format_decision_reason

logger = logging.getLogger(__name__)


class QoSPolicyEngine:
    """Deterministic, explainable rule-based QoS Policy Engine."""

    def __init__(
        self,
        traffic_priorities: Optional[Dict[str, str]] = None,
        cluster_adjustments: Optional[Dict[int, int]] = None,
        congestion_thresholds: Optional[Dict[str, Tuple[float, float]]] = None,
        custom_rules: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize the QoS Policy Engine with configurable policy tables.

        Args:
            traffic_priorities: Mapping of traffic class to default priority string.
            cluster_adjustments: Explicit mapping of cluster_id to numeric adjustment.
            congestion_thresholds: Congestion score range mapping for class resolution.
            custom_rules: Optional rule catalog overriding default rules.
        """
        self.traffic_priorities = (
            traffic_priorities.copy() if traffic_priorities else TRAFFIC_CLASS_PRIORITIES.copy()
        )
        self.cluster_adjustments = (
            cluster_adjustments.copy() if cluster_adjustments else CLUSTER_ADJUSTMENTS.copy()
        )
        self.congestion_thresholds = (
            congestion_thresholds.copy()
            if congestion_thresholds
            else DEFAULT_CONGESTION_THRESHOLDS.copy()
        )
        self.custom_rules = custom_rules
        self.rules = custom_rules if custom_rules is not None else POLICY_RULES

    def load_policy(self, config_dict: Dict[str, Any]) -> None:
        """Dynamically update policy configuration parameters.

        Args:
            config_dict: Dictionary containing policy updates.
        """
        if "traffic_priorities" in config_dict:
            self.traffic_priorities.update(config_dict["traffic_priorities"])
        if "cluster_adjustments" in config_dict:
            self.cluster_adjustments.update(config_dict["cluster_adjustments"])
        if "congestion_thresholds" in config_dict:
            self.congestion_thresholds.update(config_dict["congestion_thresholds"])
        if "custom_rules" in config_dict:
            self.custom_rules = config_dict["custom_rules"]
            self.rules = self.custom_rules

    def score_to_congestion_class(self, score: Optional[float]) -> str:
        """Convert a numerical congestion score [0.0, 1.0] to a congestion class.

        Args:
            score: Congestion score between 0.0 and 1.0, or None.

        Returns:
            One of 'LOW', 'MEDIUM', 'HIGH', or 'UNKNOWN'.
        """
        if score is None:
            return "UNKNOWN"
        try:
            val = float(score)
        except (ValueError, TypeError):
            return "UNKNOWN"

        if val < 0.0 or val > 1.0:
            logger.warning("Congestion score %s out of [0.0, 1.0] range", val)

        for c_class, (low, high) in self.congestion_thresholds.items():
            # Inclusive on upper boundary for HIGH class
            if c_class == "HIGH":
                if low <= val <= high + 1e-6:
                    return c_class
            else:
                if low <= val < high:
                    return c_class

        if val >= 0.67:
            return "HIGH"
        elif val >= 0.33:
            return "MEDIUM"
        return "LOW"

    def validate_input(self, context: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate input flow context and extract normalized attributes.

        Args:
            context: Dictionary containing flow attributes.

        Returns:
            Tuple of (is_valid, error_message, normalized_context).
        """
        if not isinstance(context, dict):
            return False, f"Context must be a dictionary, got {type(context).__name__}", {}

        normalized = dict(context)

        # Validate / normalize device_id & flow_id
        normalized["device_id"] = str(context.get("device_id", "unknown_device")).strip()
        normalized["flow_id"] = str(context.get("flow_id", "unknown_flow")).strip()
        normalized["timestamp"] = context.get("timestamp", None)

        # Validate / normalize traffic_class
        raw_tc = context.get("traffic_class")
        if raw_tc is None or not isinstance(raw_tc, str) or not raw_tc.strip():
            normalized["traffic_class"] = "OTHER"
        else:
            tc_upper = raw_tc.strip().upper()
            normalized["traffic_class"] = tc_upper if tc_upper in TRAFFIC_CLASSES else "OTHER"

        # Validate classification confidence
        raw_conf = context.get("classification_confidence", 1.0)
        try:
            normalized["classification_confidence"] = float(raw_conf) if raw_conf is not None else 0.0
        except (ValueError, TypeError):
            normalized["classification_confidence"] = 0.0

        # Validate congestion attributes
        raw_c_class = context.get("predicted_congestion_class")
        raw_score = context.get("predicted_congestion_score")

        try:
            norm_score = float(raw_score) if raw_score is not None else None
        except (ValueError, TypeError):
            norm_score = None
        normalized["predicted_congestion_score"] = norm_score

        if raw_c_class is not None and isinstance(raw_c_class, str) and raw_c_class.strip().upper() in CONGESTION_CLASSES:
            normalized["predicted_congestion_class"] = raw_c_class.strip().upper()
        elif norm_score is not None:
            normalized["predicted_congestion_class"] = self.score_to_congestion_class(norm_score)
        else:
            normalized["predicted_congestion_class"] = "UNKNOWN"

        # Validate cluster_id (neutral mathematical identifier)
        raw_cluster = context.get("cluster_id")
        try:
            normalized["cluster_id"] = int(raw_cluster) if raw_cluster is not None else None
        except (ValueError, TypeError):
            normalized["cluster_id"] = None

        return True, "", normalized

    def evaluate(self, flow_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute deterministic 9-step policy evaluation on a flow context.

        Evaluation Order:
            1. Validate input
            2. Determine traffic class
            3. Determine congestion class
            4. Determine default traffic priority
            5. Apply congestion adjustment / rule matching
            6. Apply optional user-profile adjustment
            7. Clamp final priority
            8. Generate policy reason
            9. Generate decision record

        Args:
            flow_context: Dictionary representing a single flow context.

        Returns:
            Structured decision record dictionary.
        """
        # Step 1: Validate input
        is_valid, err_msg, ctx = self.validate_input(flow_context)
        if not is_valid:
            raise ValueError(f"Input validation error: {err_msg}")

        # Step 2: Determine traffic class
        traffic_class = ctx["traffic_class"]

        # Step 3: Determine congestion class
        congestion_class = ctx["predicted_congestion_class"]

        # Step 4: Determine default traffic priority
        base_priority = self.traffic_priorities.get(traffic_class, DEFAULT_PRIORITY)

        # Step 5: Match rule and apply congestion-aware resolution
        matched_rule = find_matching_rule(traffic_class, congestion_class, self.rules)
        rule_id = matched_rule["rule_id"]
        rule_priority = matched_rule["priority"]
        base_reason = matched_rule["reason"]

        # Congestion adjustment delta
        congestion_adj = CONGESTION_ADJUSTMENTS.get(congestion_class, 0)
        if congestion_adj != 0:
            congestion_adjusted_pri, _ = apply_priority_adjustment(rule_priority, congestion_adj)
        else:
            congestion_adjusted_pri = rule_priority

        # Step 6: Apply optional user-profile adjustment
        cluster_id = ctx["cluster_id"]
        cluster_available = cluster_id is not None
        prediction_available = congestion_class != "UNKNOWN"
        classification_confidence = ctx["classification_confidence"]

        if cluster_available and cluster_id in self.cluster_adjustments:
            user_profile_adj = int(self.cluster_adjustments[cluster_id])
        else:
            user_profile_adj = 0

        # Step 7: Clamp final priority within [0, 3] (LOW to HIGH)
        final_priority, final_numeric = apply_priority_adjustment(
            congestion_adjusted_pri, user_profile_adj
        )

        # Step 8: Generate explainable policy reason
        policy_reason = format_decision_reason(
            base_reason=base_reason,
            base_priority=congestion_adjusted_pri,
            user_profile_adjustment=user_profile_adj,
            final_priority=final_priority,
            cluster_id=cluster_id,
        )

        # Input completeness: COMPLETE only if traffic class, congestion prediction, and cluster are known
        if traffic_class in TRAFFIC_CLASSES and prediction_available and cluster_available:
            input_completeness = "COMPLETE"
        else:
            input_completeness = "PARTIAL"

        # Step 9: Generate decision record
        decision_record: Dict[str, Any] = {
            "timestamp": ctx.get("timestamp"),
            "device_id": ctx["device_id"],
            "flow_id": ctx["flow_id"],
            "cluster_id": cluster_id,
            "traffic_class": traffic_class,
            "classification_confidence": classification_confidence,
            "predicted_congestion_score": ctx["predicted_congestion_score"],
            "predicted_congestion_class": congestion_class,
            "base_priority": base_priority,
            "congestion_adjustment": congestion_adj,
            "user_profile_adjustment": user_profile_adj,
            "final_priority": final_priority,
            "policy_rule_id": rule_id,
            "policy_reason": policy_reason,
            "input_completeness": input_completeness,
            "prediction_available": prediction_available,
            "cluster_available": cluster_available,
        }

        return decision_record

    def evaluate_policy(self, flow_context: Dict[str, Any]) -> Dict[str, Any]:
        """Alias for evaluate() to satisfy specification interface."""
        return self.evaluate(flow_context)

    def generate_decision(self, flow_context: Dict[str, Any]) -> Dict[str, Any]:
        """Alias for evaluate() to satisfy specification interface."""
        return self.evaluate(flow_context)


def main() -> None:
    """CLI execution entrypoint: run batch policy evaluation and display report."""
    from ml.policy.policy_evaluator import run_batch_evaluation

    print("========================================")
    print("PHASE 13 — QoS POLICY ENGINE")
    print("========================================")
    print()

    decisions_df, summary = run_batch_evaluation()

    print(f"Input flows: {summary['total_decisions']}")
    print(f"Policy decisions generated: {summary['total_decisions']}")
    print()
    print("Traffic classes:")
    for tc in TRAFFIC_CLASSES:
        count = summary["traffic_class_distribution"].get(tc, 0)
        print(f"  {tc}: {count}")
    print()
    print("Predicted congestion:")
    for cc in ["LOW", "MEDIUM", "HIGH", "UNKNOWN"]:
        count = summary["congestion_distribution"].get(cc, 0)
        print(f"  {cc}: {count}")
    print()
    print("Final priorities:")
    for pri in PRIORITY_LEVELS:
        count = summary["priority_distribution"].get(pri, 0)
        print(f"  {pri}: {count}")
    print()
    print(f"Rules used: {len(summary['rule_usage'])}")
    for r_id, count in sorted(summary["rule_usage"].items(), key=lambda x: -x[1]):
        print(f"  {r_id}: {count}")
    print()
    print(f"Complete inputs: {summary['input_completeness'].get('COMPLETE', 0)}")
    print(f"Partial inputs: {summary['input_completeness'].get('PARTIAL', 0)}")
    print()
    print("Output:")
    print(f"  {QOS_DECISIONS_PATH}")
    print(f"  {POLICY_SUMMARY_PATH}")
    print()
    print("Phase 13 Status: COMPLETED")
    print("========================================")


if __name__ == "__main__":
    main()
