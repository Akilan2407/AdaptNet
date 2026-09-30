"""Core Trace Builder orchestrating end-to-end multi-stage trace creation (Phase 15)."""

from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.trace.config import (
    COMPLETENESS_COMPLETE,
    COMPLETENESS_INCOMPLETE,
    COMPLETENESS_PARTIAL,
    DEFAULT_CLASSIFICATION_PATH,
    DEFAULT_CONGESTION_PATH,
    DEFAULT_CONTROL_PATH,
    DEFAULT_FEATURES_PATH,
    DEFAULT_MONITORING_PATH,
    DEFAULT_POLICY_PATH,
    DEFAULT_PROFILES_PATH,
    TRACE_TIMESTAMP_TOLERANCE_SECONDS,
)
from ml.trace.trace_matcher import TraceMatcher
from ml.trace.trace_schema import DecisionTrace

FLOW_5TUPLE_REGEX = re.compile(
    r"^(?P<device>[^_]+)_(?P<src_ip>[^:]+):(?P<src_port>\d+)->(?P<dst_ip>[^:]+):(?P<dst_port>\d+)_(?P<protocol>[A-Za-z]+)$"
)


class TraceBuilder:
    """Orchestrates ingestion, matching, and synthesis of end-to-end Decision Traces."""

    def __init__(
        self,
        monitoring_path: Optional[Path] = None,
        features_path: Optional[Path] = None,
        profiles_path: Optional[Path] = None,
        congestion_path: Optional[Path] = None,
        classification_path: Optional[Path] = None,
        policy_path: Optional[Path] = None,
        control_path: Optional[Path] = None,
        tolerance_seconds: float = TRACE_TIMESTAMP_TOLERANCE_SECONDS,
    ):
        self.monitoring_path = monitoring_path or DEFAULT_MONITORING_PATH
        self.features_path = features_path or DEFAULT_FEATURES_PATH
        self.profiles_path = profiles_path or DEFAULT_PROFILES_PATH
        self.congestion_path = congestion_path or DEFAULT_CONGESTION_PATH
        self.classification_path = classification_path or DEFAULT_CLASSIFICATION_PATH
        self.policy_path = policy_path or DEFAULT_POLICY_PATH
        self.control_path = control_path or DEFAULT_CONTROL_PATH
        self.matcher = TraceMatcher(tolerance_seconds=tolerance_seconds)

    def load_datasets(self) -> Dict[str, pd.DataFrame]:
        """Load all 7 stage datasets into pandas DataFrames."""
        datasets = {}
        paths = {
            "monitoring": self.monitoring_path,
            "features": self.features_path,
            "profiles": self.profiles_path,
            "congestion": self.congestion_path,
            "classification": self.classification_path,
            "policy": self.policy_path,
            "control": self.control_path,
        }

        for stage, path in paths.items():
            if Path(path).exists():
                datasets[stage] = pd.read_csv(path)
            else:
                datasets[stage] = pd.DataFrame()

        return datasets

    @staticmethod
    def parse_flow_5tuple(flow_id: str) -> Dict[str, Any]:
        """Extract 5-tuple components from flow_id string."""
        if not flow_id:
            return {"src_ip": "", "dst_ip": "", "src_port": 0, "dst_port": 0, "protocol": "TCP"}
        m = FLOW_5TUPLE_REGEX.match(str(flow_id).strip())
        if m:
            gd = m.groupdict()
            return {
                "src_ip": gd["src_ip"],
                "dst_ip": gd["dst_ip"],
                "src_port": int(gd["src_port"]),
                "dst_port": int(gd["dst_port"]),
                "protocol": gd["protocol"].upper(),
            }
        return {"src_ip": "", "dst_ip": "", "src_port": 0, "dst_port": 0, "protocol": "TCP"}

    @staticmethod
    def build_reason_chain(
        device_id: str,
        profile_label: str,
        traffic_class: str,
        pred_class: str,
        pred_score: Optional[float],
        base_priority: str,
        cong_adj: int,
        user_adj: int,
        final_priority: str,
        policy_rule_id: str,
        control_action: str,
        control_class: str,
        control_status: str,
        throughput_mbps: float = 0.0,
        cluster_id: Optional[int] = None,
    ) -> List[str]:
        """Synthesize structured human-readable reason chain across stages."""
        return [
            f"device_id={device_id} (profile='{profile_label}', cluster={cluster_id})",
            f"throughput_mbps={throughput_mbps}",
            f"traffic_class={traffic_class}",
            f"predicted_congestion={pred_class} (score={pred_score})",
            f"qos_priority={final_priority} (base={base_priority}, rule={policy_rule_id}, cong_adj={cong_adj}, user_adj={user_adj})",
            f"control_action={control_action} (target_class={control_class}, status={control_status})",
        ]

    def build_traces(self) -> List[DecisionTrace]:
        """Build deterministic, linked DecisionTrace instances for all decisions."""
        dfs = self.load_datasets()
        policy_df = dfs.get("policy", pd.DataFrame())

        if policy_df.empty:
            return []

        # Sort deterministically by (timestamp, device_id, flow_id) to guarantee stable trace IDs
        sort_cols = [c for c in ["timestamp", "device_id", "flow_id"] if c in policy_df.columns]
        sorted_policy_df = policy_df.sort_values(by=sort_cols).reset_index(drop=True)

        monitoring_df = dfs.get("monitoring", pd.DataFrame())
        features_df = dfs.get("features", pd.DataFrame())
        profiles_df = dfs.get("profiles", pd.DataFrame())
        congestion_df = dfs.get("congestion", pd.DataFrame())
        classification_df = dfs.get("classification", pd.DataFrame())
        control_df = dfs.get("control", pd.DataFrame())

        traces: List[DecisionTrace] = []

        for idx, row in sorted_policy_df.iterrows():
            trace_id = f"TRC-{idx + 1:06d}"
            ts = str(row.get("timestamp", ""))
            device_id = str(row.get("device_id", ""))
            flow_id = str(row.get("flow_id", ""))

            # 5-Tuple
            tuple_dict = self.parse_flow_5tuple(flow_id)

            # Stage 1: Monitoring
            mon_record, mon_method, mon_diff_ms = self.matcher.match_monitoring_record(
                flow_id, device_id, ts, monitoring_df
            )
            has_mon = mon_record is not None

            # Stage 2: Feature Extraction
            feat_record, feat_method, feat_diff_ms = self.matcher.match_features_record(
                flow_id, ts, features_df
            )
            has_feat = feat_record is not None

            # Stage 3: User Behavior Profile
            prof_record, prof_method = self.matcher.match_profile_record(device_id, profiles_df)
            has_prof = prof_record is not None
            cluster_id = prof_record.get("cluster_id") if prof_record else row.get("cluster_id")
            if pd.notna(cluster_id):
                try:
                    cluster_id = int(cluster_id)
                except Exception:
                    cluster_id = None
            else:
                cluster_id = None
            profile_label = str(prof_record.get("profile_label", "")) if prof_record else ""

            # Stage 4: Congestion Prediction
            cong_record, cong_method, cong_diff_ms = self.matcher.match_congestion_prediction(
                device_id, ts, congestion_df
            )
            has_cong = cong_record is not None
            pred_score = (
                float(cong_record["predicted_score"])
                if cong_record and pd.notna(cong_record.get("predicted_score"))
                else (float(row["predicted_congestion_score"]) if pd.notna(row.get("predicted_congestion_score")) else None)
            )
            pred_class = (
                str(cong_record["predicted_class"]).strip().upper()
                if cong_record and pd.notna(cong_record.get("predicted_class"))
                else str(row.get("predicted_congestion_class", "UNKNOWN")).strip().upper()
            )

            # Stage 5: Traffic Classification
            class_record, class_method, class_diff_ms = self.matcher.match_classification_record(
                flow_id, ts, classification_df
            )
            has_class = class_record is not None
            traffic_class = str(row.get("traffic_class", "OTHER")).strip().upper()
            conf = float(row.get("classification_confidence", 0.0))
            reason = str(row.get("classification_reason", ""))

            # Stage 6: QoS Policy Decision
            base_prio = str(row.get("base_priority", "NORMAL")).strip().upper()
            cong_adj = int(row.get("congestion_adjustment", 0))
            user_adj = int(row.get("user_profile_adjustment", 0))
            final_prio = str(row.get("final_priority", "NORMAL")).strip().upper()
            rule_id = str(row.get("policy_rule_id", ""))
            policy_reason = str(row.get("policy_reason", ""))
            input_comp = str(row.get("input_completeness", "PARTIAL")).strip().upper()

            # Stage 7: Network Control Action
            ctrl_record, ctrl_method, ctrl_diff_ms = self.matcher.match_control_record(
                flow_id, ts, control_df
            )
            has_ctrl = ctrl_record is not None
            ctrl_action = str(ctrl_record.get("action", "")) if ctrl_record else ""
            ctrl_target = str(ctrl_record.get("target_class", "")) if ctrl_record else ""
            ctrl_iface = str(ctrl_record.get("interface", "")) if ctrl_record else ""
            ctrl_status = str(ctrl_record.get("status", "SKIPPED")) if ctrl_record else "SKIPPED"
            ctrl_rule_id = str(ctrl_record.get("rule_identifier", "")) if ctrl_record else ""
            dry_run = bool(ctrl_record.get("dry_run", True)) if ctrl_record else True
            err_msg = str(ctrl_record.get("error_message", "")) if ctrl_record and pd.notna(ctrl_record.get("error_message")) else ""

            # Stage availability dict
            stages = {
                "monitoring": has_mon,
                "features": has_feat,
                "profile": has_prof,
                "congestion": has_cong or (pred_class != "UNKNOWN"),
                "classification": has_class or (traffic_class != "OTHER"),
                "policy": True,
                "control": has_ctrl,
            }

            # Trace completeness evaluation
            if all(stages.values()) and input_comp == "COMPLETE":
                completeness = COMPLETENESS_COMPLETE
            elif stages["policy"] and (stages["classification"] or stages["features"]):
                completeness = COMPLETENESS_PARTIAL
            else:
                completeness = COMPLETENESS_INCOMPLETE

            # Overall match method
            match_method = mon_method if mon_method != "UNMATCHED" else class_method
            total_diff_ms = max(mon_diff_ms, feat_diff_ms, cong_diff_ms, class_diff_ms, ctrl_diff_ms)

            # Build reasoning chain
            reason_chain = self.build_reason_chain(
                device_id=device_id,
                profile_label=profile_label,
                traffic_class=traffic_class,
                pred_class=pred_class,
                pred_score=pred_score,
                base_priority=base_prio,
                cong_adj=cong_adj,
                user_adj=user_adj,
                final_priority=final_prio,
                policy_rule_id=rule_id,
                control_action=ctrl_action,
                control_class=ctrl_target,
                control_status=ctrl_status,
                throughput_mbps=float(feat_record.get("throughput_mbps", mon_record.get("throughput", 0.0) if mon_record else 0.0)),
                cluster_id=cluster_id,
            )

            trace = DecisionTrace(
                trace_id=trace_id,
                timestamp=ts,
                device_id=device_id,
                flow_id=flow_id,
                src_ip=tuple_dict["src_ip"],
                dst_ip=tuple_dict["dst_ip"],
                src_port=tuple_dict["src_port"],
                dst_port=tuple_dict["dst_port"],
                protocol=tuple_dict["protocol"],
                monitoring=mon_record or {},
                features=feat_record or {},
                cluster_id=cluster_id,
                profile_label=profile_label,
                user_profile=prof_record or {},
                predicted_congestion_score=pred_score,
                predicted_congestion_class=pred_class,
                congestion_prediction=cong_record or {},
                traffic_class=traffic_class,
                classification_confidence=conf,
                classification_reason=reason,
                base_priority=base_prio,
                congestion_adjustment=cong_adj,
                user_profile_adjustment=user_adj,
                final_priority=final_prio,
                policy_rule_id=rule_id,
                policy_reason=policy_reason,
                input_completeness=input_comp,
                control_action=ctrl_action,
                control_target_class=ctrl_target,
                control_interface=ctrl_iface,
                control_status=ctrl_status,
                control_rule_identifier=ctrl_rule_id,
                dry_run=dry_run,
                error_message=err_msg,
                stages=stages,
                reason_chain=reason_chain,
                trace_completeness=completeness,
                match_method=match_method,
                timestamp_difference_ms=round(total_diff_ms, 2),
            )
            traces.append(trace)

        return traces
