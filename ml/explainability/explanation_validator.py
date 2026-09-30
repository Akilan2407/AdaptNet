"""Integrity and consistency validation for SHAP explanations (Phase 16)."""

import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explainability.config import (
    ADDITIVITY_TOLERANCE,
    CONSISTENCY_TOLERANCE,
    FEATURES_PER_STEP,
    RECURRENT_FEATURE_NAMES,
)

logger = logging.getLogger("ml.explainability.explanation_validator")

FORBIDDEN_TARGET_FIELDS = {
    "future_congestion_score",
    "future_congestion_class",
    "target_score",
    "label",
}


class ExplanationValidator:
    """Validates mathematical and structural invariants of SHAP explanation records."""

    @classmethod
    def validate_explanation(
        cls,
        explanation_dict: Dict[str, Any],
        expected_score: Optional[float] = None,
        additivity_tolerance: float = ADDITIVITY_TOLERANCE,
        consistency_tolerance: float = CONSISTENCY_TOLERANCE,
    ) -> List[str]:
        """Validate an individual SHAP explanation record.

        Returns:
            List of error strings (empty if valid).
        """
        errors = []

        # 1. Feature count check
        contributions = explanation_dict.get("feature_contributions", [])
        if len(contributions) != FEATURES_PER_STEP:
            errors.append(
                f"Feature count mismatch: expected {FEATURES_PER_STEP}, got {len(contributions)}"
            )

        # 2. Feature order & naming check
        feature_names = [c.get("feature_name") for c in contributions]
        missing_names = set(RECURRENT_FEATURE_NAMES) - set(feature_names)
        if missing_names:
            errors.append(f"Missing canonical feature names: {missing_names}")

        # 3. Additivity check (where supported by explainer)
        base_val = explanation_dict.get("base_value", 0.0)
        shap_sum = explanation_dict.get("shap_sum", 0.0)
        pred_score = explanation_dict.get("predicted_congestion_score", 0.0)
        explainer_type = explanation_dict.get("explainer_type", "")

        additivity_diff = abs((base_val + shap_sum) - pred_score)
        if explainer_type == "KernelExplainer" and additivity_diff > additivity_tolerance:
            errors.append(
                f"Additivity violation: base_val ({base_val:.4f}) + shap_sum ({shap_sum:.4f}) "
                f"differs from pred_score ({pred_score:.4f}) by {additivity_diff:.4f} > {additivity_tolerance}"
            )

        # 4. Prediction consistency check against stored Phase 15 score
        if expected_score is not None:
            score_diff = abs(pred_score - expected_score)
            if score_diff > consistency_tolerance:
                errors.append(
                    f"Prediction inconsistency: model output ({pred_score:.4f}) differs from "
                    f"stored Phase 15 score ({expected_score:.4f}) by {score_diff:.4f} > {consistency_tolerance}"
                )

        return errors

    @classmethod
    def validate_no_target_leakage(cls, input_keys: List[str]) -> List[str]:
        """Verify that forbidden target fields are not present in model input."""
        errors = []
        for key in input_keys:
            if key in FORBIDDEN_TARGET_FIELDS:
                errors.append(f"CRITICAL TARGET LEAKAGE: '{key}' found in model input features")
        return errors
