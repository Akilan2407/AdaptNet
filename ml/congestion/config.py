"""Configuration constants and paths for Phase 9: Congestion Dataset Module.

Defines time-series observation windows, prediction horizons, congestion score
formulation weights, labeling thresholds, and chronological split ratios.
"""

from pathlib import Path
from typing import Dict, List

# Workspace Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Input Paths from Previous Phases
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "features" / "network_features.csv"
DEFAULT_MONITORING_PATH = PROJECT_ROOT / "data" / "monitoring" / "network_metrics.csv"
DEFAULT_PROFILES_PATH = PROJECT_ROOT / "data" / "profiling" / "behavior_profiles.csv"
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data" / "profiling" / "cluster_summary.csv"

# Output Directory & Dataset Paths
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "congestion"
DEFAULT_DATASET_PATH = DEFAULT_OUTPUT_DIR / "congestion_dataset.csv"
DEFAULT_TRAIN_PATH = DEFAULT_OUTPUT_DIR / "train_dataset.csv"
DEFAULT_VAL_PATH = DEFAULT_OUTPUT_DIR / "validation_dataset.csv"
DEFAULT_TEST_PATH = DEFAULT_OUTPUT_DIR / "test_dataset.csv"
DEFAULT_STATS_PATH = DEFAULT_OUTPUT_DIR / "dataset_statistics.json"
DEFAULT_LABEL_CONFIG_PATH = DEFAULT_OUTPUT_DIR / "congestion_label_config.json"
DEFAULT_VISUALIZATION_PATH = DEFAULT_OUTPUT_DIR / "dataset_visualization.png"

# Time-Series Windowing Parameters
HISTORY_WINDOW_SECONDS = 30
PREDICTION_HORIZON_SECONDS = 10  # Supports 10, 20, 30 via CLI/configuration
HORIZON_TOLERANCE_SECONDS = 5    # Search window around target timestamp
MIN_HISTORY_STEPS = 1            # Minimum observations in historical window

# Congestion Scoring Formulation Weights & Baselines
# Normalized into [0.0, 1.0]
NOMINAL_BANDWIDTH_MBPS = 100.0   # Reference link saturation capacity
BASE_RTT_MS = 2.0                # Uncongested LAN baseline RTT
MAX_RTT_MS = 100.0               # High latency bufferbloat reference
MAX_PACKET_LOSS_PCT = 10.0       # Severe congestion packet loss cap
MAX_ACTIVE_CONNECTIONS = 20      # High concurrency reference

# Scoring Factor Weights (sum to 1.00)
WEIGHT_PACKET_LOSS = 0.35
WEIGHT_RTT = 0.30
WEIGHT_THROUGHPUT = 0.25
WEIGHT_CONNECTIONS = 0.10

# Categorical Congestion Class Thresholds
# Documented dataset labeling thresholds (not universal RFC standards)
LOW_THRESHOLD = 0.33
HIGH_THRESHOLD = 0.67

CONGESTION_CLASSES = ["LOW", "MEDIUM", "HIGH"]

# Chronological Split Ratios (Temporal order: Train -> Validation -> Test)
TRAIN_RATIO = 0.70
VALIDATION_RATIO = 0.15
TEST_RATIO = 0.15

# Candidate Congestion Features from Phase 7
CANDIDATE_CONGESTION_FEATURES: List[str] = [
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

# Contextual Behavioral Features from Phase 8
CONTEXT_BEHAVIORAL_FEATURES: List[str] = [
    "cluster_id",
]

# ==============================================================================
# PHASE 10: CONGESTION PREDICTION MODEL & EVALUATION CONFIGURATION
# ==============================================================================

# Model and Artifact Paths
DEFAULT_MODEL_FILE = DEFAULT_OUTPUT_DIR / "gru_congestion_model.keras"
DEFAULT_SCALER_FILE = DEFAULT_OUTPUT_DIR / "congestion_scaler.pkl"
DEFAULT_METADATA_FILE = DEFAULT_OUTPUT_DIR / "model_metadata.json"
DEFAULT_EVALUATION_FILE = DEFAULT_OUTPUT_DIR / "model_evaluation.json"
DEFAULT_BASELINE_EVAL_FILE = DEFAULT_OUTPUT_DIR / "baseline_evaluation.json"
DEFAULT_PREDICTIONS_FILE = DEFAULT_OUTPUT_DIR / "test_predictions.csv"

# Visualization Plots
DEFAULT_TRAINING_LOSS_PLOT = DEFAULT_OUTPUT_DIR / "training_loss.png"
DEFAULT_ACTUAL_VS_PRED_PLOT = DEFAULT_OUTPUT_DIR / "actual_vs_predicted.png"
DEFAULT_ERROR_PLOT = DEFAULT_OUTPUT_DIR / "prediction_error.png"
DEFAULT_CONFUSION_MATRIX_PLOT = DEFAULT_OUTPUT_DIR / "congestion_confusion_matrix.png"

# Sequence Tensor Dimensions
# Shape: (samples, timesteps, features)
DEFAULT_TIMESTEPS = 2  # Step 0: Historical lookback summary, Step 1: Current anchor state

# GRU Architecture Hyperparameters
GRU_UNITS = 64
DENSE_UNITS = 32
DROPOUT_RATE = 0.20

# Training Hyperparameters
LEARNING_RATE = 0.001
BATCH_SIZE = 32
EPOCHS = 50
EARLY_STOPPING_PATIENCE = 8
RANDOM_SEED = 42

