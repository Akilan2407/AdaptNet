"""Configuration constants for Phase 14 Adaptive Traffic Control Module."""

from pathlib import Path
import sys
from typing import Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# File Paths
DEFAULT_DECISIONS_PATH = PROJECT_ROOT / "data" / "policy" / "qos_decisions.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "control"
DEFAULT_ACTIONS_PATH = DEFAULT_OUTPUT_DIR / "control_actions.csv"
DEFAULT_STATE_PATH = DEFAULT_OUTPUT_DIR / "control_state.csv"
DEFAULT_SUMMARY_PATH = DEFAULT_OUTPUT_DIR / "control_summary.json"

# Plot Artifacts
CONTROL_ACTIONS_PLOT = DEFAULT_OUTPUT_DIR / "control_actions.png"
PRIORITY_CONTROL_PLOT = DEFAULT_OUTPUT_DIR / "priority_control_distribution.png"

# C Adaptive Controller Binary Path
C_CONTROLLER_BIN = PROJECT_ROOT / "network" / "controller" / "adaptive_controller"

# Safety: Default mode is DRY_RUN = True
DEFAULT_DRY_RUN: bool = True

# Priority to TC Class Mapping (HTB Hierarchy)
PRIORITY_TO_CLASS: Dict[str, str] = {
    "HIGH": "1:10",
    "MEDIUM": "1:20",
    "NORMAL": "1:30",
    "LOW": "1:40",
}

# Configurable Rate & Priority Class Attributes
CLASS_RATES: Dict[str, Dict[str, str | int]] = {
    "1:10": {"name": "HIGH", "rate": "100mbit", "ceil": "100mbit", "prio": 1},
    "1:20": {"name": "MEDIUM", "rate": "60mbit", "ceil": "80mbit", "prio": 2},
    "1:30": {"name": "NORMAL", "rate": "30mbit", "ceil": "50mbit", "prio": 3},
    "1:40": {"name": "LOW", "rate": "10mbit", "ceil": "20mbit", "prio": 4},
}

# Mininet Small LAN Topology Device-to-Interface Mapping
DEVICE_TO_INTERFACE: Dict[str, str] = {
    "h1": "s1-eth1",
    "h2": "s1-eth2",
    "h3": "s1-eth3",
    "h4": "s1-eth4",
    "h5": "s1-eth5",
}

# Allowlisted Network Interfaces
ALLOWLISTED_INTERFACES: List[str] = [
    "s1-eth1", "s1-eth2", "s1-eth3", "s1-eth4", "s1-eth5",
    "h1-eth0", "h2-eth0", "h3-eth0", "h4-eth0", "h5-eth0",
    "lo",
]

# Allowlisted Protocols
ALLOWLISTED_PROTOCOLS: List[str] = ["TCP", "UDP"]

# Known Topology Devices
KNOWN_DEVICES: List[str] = ["h1", "h2", "h3", "h4", "h5"]
