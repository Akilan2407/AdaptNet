"""Native Python data structure and parser for network flow records (converted from record_parser.h/.c)."""

from dataclasses import dataclass
import time
from typing import Optional, Tuple


MAX_TIMESTAMP_STR = 32
MAX_DEVICE_NAME = 64
MAX_PROTO_STR = 8


@dataclass
class NetworkRecord:
    """Validated network flow record representation."""
    measurement_timestamp: str
    ingestion_timestamp: str
    device_id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str  # "TCP" or "UDP"
    throughput_mbps: float
    has_rtt: bool
    rtt_ms: Optional[float]
    has_packet_loss: bool
    packet_loss_pct: Optional[float]
    active_connections: int


def get_current_ingestion_timestamp() -> str:
    """Helper to get current wall-clock ingestion timestamp (YYYY-MM-DD HH:MM:SS)."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def parse_network_record(raw_line: str) -> Tuple[Optional[NetworkRecord], Optional[str]]:
    """Parse a pipe-delimited raw line into a NetworkRecord.

    Args:
        raw_line: String formatted as pipe-delimited fields.

    Returns:
        (record, None) on success, or (None, error_msg) on failure.
    """
    if not raw_line:
        return None, "Empty record line"

    line = raw_line.strip()
    if not line:
        return None, "Empty record line"

    # Schema:
    # 0: timestamp
    # 1: device_id
    # 2: src_ip
    # 3: dst_ip
    # 4: src_port
    # 5: dst_port
    # 6: protocol
    # 7: throughput
    # 8: rtt
    # 9: packet_loss
    # 10: active_connections
    tokens = line.split("|")
    if len(tokens) not in (11, 16):
        return None, f"Invalid field count: expected 11 or 16 fields, found {len(tokens)}"

    measurement_timestamp = tokens[0].strip()
    ingestion_timestamp = get_current_ingestion_timestamp()
    device_id = tokens[1].strip()
    src_ip = tokens[2].strip()
    dst_ip = tokens[3].strip()

    try:
        src_port = int(tokens[4].strip())
    except ValueError:
        return None, f"Invalid source port numeric value: '{tokens[4]}'"

    try:
        dst_port = int(tokens[5].strip())
    except ValueError:
        return None, f"Invalid destination port numeric value: '{tokens[5]}'"

    protocol = tokens[6].strip()

    try:
        throughput_mbps = float(tokens[7].strip())
    except ValueError:
        return None, f"Invalid throughput numeric value: '{tokens[7]}'"

    rtt_str = tokens[8].strip()
    if rtt_str.upper() == "N/A" or rtt_str == "":
        has_rtt = False
        rtt_ms = None
    else:
        try:
            has_rtt = True
            rtt_ms = float(rtt_str)
        except ValueError:
            return None, f"Invalid RTT numeric value: '{rtt_str}'"

    loss_str = tokens[9].strip()
    if loss_str.upper() == "N/A" or loss_str == "":
        has_packet_loss = False
        packet_loss_pct = None
    else:
        try:
            has_packet_loss = True
            packet_loss_pct = float(loss_str)
        except ValueError:
            return None, f"Invalid packet loss numeric value: '{loss_str}'"

    try:
        active_connections = int(tokens[10].strip())
    except ValueError:
        return None, f"Invalid active connections numeric value: '{tokens[10]}'"

    record = NetworkRecord(
        measurement_timestamp=measurement_timestamp,
        ingestion_timestamp=ingestion_timestamp,
        device_id=device_id,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        protocol=protocol,
        throughput_mbps=throughput_mbps,
        has_rtt=has_rtt,
        rtt_ms=rtt_ms,
        has_packet_loss=has_packet_loss,
        packet_loss_pct=packet_loss_pct,
        active_connections=active_connections,
    )
    return record, None
