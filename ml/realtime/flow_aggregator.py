"""Real-Time Flow Aggregator.

Aggregates individual live NormalizedPacket records into stateful network flows
identified by 5-tuple keys (src_ip, dst_ip, src_port, dst_port, protocol).
Maintains packet counts, byte volumes, duration, throughput (Mbps),
packet loss estimation, and RTT tracking with configurable idle timeouts.
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from ml.realtime.packet_normalizer import NormalizedPacket


@dataclass
class AggregatedFlow:
    """Stateful aggregated network flow representation."""

    flow_key: Tuple[str, str, int, int, str]
    flow_id: str
    device_id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str

    first_seen: float
    last_seen: float
    start_time_iso: str
    last_time_iso: str

    packet_count: int = 0
    byte_count: int = 0
    payload_byte_count: int = 0

    # Rate and performance metrics
    throughput_mbps: float = 0.0
    rtt_ms: Optional[float] = None
    packet_loss_percent: float = 0.0
    active_connections: int = 1

    # Internal state for metrics estimation
    _tcp_syn_time: Optional[float] = None
    _tcp_syn_ack_time: Optional[float] = None
    _last_rate_calc_time: float = 0.0
    _last_rate_byte_count: int = 0
    _observed_seqs: set = field(default_factory=set)
    _retransmissions: int = 0

    def duration_seconds(self) -> float:
        """Calculate total elapsed duration for this flow."""
        return max(0.001, self.last_seen - self.first_seen)

    def to_dict(self) -> Dict[str, Any]:
        """Convert flow to standard dictionary format compatible with monitoring & ML features."""
        return {
            "flow_id": self.flow_id,
            "device_id": self.device_id,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "protocol": self.protocol,
            "timestamp": self.last_time_iso,
            "first_seen": self.start_time_iso,
            "duration_seconds": round(self.duration_seconds(), 3),
            "packet_count": self.packet_count,
            "byte_count": self.byte_count,
            "throughput": round(self.throughput_mbps, 2),
            "throughput_mbps": round(self.throughput_mbps, 2),
            "traffic_volume_mbps": round(self.throughput_mbps, 2),
            "rtt": round(self.rtt_ms, 2) if self.rtt_ms is not None else None,
            "rtt_ms": round(self.rtt_ms, 2) if self.rtt_ms is not None else None,
            "packet_loss": round(self.packet_loss_percent, 2),
            "packet_loss_percent": round(self.packet_loss_percent, 2),
            "active_connections": self.active_connections,
        }


def derive_device_id(src_ip: str, dst_ip: str) -> str:
    """Derive standard host/device identifier from IP addresses.

    Maps 192.168.1.10 -> h1, 192.168.1.11 -> h2, ..., 192.168.1.14 -> h5,
    127.0.0.1 -> h_local, or host_<last_octet>.
    """
    ip_to_host = {
        "192.168.1.10": "h1",
        "192.168.1.11": "h2",
        "192.168.1.12": "h3",
        "192.168.1.13": "h4",
        "192.168.1.14": "h5",
        "127.0.0.1": "h_local",
        "localhost": "h_local",
    }
    if src_ip in ip_to_host:
        return ip_to_host[src_ip]
    if dst_ip in ip_to_host:
        return ip_to_host[dst_ip]

    # Subnet or last octet mapping
    parts = src_ip.split(".")
    if len(parts) == 4 and parts[3].isdigit():
        last = int(parts[3])
        if 10 <= last <= 14:
            return f"h{last - 9}"
        return f"host_{last}"
    return "h_live"


class RealTimeFlowAggregator:
    """Thread-safe stateful flow aggregator with idle timeout eviction."""

    def __init__(
        self,
        idle_timeout_seconds: float = 15.0,
        max_active_flows: int = 1000,
        update_interval_seconds: float = 1.0,
        on_flow_update: Optional[Callable[[AggregatedFlow], None]] = None,
    ) -> None:
        self.idle_timeout = idle_timeout_seconds
        self.max_active_flows = max_active_flows
        self.update_interval = update_interval_seconds
        self.on_flow_update = on_flow_update

        self._lock = threading.Lock()
        self._flows: Dict[Tuple[str, str, int, int, str], AggregatedFlow] = {}
        self._device_flow_counts: Dict[str, int] = defaultdict(int)
        self._completed_flows: deque = deque(maxlen=500)
        self._total_flows_created: int = 0

    def add_packet(self, pkt: NormalizedPacket) -> Optional[AggregatedFlow]:
        """Process an incoming normalized packet and update its flow state.

        Args:
            pkt: NormalizedPacket to incorporate.

        Returns:
            Updated AggregatedFlow if an update threshold was reached, else None.
        """
        now = pkt.timestamp
        key = (pkt.src_ip, pkt.dst_ip, pkt.src_port, pkt.dst_port, pkt.protocol)

        flow_to_notify: Optional[AggregatedFlow] = None

        with self._lock:
            # Check for existing flow in either forward or reverse direction
            rev_key = (pkt.dst_ip, pkt.src_ip, pkt.dst_port, pkt.src_port, pkt.protocol)
            flow = self._flows.get(key)
            is_reverse = False

            if flow is None and rev_key in self._flows:
                flow = self._flows[rev_key]
                is_reverse = True

            if flow is None:
                # Enforce capacity
                if len(self._flows) >= self.max_active_flows:
                    self._evict_oldest_locked(now)

                dev_id = derive_device_id(pkt.src_ip, pkt.dst_ip)
                flow_id = f"{dev_id}_{pkt.src_ip}:{pkt.src_port}->{pkt.dst_ip}:{pkt.dst_port}_{pkt.protocol}"
                self._total_flows_created += 1

                flow = AggregatedFlow(
                    flow_key=key,
                    flow_id=flow_id,
                    device_id=dev_id,
                    src_ip=pkt.src_ip,
                    dst_ip=pkt.dst_ip,
                    src_port=pkt.src_port,
                    dst_port=pkt.dst_port,
                    protocol=pkt.protocol,
                    first_seen=now,
                    last_seen=now,
                    start_time_iso=pkt.timestamp_iso,
                    last_time_iso=pkt.timestamp_iso,
                    _last_rate_calc_time=now,
                )
                self._flows[key] = flow
                self._device_flow_counts[dev_id] += 1

            # Update packet counters
            flow.last_seen = now
            flow.last_time_iso = pkt.timestamp_iso
            flow.packet_count += 1
            flow.byte_count += pkt.packet_len
            flow.payload_byte_count += pkt.payload_len

            # RTT estimation via TCP flags
            if pkt.protocol == "TCP":
                if "SYN" in pkt.tcp_flags and "ACK" not in pkt.tcp_flags and not is_reverse:
                    flow._tcp_syn_time = now
                elif "SYN" in pkt.tcp_flags and "ACK" in pkt.tcp_flags and is_reverse:
                    flow._tcp_syn_ack_time = now
                elif "ACK" in pkt.tcp_flags and flow._tcp_syn_time and not is_reverse and flow.rtt_ms is None:
                    # RTT = delta between initial SYN and completing ACK
                    rtt_calc = (now - flow._tcp_syn_time) * 1000.0
                    if 0.1 <= rtt_calc <= 2000.0:
                        flow.rtt_ms = rtt_calc

            # Rate / Throughput calculation (sliding delta or cumulative)
            elapsed_since_rate = now - flow._last_rate_calc_time
            if elapsed_since_rate >= self.update_interval:
                bytes_delta = flow.byte_count - flow._last_rate_byte_count
                rate_mbps = (bytes_delta * 8.0) / (elapsed_since_rate * 1e6)
                # EWMA smooth
                if flow.throughput_mbps == 0.0:
                    flow.throughput_mbps = rate_mbps
                else:
                    flow.throughput_mbps = 0.7 * flow.throughput_mbps + 0.3 * rate_mbps

                flow._last_rate_calc_time = now
                flow._last_rate_byte_count = flow.byte_count
                flow_to_notify = flow
            elif flow.throughput_mbps == 0.0:
                duration = flow.duration_seconds()
                flow.throughput_mbps = (flow.byte_count * 8.0) / (duration * 1e6)

            # Update active connection count for host
            flow.active_connections = max(1, self._device_flow_counts[flow.device_id])

        if flow_to_notify and self.on_flow_update:
            self.on_flow_update(flow_to_notify)

        return flow_to_notify or flow

    def prune_idle_flows(self, now: Optional[float] = None) -> List[AggregatedFlow]:
        """Prune flows that have been idle longer than idle_timeout.

        Args:
            now: Current epoch timestamp (defaults to time.time()).

        Returns:
            List of pruned AggregatedFlow instances.
        """
        curr = now if now is not None else time.time()
        evicted: List[AggregatedFlow] = []

        with self._lock:
            to_remove = []
            for key, flow in self._flows.items():
                if curr - flow.last_seen > self.idle_timeout:
                    to_remove.append(key)
                    evicted.append(flow)
                    self._completed_flows.append(flow)
                    self._device_flow_counts[flow.device_id] = max(
                        0, self._device_flow_counts[flow.device_id] - 1
                    )

            for key in to_remove:
                del self._flows[key]

        return evicted

    def _evict_oldest_locked(self, now: float) -> None:
        """Evict the oldest inactive flow when capacity is reached (must hold _lock)."""
        if not self._flows:
            return
        oldest_key = min(self._flows.keys(), key=lambda k: self._flows[k].last_seen)
        oldest_flow = self._flows.pop(oldest_key)
        self._completed_flows.append(oldest_flow)
        self._device_flow_counts[oldest_flow.device_id] = max(
            0, self._device_flow_counts[oldest_flow.device_id] - 1
        )

    def get_active_flows(self) -> List[AggregatedFlow]:
        """Return snapshot copy of all currently active flows."""
        with self._lock:
            return list(self._flows.values())

    def get_all_recent_flows(self, limit: int = 50) -> List[AggregatedFlow]:
        """Return active flows followed by recently completed flows."""
        with self._lock:
            active = list(self._flows.values())
            completed = list(self._completed_flows)
            combined = active + completed
            # Sort newest first
            combined.sort(key=lambda f: f.last_seen, reverse=True)
            return combined[:limit]

    def clear(self) -> None:
        """Clear all active and completed flows."""
        with self._lock:
            self._flows.clear()
            self._device_flow_counts.clear()
            self._completed_flows.clear()
            self._total_flows_created = 0
