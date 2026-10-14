"""Packet Normalizer for Real-Time Packet Capture.

Transforms low-level CapturedPacket instances from network/agent/packet_sniffer.py
or raw dictionary events into standardized NormalizedPacket records.
Gracefully handles missing fields, unsupported protocols, and non-IP frames.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Union

# Try to import CapturedPacket from packet sniffer
try:
    from network.agent.packet_sniffer import CapturedPacket
except ImportError:
    CapturedPacket = None


@dataclass
class NormalizedPacket:
    """Standardized representation of a captured network frame."""

    packet_id: str
    timestamp: float                  # Epoch seconds (float)
    timestamp_iso: str              # ISO-8601 formatted UTC string
    interface: str
    protocol: str                   # "TCP", "UDP", "ICMP", "ARP", "OTHER"
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    packet_len: int                 # Total wire length in bytes
    payload_len: int                # Transport payload length in bytes
    tcp_flags: List[str] = field(default_factory=list)
    tcp_flags_str: str = ""
    window_size: int = 0
    ttl: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert normalized packet to a serializable dictionary."""
        return {
            "packet_id": self.packet_id,
            "timestamp": self.timestamp_iso,
            "epoch_timestamp": self.timestamp,
            "interface": self.interface,
            "protocol": self.protocol,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "packet_len": self.packet_len,
            "payload_len": self.payload_len,
            "tcp_flags": self.tcp_flags,
            "tcp_flags_str": self.tcp_flags_str,
            "window_size": self.window_size,
            "ttl": self.ttl,
        }


class PacketNormalizer:
    """Normalizes raw captured packets into structured, sanitized records."""

    def __init__(self) -> None:
        self._counter: int = 0

    def normalize(
        self,
        pkt: Union[Dict[str, Any], Any],
        default_iface: str = "default",
    ) -> NormalizedPacket:
        """Normalize an incoming packet object or dictionary.

        Args:
            pkt: CapturedPacket instance or dictionary representation.
            default_iface: Fallback network interface name.

        Returns:
            NormalizedPacket record.
        """
        self._counter += 1
        pkt_id = f"pkt_{self._counter}"
        now_ts = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        # Case 1: Packet is a dictionary
        if isinstance(pkt, dict):
            ts = float(pkt.get("epoch_timestamp") or pkt.get("monotonic_ts") or now_ts)
            iso_ts = str(pkt.get("timestamp") or now_iso)
            iface = str(pkt.get("interface") or default_iface)
            proto = str(pkt.get("protocol") or "OTHER").upper()
            src_ip = str(pkt.get("src_ip") or "0.0.0.0").strip()
            dst_ip = str(pkt.get("dst_ip") or "0.0.0.0").strip()
            src_p = int(pkt.get("src_port") or 0)
            dst_p = int(pkt.get("dst_port") or 0)
            pkt_len = int(pkt.get("packet_len") or 0)
            payload_len = int(pkt.get("payload_len") or 0)
            flags = list(pkt.get("tcp_flags") or [])
            flags_str = str(pkt.get("tcp_flags_str") or "")
            win = int(pkt.get("window_size") or 0)
            ttl = pkt.get("ttl")
            if ttl is not None:
                try:
                    ttl = int(ttl)
                except (ValueError, TypeError):
                    ttl = None

            return NormalizedPacket(
                packet_id=pkt_id,
                timestamp=ts,
                timestamp_iso=iso_ts,
                interface=iface,
                protocol=proto,
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_p,
                dst_port=dst_p,
                packet_len=pkt_len,
                payload_len=payload_len,
                tcp_flags=flags,
                tcp_flags_str=flags_str,
                window_size=win,
                ttl=ttl,
            )

        # Case 2: Packet is a CapturedPacket dataclass
        if CapturedPacket is not None and isinstance(pkt, CapturedPacket):
            ts = now_ts
            iso_ts = pkt.capture_timestamp or now_iso
            iface = pkt.iface or default_iface

            proto = (pkt.protocol_name or "OTHER").upper()
            if proto == "UNKNOWN" and pkt.ip:
                if pkt.ip.protocol == 6:
                    proto = "TCP"
                elif pkt.ip.protocol == 17:
                    proto = "UDP"
                elif pkt.ip.protocol == 1:
                    proto = "ICMP"

            src_ip = pkt.src_ip or (pkt.ip.src_ip if pkt.ip else "0.0.0.0")
            dst_ip = pkt.dst_ip or (pkt.ip.dst_ip if pkt.ip else "0.0.0.0")

            src_p = pkt.src_port
            dst_p = pkt.dst_port
            if src_p == 0 and pkt.tcp:
                src_p = pkt.tcp.src_port
                dst_p = pkt.tcp.dst_port
            elif src_p == 0 and pkt.udp:
                src_p = pkt.udp.src_port
                dst_p = pkt.udp.dst_port

            pkt_len = pkt.packet_len or (pkt.ip.total_length if pkt.ip else 0)
            payload_len = pkt.payload_len

            flags: List[str] = []
            flags_str = ""
            window_size = 0
            if pkt.tcp:
                t = pkt.tcp
                window_size = t.window_size
                if t.flag_syn:
                    flags.append("SYN"); flags_str += "S"
                if t.flag_ack:
                    flags.append("ACK"); flags_str += "A"
                if t.flag_fin:
                    flags.append("FIN"); flags_str += "F"
                if t.flag_rst:
                    flags.append("RST"); flags_str += "R"
                if t.flag_psh:
                    flags.append("PSH"); flags_str += "P"
                if t.flag_urg:
                    flags.append("URG"); flags_str += "U"

            ttl = pkt.ip.ttl if pkt.ip else None

            return NormalizedPacket(
                packet_id=pkt_id,
                timestamp=ts,
                timestamp_iso=iso_ts,
                interface=iface,
                protocol=proto,
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_p,
                dst_port=dst_p,
                packet_len=pkt_len,
                payload_len=payload_len,
                tcp_flags=flags,
                tcp_flags_str=flags_str,
                window_size=window_size,
                ttl=ttl,
            )

        # Fallback for generic object
        return NormalizedPacket(
            packet_id=pkt_id,
            timestamp=now_ts,
            timestamp_iso=now_iso,
            interface=default_iface,
            protocol=getattr(pkt, "protocol", "OTHER"),
            src_ip=getattr(pkt, "src_ip", "0.0.0.0"),
            dst_ip=getattr(pkt, "dst_ip", "0.0.0.0"),
            src_port=int(getattr(pkt, "src_port", 0) or 0),
            dst_port=int(getattr(pkt, "dst_port", 0) or 0),
            packet_len=int(getattr(pkt, "packet_len", 0) or 0),
            payload_len=int(getattr(pkt, "payload_len", 0) or 0),
        )
