"""Configuration constants and policy definitions for Phase 13 QoS Policy Engine.

Centralizes decision levels, priority scales, traffic class preferences,
congestion adjustments, cluster adjustment mappings, and file paths.
"""

from pathlib import Path
from typing import Dict, List, Tuple

# Workspace Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Input Paths
DEFAULT_CLASSIFIED_FLOWS_PATH = PROJECT_ROOT / "data" / "classification" / "classified_flows.csv"
DEFAULT_TEST_PREDICTIONS_PATH = PROJECT_ROOT / "data" / "congestion" / "test_predictions.csv"
DEFAULT_CONGESTION_DATASET_PATH = PROJECT_ROOT / "data" / "congestion" / "congestion_dataset.csv"
DEFAULT_BEHAVIOR_PROFILES_PATH = PROJECT_ROOT / "data" / "profiling" / "behavior_profiles.csv"
DEFAULT_CONGESTION_LABEL_CONFIG_PATH = PROJECT_ROOT / "data" / "congestion" / "congestion_label_config.json"

# Output Directory
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "policy"

# Output Artifact Paths
QOS_DECISIONS_PATH = DEFAULT_OUTPUT_DIR / "qos_decisions.csv"
POLICY_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "policy_summary.json"

# Visualization Plots
PRIORITY_DISTRIBUTION_PLOT = DEFAULT_OUTPUT_DIR / "priority_distribution.png"
PRIORITY_BY_TRAFFIC_CLASS_PLOT = DEFAULT_OUTPUT_DIR / "priority_by_traffic_class.png"
PRIORITY_BY_CONGESTION_PLOT = DEFAULT_OUTPUT_DIR / "priority_by_congestion.png"

# QoS Decision Levels (Configurable Policy Labels)
PRIORITY_LEVELS: List[str] = ["LOW", "NORMAL", "MEDIUM", "HIGH"]
DEFAULT_PRIORITY: str = "NORMAL"

# Internal Numerical Scale (0 to 3)
PRIORITY_TO_NUMERIC: Dict[str, int] = {
    "LOW": 0,
    "NORMAL": 1,
    "MEDIUM": 2,
    "HIGH": 3,
}

NUMERIC_TO_PRIORITY: Dict[int, str] = {
    0: "LOW",
    1: "NORMAL",
    2: "MEDIUM",
    3: "HIGH",
}

# Recognized Traffic Classes (from Phase 12)
TRAFFIC_CLASSES: List[str] = [
    "REAL_TIME",
    "INTERACTIVE",
    "WEB",
    "DNS",
    "BULK_TRANSFER",
    "OTHER",
]

# Baseline Traffic-Class Preference Table
# Note: Initial rule set for evaluation; not an objective universal ranking.
TRAFFIC_CLASS_PRIORITIES: Dict[str, str] = {
    "REAL_TIME": "HIGH",
    "INTERACTIVE": "HIGH",
    "DNS": "MEDIUM",
    "WEB": "MEDIUM",
    "BULK_TRANSFER": "LOW",
    "OTHER": "NORMAL",
}

# Congestion Classes (from Phase 9/10)
CONGESTION_CLASSES: List[str] = ["LOW", "MEDIUM", "HIGH", "UNKNOWN"]

# Default Congestion Score Thresholds (Aligned with Phase 9 congestion_label_config.json)
DEFAULT_CONGESTION_THRESHOLDS: Dict[str, Tuple[float, float]] = {
    "LOW": (0.0, 0.33),
    "MEDIUM": (0.33, 0.67),
    "HIGH": (0.67, 1.0),
}

# Default Global Congestion Adjustments (delta applied on numeric scale)
CONGESTION_ADJUSTMENTS: Dict[str, int] = {
    "LOW": 0,
    "MEDIUM": 0,
    "HIGH": 0,
    "UNKNOWN": 0,
}

# User Behavior Profile Adjustments
# IMPORTANT: Cluster IDs are mathematical identifiers, not inherently good or bad.
# Explicit mapping avoids biased assumptions. Default adjustment is 0 (neutral).
CLUSTER_ADJUSTMENTS: Dict[int, int] = {
    0: 0,  # Cluster 0 (e.g. Low-Activity profile): neutral adjustment
    1: 0,  # Cluster 1 (e.g. High-Flow-Activity profile): neutral adjustment
}

# Timestamp Alignment Window for Temporal Joining (in seconds)
TIME_MATCH_TOLERANCE_SECONDS: float = 2.0
