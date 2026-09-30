"""Trace integrity and cross-stage consistency validation for Phase 15."""

from pathlib import Path
import sys
from typing import Any, Dict, List
import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.trace.config import (
    COMPLETENESS_COMPLETE,
    COMPLETENESS_INCOMPLETE,
    COMPLETENESS_PARTIAL,
    PRIORITY_TO_CONTROL_CLASS,
)
from ml.trace.trace_schema import DecisionTrace

VALID_PRIORITIES = {"HIGH", "MEDIUM", "NORMAL", "LOW"}
VALID_CONGESTION_CLASSES = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
VALID_TRAFFIC_CLASSES = {"REAL_TIME", "INTERACTIVE", "WEB", "DNS", "BULK_TRANSFER", "OTHER"}
VALID_CONTROL_STATUSES = {"SUCCESS", "FAILED", "SKIPPED", "DRY_RUN", ""}


class TraceValidator:
    """Validates the integrity, consistency, and completeness of Decision Traces."""

    @classmethod
    def validate_trace(cls, trace: DecisionTrace) -> List[str]:
        """Validate an individual DecisionTrace instance.

        Returns:
            List of error strings (empty if valid).
        """
        errors = []

        if not trace.trace_id or not trace.trace_id.startswith("TRC-"):
            errors.append(f"Invalid trace_id format: '{trace.trace_id}'")

        if not trace.flow_id or len(trace.flow_id.strip()) == 0:
            errors.append(f"Trace {trace.trace_id}: Missing flow_id")

        if not trace.timestamp:
            errors.append(f"Trace {trace.trace_id}: Missing timestamp")

        if trace.final_priority not in VALID_PRIORITIES:
            errors.append(f"Trace {trace.trace_id}: Invalid final_priority '{trace.final_priority}'")

        if trace.predicted_congestion_class not in VALID_CONGESTION_CLASSES:
            errors.append(f"Trace {trace.trace_id}: Invalid congestion class '{trace.predicted_congestion_class}'")

        if trace.traffic_class not in VALID_TRAFFIC_CLASSES:
            errors.append(f"Trace {trace.trace_id}: Invalid traffic class '{trace.traffic_class}'")

        if trace.control_status not in VALID_CONTROL_STATUSES:
            errors.append(f"Trace {trace.trace_id}: Invalid control status '{trace.control_status}'")

        # Cross-stage consistency: Policy Priority vs Control Class
        if trace.control_target_class and trace.final_priority:
            expected_class = PRIORITY_TO_CONTROL_CLASS.get(trace.final_priority)
            if expected_class and trace.control_target_class != expected_class:
                errors.append(
                    f"PRIORITY_CONTROL_MISMATCH in {trace.trace_id}: "
                    f"priority '{trace.final_priority}' expected '{expected_class}', "
                    f"got control target class '{trace.control_target_class}'"
                )

        # Inconsistency: Status SUCCESS/DRY_RUN but empty control action
        if trace.control_status in ("SUCCESS", "DRY_RUN") and not trace.control_action:
            errors.append(f"Trace {trace.trace_id}: Control status is '{trace.control_status}' but action is empty")

        return errors

    @classmethod
    def validate_traces_collection(cls, traces: List[DecisionTrace]) -> Dict[str, Any]:
        """Validate a collection of DecisionTrace records for collective invariants.

        Returns:
            Validation summary dictionary.
        """
        total = len(traces)
        all_errors: List[str] = []
        seen_ids = set()

        for trace in traces:
            # Check ID uniqueness
            if trace.trace_id in seen_ids:
                all_errors.append(f"Duplicate trace_id detected: '{trace.trace_id}'")
            seen_ids.add(trace.trace_id)

            # Individual trace validation
            errs = cls.validate_trace(trace)
            all_errors.extend(errs)

        is_valid = len(all_errors) == 0
        complete_count = sum(1 for t in traces if t.trace_completeness == COMPLETENESS_COMPLETE)
        partial_count = sum(1 for t in traces if t.trace_completeness == COMPLETENESS_PARTIAL)
        incomplete_count = sum(1 for t in traces if t.trace_completeness == COMPLETENESS_INCOMPLETE)

        return {
            "is_valid": is_valid,
            "total_traces": total,
            "unique_traces": len(seen_ids),
            "complete_traces": complete_count,
            "partial_traces": partial_count,
            "incomplete_traces": incomplete_count,
            "errors": all_errors,
        }
