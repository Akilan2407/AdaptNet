"""Configuration constants and paths for Phase 15 Decision Trace Module."""

from pathlib import Path
import sys
from typing import Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Input Dataset Paths (Phases 4–14)
DEFAULT_MONITORING_PATH = PROJECT_ROOT / "data" / "monitoring" / "network_metrics.csv"
DEFAULT_FEATURES_PATH = PROJECT_ROOT / "data" / "features" / "network_features.csv"
DEFAULT_PROFILES_PATH = PROJECT_ROOT / "data" / "profiling" / "behavior_profiles.csv"
DEFAULT_CONGESTION_PATH = PROJECT_ROOT / "data" / "congestion" / "test_predictions.csv"
DEFAULT_CONGESTION_DATASET_PATH = PROJECT_ROOT / "data" / "congestion" / "congestion_dataset.csv"
DEFAULT_CONGESTION_CONFIG_PATH = PROJECT_ROOT / "data" / "congestion" / "congestion_label_config.json"
DEFAULT_CLASSIFICATION_PATH = PROJECT_ROOT / "data" / "classification" / "classified_flows.csv"
DEFAULT_POLICY_PATH = PROJECT_ROOT / "data" / "policy" / "qos_decisions.csv"
DEFAULT_CONTROL_PATH = PROJECT_ROOT / "data" / "control" / "control_actions.csv"

# Output Directory & Artifact Paths
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "trace"
DEFAULT_TRACES_CSV = DEFAULT_OUTPUT_DIR / "decision_traces.csv"
DEFAULT_TRACES_JSONL = DEFAULT_OUTPUT_DIR / "decision_traces.jsonl"
DEFAULT_SUMMARY_JSON = DEFAULT_OUTPUT_DIR / "trace_summary.json"

# Visualization Plots
TRACE_COMPLETENESS_PLOT = DEFAULT_OUTPUT_DIR / "trace_completeness.png"
TRACE_STAGE_PLOT = DEFAULT_OUTPUT_DIR / "trace_stage_availability.png"

# Trace Schema Versioning
TRACE_SCHEMA_VERSION = "1.0"
SYSTEM_VERSION = "1.0.0"

# Configurable Timestamp Tolerance for Multi-Stage Temporal Joining (in seconds)
TRACE_TIMESTAMP_TOLERANCE_SECONDS: float = 5.0

# Trace Completeness Levels
COMPLETENESS_COMPLETE = "COMPLETE"
COMPLETENESS_PARTIAL = "PARTIAL"
COMPLETENESS_INCOMPLETE = "INCOMPLETE"

# Recognized Matching Strategies
MATCH_EXACT_FLOW_ID = "EXACT_FLOW_ID"
MATCH_EXACT_DEVICE_FLOW = "EXACT_DEVICE_FLOW"
MATCH_DEVICE_TIMESTAMP = "DEVICE_TIMESTAMP"
MATCH_FLOW_TIMESTAMP_TOLERANCE = "FLOW_TIMESTAMP_TOLERANCE"
MATCH_UNMATCHED = "UNMATCHED"

# Standard Pipeline Stages (7 Stages)
PIPELINE_STAGES: List[str] = [
    "monitoring",
    "features",
    "profile",
    "congestion",
    "classification",
    "policy",
    "control",
]

# Priority to Control Class Mapping (for Cross-Stage Consistency Checks)
PRIORITY_TO_CONTROL_CLASS: Dict[str, str] = {
    "HIGH": "1:10",
    "MEDIUM": "1:20",
    "NORMAL": "1:30",
    "LOW": "1:40",
}
