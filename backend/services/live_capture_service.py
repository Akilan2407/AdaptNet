"""
Live Packet Capture Service.

Wraps the existing PacketSniffer from network/agent/packet_sniffer.py to provide
a bounded in-memory buffer of live packet events and real-time capture metrics.
"""

from collections import deque
import platform
import socket
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from network.agent.packet_sniffer import (
    CapturedPacket,
    PacketSniffer,
    _scapy_available,
)

MAX_BUFFER_DEFAULT = 1000
RATE_WINDOW_SECONDS = 3.0


class LiveCaptureService:
    """Singleton service managing live packet sniffing and in-memory ring buffering."""

    def __init__(self, max_buffer: int = MAX_BUFFER_DEFAULT):
        self.max_buffer = max_buffer
        self._buffer: deque = deque(maxlen=max_buffer)
        self._lock = threading.Lock()

        self._sniffer: Optional[PacketSniffer] = None
        self._status: str = "STOPPED"  # "STOPPED", "STARTING", "LIVE", "ERROR"
        self._error_message: Optional[str] = None
        self._capture_mode: str = "none"
        self._active_interface: str = "default"
        self._started_at: Optional[float] = None
        self._stopped_at: Optional[float] = None

        # Packet counters
        self._packet_seq: int = 0
        self._total_captured: int = 0
        self._tcp_count: int = 0
        self._udp_count: int = 0
        self._icmp_count: int = 0
        self._other_count: int = 0
        self._latest_timestamp: Optional[str] = None

        # Rate tracking (timestamps of recent arrivals)
        self._recent_timestamps: deque = deque(maxlen=500)

    # ── Packet Event Formatting ───────────────────────────────────────────────

    def _format_packet_event(self, pkt: CapturedPacket, seq_id: int) -> Dict[str, Any]:
        """Convert CapturedPacket into a clean, serializable JSON event dict."""
        tcp_flags = []
        tcp_flags_str = ""
        window_size = 0

        if pkt.tcp:
            t = pkt.tcp
            window_size = t.window_size
            if t.flag_syn:
                tcp_flags.append("SYN")
                tcp_flags_str += "S"
            if t.flag_ack:
                tcp_flags.append("ACK")
                tcp_flags_str += "A"
            if t.flag_fin:
                tcp_flags.append("FIN")
                tcp_flags_str += "F"
            if t.flag_rst:
                tcp_flags.append("RST")
                tcp_flags_str += "R"
            if t.flag_psh:
                tcp_flags.append("PSH")
                tcp_flags_str += "P"
            if t.flag_urg:
                tcp_flags.append("URG")
                tcp_flags_str += "U"

        # Determine readable protocol name
        proto = pkt.protocol_name.upper() if pkt.protocol_name else "UNKNOWN"
        if proto == "UNKNOWN" and pkt.ip:
            if pkt.ip.protocol == 6:
                proto = "TCP"
            elif pkt.ip.protocol == 17:
                proto = "UDP"
            elif pkt.ip.protocol == 1:
                proto = "ICMP"

        return {
            "id": f"pkt_{seq_id}",
            "seq": seq_id,
            "timestamp": pkt.capture_timestamp or time.strftime("%Y-%m-%d %H:%M:%S"),
            "monotonic_ts": round(pkt.timestamp, 4) if pkt.timestamp else time.monotonic(),
            "interface": pkt.iface or self._active_interface,
            "protocol": proto,
            "src_ip": pkt.src_ip or (pkt.ip.src_ip if pkt.ip else "—"),
            "dst_ip": pkt.dst_ip or (pkt.ip.dst_ip if pkt.ip else "—"),
            "src_port": pkt.src_port or (pkt.tcp.src_port if pkt.tcp else (pkt.udp.src_port if pkt.udp else None)),
            "dst_port": pkt.dst_port or (pkt.tcp.dst_port if pkt.tcp else (pkt.udp.dst_port if pkt.udp else None)),
            "packet_len": pkt.packet_len or (pkt.ip.total_length if pkt.ip else 0),
            "payload_len": pkt.payload_len,
            "tcp_flags": tcp_flags,
            "tcp_flags_str": tcp_flags_str,
            "window_size": window_size,
            "ttl": pkt.ip.ttl if pkt.ip else None,
        }

    def _on_packet_arrived(self, pkt: CapturedPacket) -> None:
        """Callback invoked by PacketSniffer on every captured packet."""
        now = time.monotonic()
        with self._lock:
            self._packet_seq += 1
            seq = self._packet_seq
            event = self._format_packet_event(pkt, seq)

            self._buffer.append(event)
            self._total_captured += 1
            self._latest_timestamp = event["timestamp"]

            proto = event["protocol"]
            if proto == "TCP":
                self._tcp_count += 1
            elif proto == "UDP":
                self._udp_count += 1
            elif proto == "ICMP":
                self._icmp_count += 1
            else:
                self._other_count += 1

        # Feed real-time packet into ML processing pipeline
        try:
            from ml.realtime.pipeline_manager import pipeline_manager
            pipeline_manager.enqueue_packet(pkt)
        except Exception:
            pass

    def _on_sniffer_error(self, err_msg: str) -> None:
        """Handle async errors from background capture threads."""
        with self._lock:
            self._status = "ERROR"
            self._error_message = err_msg

    # ── Lifecycle Controls ───────────────────────────────────────────────────

    def start(self, interface: Optional[str] = None, bpf_filter: str = "") -> Tuple[bool, str]:
        """Start the live packet sniffer on the given interface."""
        with self._lock:
            if self._status == "LIVE" and self._sniffer is not None:
                return True, "Capture already active."

            self._status = "STARTING"
            self._error_message = None
            self._active_interface = interface if interface else "default"

        try:
            sniffer = PacketSniffer(
                iface=interface if interface and interface != "default" else None,
                bpf_filter=bpf_filter,
                callback=self._on_packet_arrived,
                error_callback=self._on_sniffer_error,
                max_buffer=self.max_buffer,
            )
            mode_desc = sniffer.start()

            with self._lock:
                if mode_desc.startswith("no_capture"):
                    self._status = "ERROR"
                    self._error_message = mode_desc
                    self._capture_mode = "none"
                    return False, mode_desc

                self._sniffer = sniffer
                self._status = "LIVE"
                self._capture_mode = mode_desc
                self._started_at = time.time()
                self._stopped_at = None

            # Start real-time ML processing pipeline worker
            try:
                from ml.realtime.pipeline_manager import pipeline_manager
                pipeline_manager.start()
            except Exception as pe_err:
                logger.warning("Pipeline manager start warning: %s", pe_err)

            return True, f"Capture active via {mode_desc}"

        except PermissionError as pe:
            with self._lock:
                self._status = "ERROR"
                self._error_message = f"Permission denied: {str(pe)}. Administrator or root access required."
            return False, self._error_message
        except Exception as e:
            with self._lock:
                self._status = "ERROR"
                self._error_message = f"Failed to start sniffer: {str(e)}"
            return False, self._error_message

    def stop(self) -> Tuple[bool, str]:
        """Stop packet capture cleanly."""
        sniffer_to_stop = None
        with self._lock:
            if self._status == "STOPPED":
                return True, "Capture is already stopped."
            sniffer_to_stop = self._sniffer
            self._sniffer = None
            self._status = "STOPPED"
            self._stopped_at = time.time()

        if sniffer_to_stop:
            try:
                sniffer_to_stop.stop()
            except Exception as e:
                return False, f"Error stopping sniffer: {str(e)}"

        # Stop real-time ML pipeline worker
        try:
            from ml.realtime.pipeline_manager import pipeline_manager
            pipeline_manager.stop()
        except Exception:
            pass

        return True, "Capture stopped."

    def clear(self) -> None:
        """Clear the in-memory packet buffer and reset arrival rates."""
        with self._lock:
            self._buffer.clear()
            self._recent_timestamps.clear()

        # Clear ML pipeline buffers
        try:
            from ml.realtime.pipeline_manager import pipeline_manager
            pipeline_manager.clear()
        except Exception:
            pass

    # ── Metrics & Queries ────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return snapshot of live capture statistics."""
        now = time.monotonic()
        with self._lock:
            # Calculate current arrival rate over RATE_WINDOW_SECONDS
            cutoff = now - RATE_WINDOW_SECONDS
            recent_count = sum(1 for t in self._recent_timestamps if t >= cutoff)
            rate_pps = round(recent_count / RATE_WINDOW_SECONDS, 2) if recent_count > 0 else 0.0

            uptime = 0.0
            if self._started_at:
                end_time = self._stopped_at or time.time()
                uptime = round(end_time - self._started_at, 1)

            return {
                "status": self._status,
                "capture_mode": self._capture_mode,
                "interface": self._active_interface,
                "error_message": self._error_message,
                "total_captured": self._total_captured,
                "tcp_count": self._tcp_count,
                "udp_count": self._udp_count,
                "icmp_count": self._icmp_count,
                "other_count": self._other_count,
                "buffer_size": len(self._buffer),
                "buffer_capacity": self.max_buffer,
                "latest_timestamp": self._latest_timestamp,
                "packets_per_second": rate_pps,
                "uptime_seconds": uptime,
                "is_live": self._status == "LIVE",
                "scapy_available": _scapy_available(),
                "os": platform.system(),
                "source": "live_wire_capture",
            }

    def get_packets(
        self,
        limit: int = 50,
        offset: int = 0,
        protocol: Optional[str] = None,
        ip_query: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Query buffered packets in reverse chronological order (newest first).
        Returns (records, total_matching).
        """
        with self._lock:
            items = list(self._buffer)

        # Reverse so newest is first
        items.reverse()

        # Apply protocol filter
        if protocol and protocol.upper() != "ALL":
            p_upper = protocol.upper()
            items = [item for item in items if item["protocol"] == p_upper]

        # Apply IP/query filter
        if ip_query:
            q = ip_query.strip().lower()
            items = [
                item for item in items
                if q in str(item["src_ip"]).lower()
                or q in str(item["dst_ip"]).lower()
                or q in str(item.get("src_port", "")).lower()
                or q in str(item.get("dst_port", "")).lower()
                or q in str(item["protocol"]).lower()
            ]

        total = len(items)
        paginated = items[offset : offset + limit]
        return paginated, total

    @staticmethod
    def get_available_interfaces() -> List[Dict[str, Any]]:
        """List discoverable network interfaces on this machine."""
        ifaces: List[Dict[str, Any]] = [{"id": "default", "name": "Default / Auto-Detect", "is_up": True}]
        try:
            import psutil
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
            for iface_name, stat in stats.items():
                ip = ""
                if iface_name in addrs:
                    for addr in addrs[iface_name]:
                        if addr.family == socket.AF_INET:
                            ip = addr.address
                            break
                label = f"{iface_name} ({ip})" if ip else iface_name
                ifaces.append({"id": iface_name, "name": label, "is_up": stat.isup})
        except Exception:
            pass

        return ifaces


# Global singleton instance for Flask app lifecycle
live_capture_service = LiveCaptureService()
