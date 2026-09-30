"""Configuration constants and paths for Phase 8: User Behavior Profiling Module.

Defines default file locations, feature specifications, clustering parameters,
and random state definitions for reproducible behavior profiling.
"""

from pathlib import Path
from typing import Dict, List

# Workspace Root Discovery
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Default Dataset & Output Paths
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "features" / "network_features.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "profiling"

DEFAULT_OUTPUT_PROFILES = DEFAULT_OUTPUT_DIR / "behavior_profiles.csv"
DEFAULT_OUTPUT_SUMMARY = DEFAULT_OUTPUT_DIR / "cluster_summary.csv"
DEFAULT_OUTPUT_EVALUATION = DEFAULT_OUTPUT_DIR / "clustering_evaluation.csv"
DEFAULT_MODEL_PATH = DEFAULT_OUTPUT_DIR / "clustering_model.pkl"
DEFAULT_SCALER_PATH = DEFAULT_OUTPUT_DIR / "scaler.pkl"
DEFAULT_FEATURES_JSON_PATH = DEFAULT_OUTPUT_DIR / "clustering_features.json"
DEFAULT_VISUALIZATION_PATH = DEFAULT_OUTPUT_DIR / "cluster_visualization.png"

# Behavior Features from Phase 7
# Candidate features required for device-level behavior profiling
CORE_BEHAVIOR_FEATURES: List[str] = [
    "mean_throughput_mbps",
    "mean_rtt_ms",
    "mean_packet_loss_percent",
    "mean_active_connections",
    "total_flow_count",  # Flow count from Phase 7
    "tcp_flow_ratio",
    "udp_flow_ratio",
    "throughput_std",
    "rtt_std",
]

# Time and Activity Features
TEMPORAL_FEATURES: List[str] = [
    "active_hours_count",  # Derived: number of distinct active hours per device
]

# All Candidate Features to Include if Available
ALL_CANDIDATE_FEATURES: List[str] = CORE_BEHAVIOR_FEATURES + TEMPORAL_FEATURES

# Field Aliases between Documentation and Phase 7 Columns
FEATURE_ALIASES: Dict[str, str] = {
    "flow_count": "total_flow_count",
}

# Clustering Hyperparameters & Reproducibility
RANDOM_STATE = 42
DEFAULT_MIN_K = 2
DEFAULT_MAX_K = 6
KMEANS_N_INIT = 10

# Optional DBSCAN Defaults
DBSCAN_DEFAULT_EPS = 0.5
DBSCAN_DEFAULT_MIN_SAMPLES = 2

# Output Column Order for behavior_profiles.csv
OUTPUT_PROFILE_COLUMNS: List[str] = [
    "device_id",
    "cluster_id",
    "profile_label",
    "mean_throughput_mbps",
    "mean_rtt_ms",
    "mean_packet_loss_percent",
    "mean_active_connections",
    "total_flow_count",
    "tcp_flow_ratio",
    "udp_flow_ratio",
    "throughput_std",
    "rtt_std",
    "active_hours_count",
]
