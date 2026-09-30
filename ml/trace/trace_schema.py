"""Structured schema definition for Decision Trace records (Phase 15)."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.trace.config import TRACE_SCHEMA_VERSION


@dataclass
class DecisionTrace:
    """Encapsulates the complete 7-stage lifecycle of a network traffic decision."""

    trace_id: str
    timestamp: str
    device_id: str
    flow_id: str

    # 5-Tuple Network Metadata
    src_ip: str = ""
    dst_ip: str = ""
    src_port: int = 0
    dst_port: int = 0
    protocol: str = "TCP"

    # Stage 1: Monitoring (Phase 4/6)
    monitoring: Dict[str, Any] = field(default_factory=dict)

    # Stage 2: Feature Extraction (Phase 7)
    features: Dict[str, Any] = field(default_factory=dict)

    # Stage 3: User Behavior Profiling (Phase 8)
    cluster_id: Optional[int] = None
    profile_label: str = ""
    user_profile: Dict[str, Any] = field(default_factory=dict)

    # Stage 4: Congestion Prediction (Phase 10)
    predicted_congestion_score: Optional[float] = None
    predicted_congestion_class: str = "UNKNOWN"
    congestion_prediction: Dict[str, Any] = field(default_factory=dict)

    # Stage 5: Traffic Classification (Phase 12)
    traffic_class: str = "OTHER"
    classification_confidence: float = 0.0
    classification_reason: str = ""

    # Stage 6: QoS Policy Decision (Phase 13)
    base_priority: str = "NORMAL"
    congestion_adjustment: int = 0
    user_profile_adjustment: int = 0
    final_priority: str = "NORMAL"
    policy_rule_id: str = ""
    policy_reason: str = ""
    input_completeness: str = "PARTIAL"

    # Stage 7: Network Control Action (Phase 14)
    control_action: str = ""
    control_target_class: str = ""
    control_interface: str = ""
    control_status: str = "SKIPPED"
    control_rule_identifier: str = ""
    dry_run: bool = True
    error_message: str = ""

    # Pipeline Stages Availability Tracking
    stages: Dict[str, bool] = field(default_factory=dict)

    # Structural Reasoning Chain
    reason_chain: List[str] = field(default_factory=list)

    # Trace Metadata
    trace_completeness: str = "PARTIAL"
    match_method: str = "EXACT_FLOW_ID"
    timestamp_difference_ms: float = 0.0
    trace_schema_version: str = TRACE_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to hierarchical nested dictionary (for JSONL export)."""
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "flow_id": self.flow_id,
            "network_5tuple": {
                "src_ip": self.src_ip,
                "dst_ip": self.dst_ip,
                "src_port": self.src_port,
                "dst_port": self.dst_port,
                "protocol": self.protocol,
            },
            "stages": self.stages,
            "stage_1_monitoring": self.monitoring,
            "stage_2_features": self.features,
            "stage_3_user_profile": {
                "cluster_id": self.cluster_id,
                "profile_label": self.profile_label,
                "metrics": self.user_profile,
            },
            "stage_4_congestion_prediction": {
                "predicted_score": self.predicted_congestion_score,
                "predicted_class": self.predicted_congestion_class,
                "details": self.congestion_prediction,
            },
            "stage_5_traffic_classification": {
                "traffic_class": self.traffic_class,
                "confidence": self.classification_confidence,
                "reason": self.classification_reason,
            },
            "stage_6_qos_policy": {
                "base_priority": self.base_priority,
                "congestion_adjustment": self.congestion_adjustment,
                "user_profile_adjustment": self.user_profile_adjustment,
                "final_priority": self.final_priority,
                "policy_rule_id": self.policy_rule_id,
                "policy_reason": self.policy_reason,
                "input_completeness": self.input_completeness,
            },
            "stage_7_network_control": {
                "action": self.control_action,
                "target_class": self.control_target_class,
                "interface": self.control_interface,
                "status": self.control_status,
                "rule_identifier": self.control_rule_identifier,
                "dry_run": self.dry_run,
                "error_message": self.error_message,
            },
            "reason_chain": self.reason_chain,
            "trace_metadata": {
                "trace_completeness": self.trace_completeness,
                "match_method": self.match_method,
                "timestamp_difference_ms": self.timestamp_difference_ms,
                "trace_schema_version": self.trace_schema_version,
            },
        }

    def to_flat_dict(self) -> Dict[str, Any]:
        """Convert trace to a flat dictionary for tabular CSV export."""
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "flow_id": self.flow_id,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "protocol": self.protocol,
            "throughput_mbps": self.features.get("throughput_mbps", self.monitoring.get("throughput")),
            "rtt_ms": self.features.get("rtt_ms", self.monitoring.get("rtt")),
            "packet_loss_percent": self.features.get("packet_loss_percent", self.monitoring.get("packet_loss")),
            "active_connections": self.features.get("active_connections", self.monitoring.get("active_connections")),
            "cluster_id": self.cluster_id,
            "profile_label": self.profile_label,
            "predicted_congestion_score": self.predicted_congestion_score,
            "predicted_congestion_class": self.predicted_congestion_class,
            "traffic_class": self.traffic_class,
            "classification_confidence": self.classification_confidence,
            "classification_reason": self.classification_reason,
            "base_priority": self.base_priority,
            "congestion_adjustment": self.congestion_adjustment,
            "user_profile_adjustment": self.user_profile_adjustment,
            "final_priority": self.final_priority,
            "policy_rule_id": self.policy_rule_id,
            "policy_reason": self.policy_reason,
            "input_completeness": self.input_completeness,
            "control_action": self.control_action,
            "control_target_class": self.control_target_class,
            "control_interface": self.control_interface,
            "control_status": self.control_status,
            "control_rule_identifier": self.control_rule_identifier,
            "dry_run": self.dry_run,
            "trace_completeness": self.trace_completeness,
            "match_method": self.match_method,
            "timestamp_difference_ms": self.timestamp_difference_ms,
        }

    def to_jsonl(self) -> str:
        """Serialize trace dictionary as a single-line JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
