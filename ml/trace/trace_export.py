"""Serialization and dataset export services for Phase 15 Decision Traces."""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.trace.config import (
    COMPLETENESS_COMPLETE,
    COMPLETENESS_INCOMPLETE,
    COMPLETENESS_PARTIAL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SUMMARY_JSON,
    DEFAULT_TRACES_CSV,
    DEFAULT_TRACES_JSONL,
    MATCH_EXACT_DEVICE_FLOW,
    MATCH_EXACT_FLOW_ID,
    MATCH_FLOW_TIMESTAMP_TOLERANCE,
    MATCH_UNMATCHED,
)
from ml.trace.trace_schema import DecisionTrace


class TraceExporter:
    """Exports DecisionTrace objects to CSV, JSONL, and summary statistics."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.output_dir / "decision_traces.csv"
        self.jsonl_path = self.output_dir / "decision_traces.jsonl"
        self.summary_path = self.output_dir / "trace_summary.json"

    def export_csv(self, traces: List[DecisionTrace]) -> Path:
        """Export tabular trace records to CSV."""
        rows = [t.to_flat_dict() for t in traces]
        df = pd.DataFrame(rows)
        df.to_csv(self.csv_path, index=False)
        return self.csv_path

    def export_jsonl(self, traces: List[DecisionTrace]) -> Path:
        """Export structured nested trace records to JSON Lines."""
        with open(self.jsonl_path, "w", encoding="utf-8") as f:
            for t in traces:
                f.write(t.to_jsonl() + "\n")
        return self.jsonl_path

    def generate_summary(self, traces: List[DecisionTrace]) -> Dict[str, Any]:
        """Compute comprehensive match rates, completeness counts, and stage statistics."""
        total = len(traces)
        if total == 0:
            return {"total_traces": 0}

        complete_count = sum(1 for t in traces if t.trace_completeness == COMPLETENESS_COMPLETE)
        partial_count = sum(1 for t in traces if t.trace_completeness == COMPLETENESS_PARTIAL)
        incomplete_count = sum(1 for t in traces if t.trace_completeness == COMPLETENESS_INCOMPLETE)

        # Stage matches
        mon_matches = sum(1 for t in traces if t.stages.get("monitoring", False))
        feat_matches = sum(1 for t in traces if t.stages.get("features", False))
        prof_matches = sum(1 for t in traces if t.stages.get("profile", False))
        cong_matches = sum(1 for t in traces if t.stages.get("congestion", False))
        class_matches = sum(1 for t in traces if t.stages.get("classification", False))
        policy_matches = sum(1 for t in traces if t.stages.get("policy", False))
        ctrl_matches = sum(1 for t in traces if t.stages.get("control", False))

        # Match methods
        exact_matches = sum(1 for t in traces if t.match_method in (MATCH_EXACT_FLOW_ID, MATCH_EXACT_DEVICE_FLOW))
        tolerance_matches = sum(1 for t in traces if t.match_method == MATCH_FLOW_TIMESTAMP_TOLERANCE)
        unmatched = sum(1 for t in traces if t.match_method == MATCH_UNMATCHED)

        summary = {
            "total_traces": total,
            "complete_traces": complete_count,
            "partial_traces": partial_count,
            "incomplete_traces": incomplete_count,
            "monitoring_match_rate": round(mon_matches / total * 100.0, 2),
            "feature_match_rate": round(feat_matches / total * 100.0, 2),
            "profile_match_rate": round(prof_matches / total * 100.0, 2),
            "congestion_match_rate": round(cong_matches / total * 100.0, 2),
            "classification_match_rate": round(class_matches / total * 100.0, 2),
            "policy_match_rate": round(policy_matches / total * 100.0, 2),
            "control_match_rate": round(ctrl_matches / total * 100.0, 2),
            "exact_match_count": exact_matches,
            "timestamp_tolerance_match_count": tolerance_matches,
            "unmatched_count": unmatched,
        }

        with open(self.summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary

    def export_all(self, traces: List[DecisionTrace]) -> Dict[str, Any]:
        """Execute full serialization: CSV, JSONL, and summary JSON."""
        self.export_csv(traces)
        self.export_jsonl(traces)
        return self.generate_summary(traces)
