"""Model Explainability & Feature Attribution Module (SHAP) — Phase 16."""

from ml.explainability.config import (
    ADDITIVITY_TOLERANCE,
    CONSISTENCY_TOLERANCE,
    FEATURES_PER_STEP,
    RECURRENT_FEATURE_NAMES,
    SHAP_TIME_AGGREGATION,
    TIMESTEPS,
)
from ml.explainability.explanation_validator import ExplanationValidator
from ml.explainability.feature_mapper import FeatureMapper
from ml.explainability.global_explanation import GlobalExplainer
from ml.explainability.local_explanation import LocalExplainer
from ml.explainability.model_loader import ModelLoader
from ml.explainability.shap_explainer import SHAPExplainerWrapper
from ml.explainability.trace_explainer import TraceExplainerPipeline
from ml.explainability.visualization import ExplainabilityVisualizer

__all__ = [
    "ModelLoader",
    "FeatureMapper",
    "SHAPExplainerWrapper",
    "LocalExplainer",
    "GlobalExplainer",
    "ExplanationValidator",
    "ExplainabilityVisualizer",
    "TraceExplainerPipeline",
    "RECURRENT_FEATURE_NAMES",
    "FEATURES_PER_STEP",
    "TIMESTEPS",
    "SHAP_TIME_AGGREGATION",
    "ADDITIVITY_TOLERANCE",
    "CONSISTENCY_TOLERANCE",
]
