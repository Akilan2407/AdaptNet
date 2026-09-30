"""Configuration constants and settings for the Feature Extraction Module (Phase 7).

Defines default paths, required schema columns, rolling window settings,
and time-of-day boundary definitions.
"""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT_PATH = BASE_DIR / "data" / "monitoring" / "network_metrics.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "features"
DEFAULT_OUTPUT_PATH = DEFAULT_OUTPUT_DIR / "network_features.csv"

# Required input columns from Phase 6
REQUIRED_COLUMNS = [
    "timestamp",
    "device_id",
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "throughput",
    "rtt",
    "packet_loss",
    "active_connections",
]

# Numeric columns to coerce
NUMERIC_COLUMNS = [
    "throughput",
    "rtt",
    "packet_loss",
    "active_connections",
    "src_port",
    "dst_port",
]

# Protocol encoding map
PROTOCOL_ENCODING = {
    "TCP": 1,
    "UDP": 0,
}

# Time of Day boundaries (hour-based)
# morning:   06:00 - 11:59 (6 to 11)
# afternoon: 12:00 - 17:59 (12 to 17)
# evening:   18:00 - 23:59 (18 to 23)
# night:     00:00 - 05:59 (0 to 5)
TIME_OF_DAY_BINS = {
    "night": (0, 5),
    "morning": (6, 11),
    "afternoon": (12, 17),
    "evening": (18, 23),
}

# Default rolling window size in seconds (5 minutes = 300 seconds)
DEFAULT_ROLLING_WINDOW_SECONDS = 300
DEFAULT_ROLLING_WINDOW_LABEL = "5m"
