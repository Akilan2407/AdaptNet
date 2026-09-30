"""Configuration constants and rule definitions for Phase 12 Traffic Classification."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

# Workspace Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Input Paths
DEFAULT_FEATURES_PATH = PROJECT_ROOT / "data" / "features" / "network_features.csv"
DEFAULT_MONITORING_PATH = PROJECT_ROOT / "data" / "monitoring" / "network_metrics.csv"

# Output Directory
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "classification"

# Output Artifact Paths
CLASSIFIED_FLOWS_PATH = DEFAULT_OUTPUT_DIR / "classified_flows.csv"
CLASSIFICATION_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "classification_summary.json"
CLASSIFICATION_RULES_PATH = DEFAULT_OUTPUT_DIR / "classification_rules.json"

# Visualization Plots
CLASS_DISTRIBUTION_PLOT = DEFAULT_OUTPUT_DIR / "traffic_class_distribution.png"
PROTOCOL_DISTRIBUTION_PLOT = DEFAULT_OUTPUT_DIR / "protocol_distribution.png"
CLASS_BY_PROTOCOL_PLOT = DEFAULT_OUTPUT_DIR / "class_by_protocol.png"

# Allowed Traffic Categories (Configurable)
TRAFFIC_CLASSES: List[str] = [
    "INTERACTIVE",
    "REAL_TIME",
    "BULK_TRANSFER",
    "WEB",
    "DNS",
    "OTHER",
]

# Rule Evaluation Precedence Order
RULE_PRIORITY: List[str] = [
    "DNS",
    "REAL_TIME",
    "WEB",
    "INTERACTIVE",
    "BULK_TRANSFER",
    "OTHER",
]

# Port & Protocol Rule Catalog
PORT_RULES: Dict[str, Dict[str, Any]] = {
    "DNS": {
        "protocols": ["UDP", "TCP"],
        "ports": [53],
        "ranges": [],
        "description": "Domain Name System resolution traffic",
    },
    "REAL_TIME": {
        "protocols": ["UDP"],
        "ports": [5004, 5005, 5060, 5061],
        "ranges": [(3478, 3481), (5000, 6000)],
        "description": "Real-time communication, STUN/TURN, SIP, and RTP audio/video streams",
    },
    "WEB": {
        "protocols": ["TCP"],
        "ports": [80, 443, 8080, 8443],
        "ranges": [],
        "description": "Standard HTTP, HTTPS, and web alternate communication",
    },
    "INTERACTIVE": {
        "protocols": ["TCP"],
        "ports": [22, 23, 3389, 5900],
        "ranges": [],
        "description": "Interactive shell and remote desktop sessions (SSH, Telnet, RDP, VNC)",
    },
    "BULK_TRANSFER": {
        "protocols": ["TCP"],
        "ports": [20, 21, 445, 5201, 873],
        "ranges": [],
        "description": "Bulk data, file transfer, SMB, rsync, and sustained throughput benchmarks (iPerf3)",
    },
}

# Rule Confidence Values
CONFIDENCE_EXACT_PORT: float = 1.0
CONFIDENCE_PORT_RANGE: float = 0.85
CONFIDENCE_SECONDARY_FEATURE: float = 0.70
CONFIDENCE_UNKNOWN: float = 0.0

# Port Range Bounds
MIN_VALID_PORT: int = 1
MAX_VALID_PORT: int = 65535
