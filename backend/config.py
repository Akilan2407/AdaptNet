"""Configuration settings and data paths for Phase 18 Flask Backend REST API."""

import os
from pathlib import Path
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Server Configuration
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", 5001))
DEBUG = False

# API Version & Prefix
API_PREFIX = "/api"


class Config:
    """Flask application configuration class."""
    API_HOST = os.environ.get("HOST", "0.0.0.0")
    API_PORT = int(os.environ.get("PORT", 5001))
    API_PREFIX = "/api"
    DEBUG = False
    TESTING = False
    PROJECT_ROOT = PROJECT_ROOT


# Concrete Data Paths (Phases 1-17 Outputs)
# Monitoring & Features (Phases 4-7)
MONITORING_METRICS_CSV = PROJECT_ROOT / "data" / "monitoring" / "network_metrics.csv"
FEATURES_CSV = PROJECT_ROOT / "data" / "features" / "network_features.csv"

# Behavior Profiling (Phase 8)
BEHAVIOR_PROFILES_CSV = PROJECT_ROOT / "data" / "profiling" / "behavior_profiles.csv"
CLUSTER_SUMMARY_CSV = PROJECT_ROOT / "data" / "profiling" / "cluster_summary.csv"
CLUSTERING_EVALUATION_CSV = PROJECT_ROOT / "data" / "profiling" / "clustering_evaluation.csv"
CLUSTERING_FEATURES_JSON = PROJECT_ROOT / "data" / "profiling" / "clustering_features.json"

# Congestion Prediction & Dataset (Phases 9-11)
CONGESTION_PREDICTIONS_CSV = PROJECT_ROOT / "data" / "congestion" / "test_predictions.csv"
CONGESTION_DATASET_CSV = PROJECT_ROOT / "data" / "congestion" / "congestion_dataset.csv"
CONGESTION_STATS_JSON = PROJECT_ROOT / "data" / "congestion" / "dataset_statistics.json"
CONGESTION_MODEL_EVAL_JSON = PROJECT_ROOT / "data" / "congestion" / "model_evaluation.json"
CONGESTION_METADATA_JSON = PROJECT_ROOT / "data" / "congestion" / "model_metadata.json"
BASELINE_COMPARISON_CSV = PROJECT_ROOT / "data" / "baseline" / "model_comparison.csv"
BASELINE_SUMMARY_JSON = PROJECT_ROOT / "data" / "baseline" / "baseline_summary.json"

# Traffic Classification (Phase 12)
CLASSIFIED_FLOWS_CSV = PROJECT_ROOT / "data" / "classification" / "classified_flows.csv"
CLASSIFICATION_SUMMARY_JSON = PROJECT_ROOT / "data" / "classification" / "classification_summary.json"
CLASSIFICATION_RULES_JSON = PROJECT_ROOT / "data" / "classification" / "classification_rules.json"

# QoS Policy Engine (Phase 13)
POLICY_DECISIONS_CSV = PROJECT_ROOT / "data" / "policy" / "qos_decisions.csv"
POLICY_SUMMARY_JSON = PROJECT_ROOT / "data" / "policy" / "policy_summary.json"

# Adaptive Traffic Control (Phase 14)
CONTROL_ACTIONS_CSV = PROJECT_ROOT / "data" / "control" / "control_actions.csv"
CONTROL_STATE_CSV = PROJECT_ROOT / "data" / "control" / "control_state.csv"
CONTROL_SUMMARY_JSON = PROJECT_ROOT / "data" / "control" / "control_summary.json"

# Decision Trace Module (Phase 15)
DECISION_TRACES_CSV = PROJECT_ROOT / "data" / "trace" / "decision_traces.csv"
DECISION_TRACES_JSONL = PROJECT_ROOT / "data" / "trace" / "decision_traces.jsonl"
TRACE_SUMMARY_JSON = PROJECT_ROOT / "data" / "trace" / "trace_summary.json"

# SHAP Explainability Module (Phase 16)
EXPLAINABILITY_LOCAL_CSV = PROJECT_ROOT / "data" / "explainability" / "local_shap_explanations.csv"
EXPLAINABILITY_LOCAL_JSONL = PROJECT_ROOT / "data" / "explainability" / "local_shap_explanations.jsonl"
EXPLAINABILITY_GLOBAL_CSV = PROJECT_ROOT / "data" / "explainability" / "global_shap_importance.csv"
EXPLAINABILITY_SUMMARY_JSON = PROJECT_ROOT / "data" / "explainability" / "explainability_summary.json"
EXPLANATION_RECORDS_JSONL = PROJECT_ROOT / "data" / "explainability" / "explanation_records.jsonl"

# Natural-Language Explanations (Phase 17)
NATURAL_LANGUAGE_CSV = PROJECT_ROOT / "data" / "explanations" / "natural_language_explanations.csv"
NATURAL_LANGUAGE_JSONL = PROJECT_ROOT / "data" / "explanations" / "natural_language_explanations.jsonl"
EXPLANATION_SUMMARY_JSON = PROJECT_ROOT / "data" / "explanations" / "explanation_summary.json"
EXPLANATION_REPORT_TXT = PROJECT_ROOT / "data" / "explanations" / "explanation_report.txt"
