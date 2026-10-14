"""Flow tuple parsing, resolution, and validation (converted from flow_mapper.h/.c)."""

from dataclasses import dataclass
from typing import Optional

from network.controller.control_config import (
    ALLOWLISTED_INTERFACES,
    KNOWN_DEVICES,
)


@dataclass
class FlowTuple:
    """Parsed and validated network flow 5-tuple + interface metadata."""
    device_id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str
    interface: str


def is_valid_ipv4(ip: str) -> bool:
    """Validate 4-octet dotted decimal IPv4 string."""
    if not ip or len(ip) > 15:
        return False
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for p in parts:
        if not p.isdigit():
            return False
        val = int(p)
        if val < 0 or val > 255:
            return False
        if len(p) > 1 and p.startswith("0"):
            return False
    return True


def is_valid_port(port: int) -> bool:
    """Validate TCP/UDP port range 1..65535."""
    return 1 <= port <= 65535


def is_valid_protocol(proto: str) -> bool:
    """Validate allowlisted transport protocol."""
    return proto is not None and proto.upper() in ("TCP", "UDP")


def is_allowlisted_interface(iface: str) -> bool:
    """Check if network interface is in the allowlist."""
    return iface is not None and iface in ALLOWLISTED_INTERFACES


def is_known_device(device_id: str) -> bool:
    """Check if device identifier is in known topology devices."""
    return device_id is not None and device_id in KNOWN_DEVICES


def resolve_device_interface(device_id: str) -> Optional[str]:
    """Resolve device ID (e.g. h1..h5) to switch port interface (s1-eth1..s1-eth5)."""
    if not device_id:
        return None
    if device_id.startswith("h") and device_id[1:].isdigit():
        host_num = int(device_id[1:])
        if 1 <= host_num <= 5:
            return f"s1-eth{host_num}"
    if is_allowlisted_interface(device_id):
        return device_id
    return None


def resolve_device_ip(device_id: str) -> Optional[str]:
    """Resolve device identifier to LAN IP address."""
    if not device_id:
        return None
    if device_id.startswith("h") and device_id[1:].isdigit():
        host_num = int(device_id[1:])
        if 1 <= host_num <= 50:
            return f"192.168.1.{9 + host_num}"
    return None


def parse_flow_id(flow_id: str) -> Optional[FlowTuple]:
    """Parse and validate standard flow identifier string into FlowTuple.

    Format: <device>_<src_ip>:<src_port>-><dst_ip>:<dst_port>_<proto>
    Example: h1_192.168.1.10:45672->192.168.1.11:5201_TCP
    """
    if not flow_id or "_" not in flow_id or "->" not in flow_id:
        return None

    try:
        dev_part, rest = flow_id.split("_", 1)
        device_id = dev_part.strip()

        src_part, dst_and_proto = rest.split("->", 1)
        if ":" not in src_part:
            return None
        src_ip, src_port_str = src_part.split(":", 1)
        src_port = int(src_port_str)

        if "_" not in dst_and_proto:
            return None
        dst_part, protocol = dst_and_proto.rsplit("_", 1)
        if ":" not in dst_part:
            return None
        dst_ip, dst_port_str = dst_part.split(":", 1)
        dst_port = int(dst_port_str)

        interface = resolve_device_interface(device_id) or ""

        # Validate components
        if not is_valid_ipv4(src_ip) or not is_valid_ipv4(dst_ip):
            return None
        if not is_valid_port(src_port) or not is_valid_port(dst_port):
            return None
        if not is_valid_protocol(protocol):
            return None

        return FlowTuple(
            device_id=device_id,
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            protocol=protocol.upper(),
            interface=interface,
        )
    except Exception:
        return None
