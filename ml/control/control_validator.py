"""Input validation and sanitization for Phase 14 Adaptive Traffic Control."""

import ipaddress
from pathlib import Path
import sys
from typing import Any, Dict, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.control.config import (
    ALLOWLISTED_INTERFACES,
    ALLOWLISTED_PROTOCOLS,
    KNOWN_DEVICES,
    PRIORITY_TO_CLASS,
)


class ControlValidator:
    """Validates and sanitizes network-control inputs against strict allowlists."""

    @staticmethod
    def validate_ip(ip: str) -> bool:
        """Validate IPv4 address string."""
        if not ip or not isinstance(ip, str):
            return False
        try:
            ip_obj = ipaddress.IPv4Address(ip.strip())
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_port(port: Any) -> bool:
        """Validate TCP/UDP port number (1-65535)."""
        try:
            val = int(port)
            return 1 <= val <= 65535
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_protocol(proto: str) -> bool:
        """Validate network transport protocol."""
        if not proto or not isinstance(proto, str):
            return False
        return proto.strip().upper() in ALLOWLISTED_PROTOCOLS

    @staticmethod
    def validate_priority(priority: str) -> bool:
        """Validate priority label against recognized policy levels."""
        if not priority or not isinstance(priority, str):
            return False
        return priority.strip().upper() in PRIORITY_TO_CLASS

    @staticmethod
    def validate_device(device_id: str) -> bool:
        """Validate host device identifier."""
        if not device_id or not isinstance(device_id, str):
            return False
        return device_id.strip() in KNOWN_DEVICES

    @staticmethod
    def validate_interface(interface: str) -> bool:
        """Validate network interface name against allowlist."""
        if not interface or not isinstance(interface, str):
            return False
        return interface.strip() in ALLOWLISTED_INTERFACES

    @classmethod
    def validate_record(cls, record: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate a complete control record before execution or simulation.

        Args:
            record: Dictionary containing flow attributes and control intent.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not isinstance(record, dict):
            return False, "Record must be a dictionary"

        dev = record.get("device_id")
        if not cls.validate_device(dev):
            return False, f"Unknown or invalid device_id: {dev}"

        iface = record.get("interface")
        if not cls.validate_interface(iface):
            return False, f"Interface '{iface}' not in allowlist"

        src_ip = record.get("src_ip")
        if not cls.validate_ip(src_ip):
            return False, f"Invalid source IP address: {src_ip}"

        dst_ip = record.get("dst_ip")
        if not cls.validate_ip(dst_ip):
            return False, f"Invalid destination IP address: {dst_ip}"

        src_port = record.get("src_port")
        if not cls.validate_port(src_port):
            return False, f"Invalid source port: {src_port}"

        dst_port = record.get("dst_port")
        if not cls.validate_port(dst_port):
            return False, f"Invalid destination port: {dst_port}"

        proto = record.get("protocol")
        if not cls.validate_protocol(proto):
            return False, f"Invalid protocol: {proto}"

        prio = record.get("final_priority")
        if not cls.validate_priority(prio):
            return False, f"Invalid priority level: {prio}"

        return True, ""
