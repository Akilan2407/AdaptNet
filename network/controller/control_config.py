"""Configuration constants for Adaptive Traffic Controller (converted from control_config.h)."""

from enum import IntEnum
from typing import List


class PriorityLevel(IntEnum):
    """Priority levels aligned with QoS Policy Engine."""
    PRIO_LEVEL_UNKNOWN = -1
    PRIO_LEVEL_LOW = 0
    PRIO_LEVEL_NORMAL = 1
    PRIO_LEVEL_MEDIUM = 2
    PRIO_LEVEL_HIGH = 3


# Traffic Control Classes & Bandwidth Allocation
HTB_ROOT_HANDLE_MAJOR = 1
HTB_ROOT_CLASS_ID = "1:1"
HTB_CLASS_HIGH = "1:10"
HTB_CLASS_MEDIUM = "1:20"
HTB_CLASS_NORMAL = "1:30"
HTB_CLASS_LOW = "1:40"
HTB_DEFAULT_CLASS_NUM = 30

# Configurable Bandwidth & Ceiling Rates
RATE_ROOT_TOTAL = "100mbit"
RATE_HIGH = "100mbit"
CEIL_HIGH = "100mbit"
TC_PRIO_HIGH = 1

RATE_MEDIUM = "60mbit"
CEIL_MEDIUM = "80mbit"
TC_PRIO_MEDIUM = 2

RATE_NORMAL = "30mbit"
CEIL_NORMAL = "50mbit"
TC_PRIO_NORMAL = 3

RATE_LOW = "10mbit"
CEIL_LOW = "20mbit"
TC_PRIO_LOW = 4

# Safety Default
DEFAULT_DRY_RUN = True

# File Paths
DEFAULT_QOS_DECISIONS_CSV = "data/policy/qos_decisions.csv"
DEFAULT_CONTROL_ACTIONS_CSV = "data/control/control_actions.csv"
DEFAULT_CONTROL_STATE_CSV = "data/control/control_state.csv"
DEFAULT_CONTROL_LOG_DIR = "data/control"

# Allowlisted Network Interfaces (Mininet Small LAN Topology)
ALLOWLISTED_INTERFACES: List[str] = [
    "s1-eth1", "s1-eth2", "s1-eth3", "s1-eth4", "s1-eth5",
    "h1-eth0", "h2-eth0", "h3-eth0", "h4-eth0", "h5-eth0",
    "lo",
]

# Known Topology Devices
KNOWN_DEVICES: List[str] = ["h1", "h2", "h3", "h4", "h5"]
