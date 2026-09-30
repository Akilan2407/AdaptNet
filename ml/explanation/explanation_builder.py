"""Structured Explanation Record and Builder (Phase 17)."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explanation.config import (
    STATUS_FAILED,
    STATUS_PARTIAL,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    TOP_FEATURES,
)
from ml.explanation.explanation_templates import ExplanationTemplates


@dataclass
class ExplanationRecord:
    """Encapsulates a verified, structured natural-language decision explanation."""

    trace_id: str
    timestamp: str
    device_id: str
    flow_id: str

    observations: Dict[str, Any] = field(default_factory=dict)
    prediction: Dict[str, Any] = field(default_factory=dict)
    feature_contributions: List[Dict[str, Any]] = field(default_factory=list)
    classification: Dict[str, Any] = field(default_factory=dict)
    policy_decision: Dict[str, Any] = field(default_factory=dict)
    network_action: Dict[str, Any] = field(default_factory=dict)

    cluster_id: Optional[int] = None
    profile_label: str = ""

    explanation_text: str = ""
    explanation_status: str = STATUS_SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        """Convert explanation record to structured nested dictionary (for JSONL export)."""
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "flow_id": self.flow_id,
            "observations": self.observations,
            "prediction": self.prediction,
            "feature_contributions": self.feature_contributions,
            "classification": self.classification,
            "policy_decision": self.policy_decision,
            "network_action": self.network_action,
            "user_profile": {
                "cluster_id": self.cluster_id,
                "profile_label": self.profile_label,
            },
            "explanation_status": self.explanation_status,
            "explanation_text": self.explanation_text,
        }

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert explanation record to flat tabular dictionary (for CSV export)."""
        top_1 = self.feature_contributions[0] if len(self.feature_contributions) > 0 else {}
        top_2 = self.feature_contributions[1] if len(self.feature_contributions) > 1 else {}
        top_3 = self.feature_contributions[2] if len(self.feature_contributions) > 2 else {}

        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "flow_id": self.flow_id,
            "predicted_congestion_score": self.prediction.get("score"),
            "predicted_congestion_class": self.prediction.get("class", "UNKNOWN"),
            "top_feature_1": top_1.get("feature", top_1.get("name")),
            "top_feature_1_value": top_1.get("value"),
            "top_feature_1_shap": top_1.get("shap_value"),
            "top_feature_2": top_2.get("feature", top_2.get("name")),
            "top_feature_2_value": top_2.get("value"),
            "top_feature_2_shap": top_2.get("shap_value"),
            "top_feature_3": top_3.get("feature", top_3.get("name")),
            "top_feature_3_value": top_3.get("value"),
            "top_feature_3_shap": top_3.get("shap_value"),
            "traffic_class": self.classification.get("class", "OTHER"),
            "classification_reason": self.classification.get("reason", ""),
            "policy_rule_id": self.policy_decision.get("rule_id", ""),
            "final_priority": self.policy_decision.get("final_priority", "NORMAL"),
            "policy_reason": self.policy_decision.get("reason", ""),
            "control_action": self.network_action.get("action", ""),
            "control_target_class": self.network_action.get("target_class", ""),
            "control_status": self.network_action.get("status", "SKIPPED"),
            "explanation_status": self.explanation_status,
            "explanation_text": self.explanation_text,
        }

    def to_jsonl(self) -> str:
        """Serialize explanation dictionary as a single-line JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class ExplanationBuilder:
    """Builds validated ExplanationRecord instances from trace and SHAP outputs."""

    @classmethod
    def build_record(
        cls,
        trace_record: Dict[str, Any],
        shap_record: Optional[Dict[str, Any]] = None,
        top_n: int = TOP_FEATURES,
    ) -> ExplanationRecord:
        """Construct ExplanationRecord from Phase 15 and Phase 16 records."""
        trace_id = str(trace_record.get("trace_id", ""))
        ts = str(trace_record.get("timestamp", ""))
        device_id = str(trace_record.get("device_id", ""))
        flow_id = str(trace_record.get("flow_id", ""))

        # 1. Observations
        obs = {
            "throughput_mbps": trace_record.get("throughput_mbps"),
            "rtt_ms": trace_record.get("rtt_ms"),
            "packet_loss_percent": trace_record.get("packet_loss_percent"),
            "active_connections": trace_record.get("active_connections"),
            "total_flow_count": trace_record.get("total_flow_count", 1),
        }
        # Clean NaNs
        clean_obs = {k: v for k, v in obs.items() if pd.notna(v) and v is not None}

        # 2. Prediction
        score = trace_record.get("predicted_congestion_score")
        if pd.isna(score) or score is None:
            pred_score = None
            pred_class = str(trace_record.get("predicted_congestion_class", "UNKNOWN")).strip().upper()
        else:
            pred_score = float(score)
            pred_class = str(trace_record.get("predicted_congestion_class", "UNKNOWN")).strip().upper()

        # 3. SHAP contributions
        shap_contribs = []
        if shap_record:
            raw_contribs = shap_record.get("top_contributors") or shap_record.get("features", [])
            for c in raw_contribs[:top_n]:
                shap_contribs.append({
                    "feature": c.get("feature", c.get("name")),
                    "value": c.get("value"),
                    "shap_value": c.get("shap_value"),
                    "direction": c.get("direction"),
                })

        # 4. Classification
        traffic_class = str(trace_record.get("traffic_class", "OTHER")).strip().upper()
        raw_reason = trace_record.get("classification_reason", "")
        class_reason = str(raw_reason).strip() if pd.notna(raw_reason) and str(raw_reason).strip().lower() != "nan" else ""
        classification = {
            "class": traffic_class,
            "confidence": float(trace_record.get("classification_confidence", 1.0) or 1.0),
            "reason": class_reason,
        }

        # 5. User Profile
        raw_cid = trace_record.get("cluster_id")
        cluster_id = int(raw_cid) if pd.notna(raw_cid) and raw_cid is not None else None
        profile_label = str(trace_record.get("profile_label", ""))

        # 6. Policy
        rule_id = str(trace_record.get("policy_rule_id", ""))
        final_prio = str(trace_record.get("final_priority", "NORMAL")).strip().upper()
        base_prio = str(trace_record.get("base_priority", "NORMAL")).strip().upper()
        policy_reason = str(trace_record.get("policy_reason", ""))
        policy = {
            "rule_id": rule_id,
            "base_priority": base_prio,
            "final_priority": final_prio,
            "reason": policy_reason,
        }

        # 7. Network Control
        ctrl_action = str(trace_record.get("control_action", ""))
        ctrl_target = str(trace_record.get("control_target_class", ""))
        ctrl_status = str(trace_record.get("control_status", "SKIPPED")).strip().upper()
        ctrl_iface = str(trace_record.get("control_interface", ""))
        network_action = {
            "action": ctrl_action,
            "target_class": ctrl_target,
            "status": ctrl_status,
            "interface": ctrl_iface,
        }

        # Determine Explanation Status
        has_pred = pred_score is not None and pred_class != "UNKNOWN"
        has_shap = len(shap_contribs) > 0
        has_ctrl = ctrl_status in ("SUCCESS", "DRY_RUN")

        if has_pred and has_shap and has_ctrl:
            explanation_status = STATUS_SUCCESS
        elif rule_id:
            explanation_status = STATUS_PARTIAL
        else:
            explanation_status = STATUS_SKIPPED

        # Synthesize Explanation Text
        explanation_text = ExplanationTemplates.assemble_full_explanation(
            trace_id=trace_id,
            device_id=device_id,
            flow_id=flow_id,
            observations=clean_obs,
            pred_score=pred_score,
            pred_class=pred_class,
            shap_contributions=shap_contribs,
            traffic_class=traffic_class,
            classification_reason=class_reason,
            policy_rule_id=rule_id,
            final_priority=final_prio,
            base_priority=base_prio,
            policy_reason=policy_reason,
            cluster_id=cluster_id,
            profile_label=profile_label,
            control_action=ctrl_action,
            control_target_class=ctrl_target,
            control_status=ctrl_status,
            control_interface=ctrl_iface,
        )

        return ExplanationRecord(
            trace_id=trace_id,
            timestamp=ts,
            device_id=device_id,
            flow_id=flow_id,
            observations=clean_obs,
            prediction={"score": pred_score, "class": pred_class},
            feature_contributions=shap_contribs,
            classification=classification,
            policy_decision=policy,
            network_action=network_action,
            cluster_id=cluster_id,
            profile_label=profile_label,
            explanation_text=explanation_text,
            explanation_status=explanation_status,
        )
