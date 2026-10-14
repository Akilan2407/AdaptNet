"""
Network record integrity validator — updated for real packet-capture schema.

Validates NetworkRecord structs parsed from the pipe-delimited wire protocol.
Supports both the legacy 11-field schema and the extended 16-field schema
that includes real packet-capture derived fields:
  - retransmit_pct, jitter_ms, window_size, total_packets, total_bytes
"""

from typing import Optional, Tuple
from network.ingestion.record_parser import NetworkRecord


def is_valid_ipv4(ip_str: str) -> bool:
    """Validate that the given string is a standard 4-octet IPv4 address."""
    if not ip_str:
        return False
    parts = ip_str.split(".")
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


def validate_network_record(record: NetworkRecord) -> Tuple[bool, Optional[str]]:
    """
    Validate a parsed NetworkRecord against network integrity rules.

    Normalizes protocol to uppercase ("TCP", "UDP", or "ICMP").

    Returns:
        (True, None) if valid, or (False, error_msg) if invalid.
    """
    if record is None:
        return False, "Null record pointer"

    # 1. Timestamp
    if not record.measurement_timestamp or len(record.measurement_timestamp) < 5:
        return False, "Invalid or empty measurement timestamp"

    # 2. Device ID
    if not record.device_id:
        return False, "Empty device ID"

    # 3. Source & Destination IP addresses
    if not is_valid_ipv4(record.src_ip):
        return False, f"Invalid source IP format: '{record.src_ip}'"
    if not is_valid_ipv4(record.dst_ip):
        return False, f"Invalid destination IP format: '{record.dst_ip}'"

    # 4. Port ranges (0..65535 — allow 0 for ICMP flows)
    if record.src_port < 0 or record.src_port > 65535:
        return False, f"Invalid source port {record.src_port} (must be 0-65535)"
    if record.dst_port < 0 or record.dst_port > 65535:
        return False, f"Invalid destination port {record.dst_port} (must be 0-65535)"

    # 5. Protocol — accept TCP, UDP, ICMP
    proto_upper = record.protocol.upper()
    if proto_upper in ("TCP", "UDP", "ICMP"):
        record.protocol = proto_upper
    else:
        return False, f"Invalid protocol '{record.protocol}' (must be TCP, UDP, or ICMP)"

    # 6. Throughput (cannot be negative; 0.0 is valid for idle flows)
    if record.throughput_mbps < 0.0:
        return False, f"Negative throughput: {record.throughput_mbps:.4f} Mbps"

    # 7. RTT — must be non-negative when present
    if record.has_rtt and record.rtt_ms is not None and record.rtt_ms < 0.0:
        return False, f"Negative RTT value: {record.rtt_ms:.3f} ms"

    # 8. Packet Loss — must be 0-100%
    if record.has_packet_loss and record.packet_loss_pct is not None:
        if record.packet_loss_pct < 0.0 or record.packet_loss_pct > 100.0:
            return False, f"Invalid packet loss: {record.packet_loss_pct:.4f}% (must be 0-100)"

    # 9. Active Connections
    if record.active_connections < 0:
        return False, f"Negative active connections: {record.active_connections}"

    # 10. Extended real-capture fields (validated only if present)
    if hasattr(record, 'retransmit_pct') and record.retransmit_pct is not None:
        if record.retransmit_pct < 0.0 or record.retransmit_pct > 100.0:
            return False, f"Invalid retransmit_pct: {record.retransmit_pct:.4f}%"

    if hasattr(record, 'jitter_ms') and record.jitter_ms is not None:
        if record.jitter_ms < 0.0:
            return False, f"Negative jitter: {record.jitter_ms:.3f} ms"

    if hasattr(record, 'window_size') and record.window_size is not None:
        if record.window_size < 0 or record.window_size > 2**30:
            return False, f"Invalid TCP window size: {record.window_size}"

    if hasattr(record, 'total_packets') and record.total_packets is not None:
        if record.total_packets < 0:
            return False, f"Negative total_packets: {record.total_packets}"

    if hasattr(record, 'total_bytes') and record.total_bytes is not None:
        if record.total_bytes < 0:
            return False, f"Negative total_bytes: {record.total_bytes}"

    return True, None
