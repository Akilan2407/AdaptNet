"""Configuration constants and paths for Phase 16 SHAP Explainability Module."""

from pathlib import Path
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Input Model & Scaler Artifacts (Phase 10)
DEFAULT_MODEL_PATH = PROJECT_ROOT / "data" / "congestion" / "gru_congestion_model.keras"
DEFAULT_SCALER_PATH = PROJECT_ROOT / "data" / "congestion" / "congestion_scaler.pkl"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "data" / "congestion" / "model_metadata.json"
DEFAULT_CONGESTION_DATASET_PATH = PROJECT_ROOT / "data" / "congestion" / "congestion_dataset.csv"
DEFAULT_TEST_DATASET_PATH = PROJECT_ROOT / "data" / "congestion" / "test_dataset.csv"

# Input Trace Artifacts (Phase 15)
DEFAULT_TRACES_CSV = PROJECT_ROOT / "data" / "trace" / "decision_traces.csv"
DEFAULT_TRACES_JSONL = PROJECT_ROOT / "data" / "trace" / "decision_traces.jsonl"

# Output Explainability Artifacts (Phase 16)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "explainability"
DEFAULT_LOCAL_CSV = DEFAULT_OUTPUT_DIR / "local_shap_explanations.csv"
DEFAULT_LOCAL_JSONL = DEFAULT_OUTPUT_DIR / "local_shap_explanations.jsonl"
DEFAULT_GLOBAL_CSV = DEFAULT_OUTPUT_DIR / "global_shap_importance.csv"
DEFAULT_GLOBAL_PLOT = DEFAULT_OUTPUT_DIR / "global_feature_importance.png"
DEFAULT_SUMMARY_PLOT = DEFAULT_OUTPUT_DIR / "shap_summary.png"
DEFAULT_LOCAL_PLOTS_DIR = DEFAULT_OUTPUT_DIR / "local"
DEFAULT_EXPLAINABILITY_SUMMARY = DEFAULT_OUTPUT_DIR / "explainability_summary.json"
DEFAULT_SELECTION_JSON = DEFAULT_OUTPUT_DIR / "explanation_selection.json"
DEFAULT_RECORDS_JSONL = DEFAULT_OUTPUT_DIR / "explanation_records.jsonl"

# The 11 recurrent feature names per timestep in exact GRU model input order
RECURRENT_FEATURE_NAMES = [
    "cluster_id",
    "throughput_mbps",
    "rtt_ms",
    "packet_loss_percent",
    "active_connections",
    "throughput_std",
    "rtt_std",
    "packet_loss_std",
    "total_flow_count",
    "tcp_flow_ratio",
    "udp_flow_ratio",
]

# The 21 scaler features used during StandardScaler transform
SCALER_FEATURE_COLUMNS = [
    "cluster_id",
    "throughput_mbps",
    "rtt_ms",
    "packet_loss_percent",
    "active_connections",
    "throughput_std",
    "rtt_std",
    "packet_loss_std",
    "total_flow_count",
    "tcp_flow_ratio",
    "udp_flow_ratio",
    "hist_mean_throughput_mbps",
    "hist_mean_rtt_ms",
    "hist_mean_packet_loss_percent",
    "hist_mean_active_connections",
    "hist_mean_throughput_std",
    "hist_mean_rtt_std",
    "hist_mean_packet_loss_std",
    "hist_mean_total_flow_count",
    "hist_mean_tcp_flow_ratio",
    "hist_mean_udp_flow_ratio",
]

# Recurrent Sequence Dimensions
TIMESTEPS = 2
FEATURES_PER_STEP = 11

# Temporal Aggregation Modes
AGG_MEAN_ABSOLUTE = "mean_absolute"
AGG_MEAN = "mean"
AGG_SUM = "sum"
AGG_LAST_TIMESTEP = "last_timestep"
SHAP_TIME_AGGREGATION = AGG_MEAN_ABSOLUTE

# Sampling & Performance Parameters
BACKGROUND_SAMPLE_SIZE = 50
EXPLANATION_SAMPLE_SIZE = 100
MAX_LOCAL_EXPLANATION_PLOTS = 20
RANDOM_SEED = 42

# Validation Thresholds
ADDITIVITY_TOLERANCE = 0.25
CONSISTENCY_TOLERANCE = 0.05

# Status Strings
STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL = "PARTIAL"
STATUS_SKIPPED = "SKIPPED"
STATUS_FAILED = "FAILED"

# Direction Strings
DIRECTION_INCREASED = "increased"
DIRECTION_DECREASED = "decreased"
DIRECTION_NEUTRAL = "neutral"
