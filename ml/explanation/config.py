"""Configuration constants, paths, and thresholds for Phase 17 Natural-Language Explanation Module."""

from pathlib import Path
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Phase 15 Inputs (Decision Traces)
DEFAULT_TRACES_CSV = PROJECT_ROOT / "data" / "trace" / "decision_traces.csv"
DEFAULT_TRACES_JSONL = PROJECT_ROOT / "data" / "trace" / "decision_traces.jsonl"

# Phase 16 Inputs (SHAP Explanations)
DEFAULT_SHAP_LOCAL_CSV = PROJECT_ROOT / "data" / "explainability" / "local_shap_explanations.csv"
DEFAULT_SHAP_LOCAL_JSONL = PROJECT_ROOT / "data" / "explainability" / "local_shap_explanations.jsonl"
DEFAULT_EXPLANATION_RECORDS_JSONL = PROJECT_ROOT / "data" / "explainability" / "explanation_records.jsonl"
DEFAULT_SHAP_SUMMARY_JSON = PROJECT_ROOT / "data" / "explainability" / "explainability_summary.json"
DEFAULT_SHAP_GLOBAL_CSV = PROJECT_ROOT / "data" / "explainability" / "global_shap_importance.csv"

# Phase 13 & Phase 14 Direct Inputs
DEFAULT_POLICY_CSV = PROJECT_ROOT / "data" / "policy" / "qos_decisions.csv"
DEFAULT_CONTROL_CSV = PROJECT_ROOT / "data" / "control" / "control_actions.csv"

# Phase 17 Outputs
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "explanations"
DEFAULT_EXPLANATIONS_CSV = DEFAULT_OUTPUT_DIR / "natural_language_explanations.csv"
DEFAULT_EXPLANATIONS_JSONL = DEFAULT_OUTPUT_DIR / "natural_language_explanations.jsonl"
DEFAULT_REPORT_TXT = DEFAULT_OUTPUT_DIR / "explanation_report.txt"
DEFAULT_SUMMARY_JSON = DEFAULT_OUTPUT_DIR / "explanation_summary.json"
DEFAULT_STATUS_PLOT = DEFAULT_OUTPUT_DIR / "explanation_status.png"
DEFAULT_TOP_SHAP_PLOT = DEFAULT_OUTPUT_DIR / "top_shap_features.png"

# Explanation Configuration
TOP_FEATURES = 3
SHAP_STRONG_THRESHOLD = 0.05
SHAP_MODERATE_THRESHOLD = 0.01
ENABLE_LLM_EXPLANATION = False
MAX_REPORT_TRACES = 10

# Explanation Status Constants
STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL = "PARTIAL"
STATUS_SKIPPED = "SKIPPED"
STATUS_FAILED = "FAILED"
