"""
Configuration and constants for the Traffic Generation Module.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
DEFAULT_LOG_DIR = os.path.join(BASE_DIR, "data", "traffic_logs")

# Network Defaults
DEFAULT_SUBNET = "192.168.1"
DEFAULT_BASE_PORT = 5201
DEFAULT_DURATION = 10 # seconds
DEFAULT_UDP_BANDWIDTH = "10M" # 10 Mbps
DEFAULT_TCP_PARALLEL = 1
DEFAULT_HOST_COUNT = 5

@dataclass
class FlowConfig:
    """Represents a single traffic flow specification."""
    flow_id: str
    src_host: str
    dst_host: str
    protocol: str              # "tcp" or "udp"
    duration: int = DEFAULT_DURATION
    bandwidth: str = DEFAULT_UDP_BANDWIDTH # relevant for UDP
    port: int = DEFAULT_BASE_PORT
    parallel: int = 1          # parallel streams
    description: str = ""
    extra_args: List[str] = field(default_factory=list)

    def validate(self):
        """Validate flow parameters."""
        proto = self.protocol.lower()
        if proto not in ["tcp", "udp"]:
            raise ValueError(f"Invalid protocol '{self.protocol}'. Must be 'tcp' or 'udp'.")
        if self.duration <= 0:
            raise ValueError(f"Duration must be positive, got {self.duration}")
        if self.port < 1024 or self.port > 65535:
            raise ValueError(f"Port must be between 1024 and 65535, got {self.port}")
        if self.parallel < 1:
            raise ValueError(f"Parallel streams must be >= 1, got {self.parallel}")
        return True


def get_default_host_ip(host_name: str, subnet: str = DEFAULT_SUBNET) -> str:
    """
    Resolve host name (e.g., 'h1', 'h2') to IP address (e.g., '192.168.1.10', '192.168.1.11').
    """
    if not host_name.startswith("h") or not host_name[1:].isdigit():
        raise ValueError(f"Invalid host name format '{host_name}'. Expected 'h1', 'h2', etc.")
    host_num = int(host_name[1:])
    return f"{subnet}.{9 + host_num}"
