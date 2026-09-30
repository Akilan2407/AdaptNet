"""Explanation fidelity and consistency validator (Phase 17)."""

from typing import Any, Dict, List, Optional
import pandas as pd


class ExplanationValidator:
    """Verifies that natural-language explanations faithfully reflect recorded stage data."""

    @classmethod
    def validate_record_fidelity(
        cls,
        record: Any,
        expected_trace: Dict[str, Any],
        expected_shap: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Validate an ExplanationRecord against ground-truth Phase 15 and 16 records.

        Returns:
            List of discrepancy error strings (empty if valid).
        """
        errors = []

        # 1. Trace ID match
        if record.trace_id != str(expected_trace.get("trace_id")):
            errors.append(f"Trace ID mismatch: got '{record.trace_id}', expected '{expected_trace.get('trace_id')}'")

        # 2. Prediction fidelity
        exp_score = expected_trace.get("predicted_congestion_score")
        if pd.notna(exp_score) and exp_score is not None:
            if record.prediction.get("score") is None:
                errors.append(f"Trace {record.trace_id}: Missing prediction score, expected {exp_score}")
            elif abs(float(record.prediction["score"]) - float(exp_score)) > 0.001:
                errors.append(
                    f"Trace {record.trace_id}: Score mismatch: got {record.prediction['score']}, expected {exp_score}"
                )

        # 3. Policy fidelity
        exp_rule = str(expected_trace.get("policy_rule_id", ""))
        exp_prio = str(expected_trace.get("final_priority", "")).strip().upper()
        if record.policy_decision.get("rule_id") != exp_rule:
            errors.append(f"Trace {record.trace_id}: Rule mismatch: got '{record.policy_decision.get('rule_id')}', expected '{exp_rule}'")
        if record.policy_decision.get("final_priority") != exp_prio:
            errors.append(f"Trace {record.trace_id}: Priority mismatch: got '{record.policy_decision.get('final_priority')}', expected '{exp_prio}'")

        # 4. Control fidelity
        exp_status = str(expected_trace.get("control_status", "")).strip().upper()
        if record.network_action.get("status") != exp_status:
            errors.append(f"Trace {record.trace_id}: Control status mismatch: got '{record.network_action.get('status')}', expected '{exp_status}'")

        # 5. SHAP fidelity
        if expected_shap and record.feature_contributions:
            shap_list = expected_shap.get("top_contributors") or expected_shap.get("features", [])
            if shap_list:
                exp_top_feat = shap_list[0].get("feature", shap_list[0].get("name"))
                rec_top_feat = record.feature_contributions[0].get("feature")
                if exp_top_feat and rec_top_feat and exp_top_feat != rec_top_feat:
                    errors.append(f"Trace {record.trace_id}: Top SHAP feature mismatch: got '{rec_top_feat}', expected '{exp_top_feat}'")

        return errors
