"""Configuration constants and artifact paths for Phase 11: Congestion Baseline Module."""

from pathlib import Path
from typing import List

# Workspace Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Input Paths from Phase 7, 9, 10
DEFAULT_TEST_PREDICTIONS_PATH = PROJECT_ROOT / "data" / "congestion" / "test_predictions.csv"
DEFAULT_TEST_DATASET_PATH = PROJECT_ROOT / "data" / "congestion" / "test_dataset.csv"
DEFAULT_CONGESTION_DATASET_PATH = PROJECT_ROOT / "data" / "congestion" / "congestion_dataset.csv"
DEFAULT_LABEL_CONFIG_PATH = PROJECT_ROOT / "data" / "congestion" / "congestion_label_config.json"
DEFAULT_MODEL_EVAL_PATH = PROJECT_ROOT / "data" / "congestion" / "model_evaluation.json"
DEFAULT_NETWORK_FEATURES_PATH = PROJECT_ROOT / "data" / "features" / "network_features.csv"

# Output Directory
DEFAULT_BASELINE_OUTPUT_DIR = PROJECT_ROOT / "data" / "baseline"

# Generated Output Files
PERSISTENCE_PREDICTIONS_PATH = DEFAULT_BASELINE_OUTPUT_DIR / "persistence_predictions.csv"
MOVING_AVERAGE_PREDICTIONS_PATH = DEFAULT_BASELINE_OUTPUT_DIR / "moving_average_predictions.csv"
LINEAR_TREND_PREDICTIONS_PATH = DEFAULT_BASELINE_OUTPUT_DIR / "linear_trend_predictions.csv"
BASELINE_EVALUATION_PATH = DEFAULT_BASELINE_OUTPUT_DIR / "baseline_evaluation.json"
MODEL_COMPARISON_PATH = DEFAULT_BASELINE_OUTPUT_DIR / "model_comparison.csv"
BASELINE_SUMMARY_PATH = DEFAULT_BASELINE_OUTPUT_DIR / "baseline_summary.json"

# Generated Diagnostic Plots
MAE_COMPARISON_PLOT = DEFAULT_BASELINE_OUTPUT_DIR / "mae_comparison.png"
RMSE_COMPARISON_PLOT = DEFAULT_BASELINE_OUTPUT_DIR / "rmse_comparison.png"
BASELINE_PREDICTIONS_PLOT = DEFAULT_BASELINE_OUTPUT_DIR / "baseline_predictions.png"

# Baseline Algorithmic Hyperparameters
MOVING_AVERAGE_WINDOW: int = 5
MIN_HISTORY_POINTS: int = 1
MIN_TREND_POINTS: int = 2

# Congestion Thresholds & Categorical Classes (matches Phase 9/10)
LOW_THRESHOLD: float = 0.33
HIGH_THRESHOLD: float = 0.67
CONGESTION_CLASSES: List[str] = ["LOW", "MEDIUM", "HIGH"]
