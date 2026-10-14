"""
Real-time network flow monitor backed by live packet capture.

Replaces the previous /proc/net/tcp kernel-table polling approach with
actual packet-level observation using the PacketSniffer, RTTTracker, and
PacketLossTracker modules.

What is computed from real captured packets:
  ─ Flow identification (src IP, dst IP, src port, dst port, protocol)
  ─ Throughput in Mbps (bytes captured per interval × 8 / interval)
  ─ RTT in milliseconds (TCP SYN/SYN-ACK timing, data/ACK timing)
  ─ Packet loss % (TCP sequence gap detection, duplicate ACK events)
  ─ Active connection count (flows with SYN seen but no FIN/RST)
  ─ TCP flag breakdown (SYN, ACK, FIN, RST, PSH seen per flow)
  ─ Window size (TCP advertised receive window, in bytes)
  ─ Payload bytes per flow

No synthetic values, no /proc table reads, no simulated fallbacks.
"""

import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from network.agent.network_stats import get_current_timestamp_str
from network.agent.packet_sniffer import (
    CapturedPacket,
    PacketSniffer,
    IPPROTO_TCP,
    IPPROTO_UDP,
    IPPROTO_ICMP,
    TCP_FLAG_SYN,
    TCP_FLAG_ACK,
    TCP_FLAG_FIN,
    TCP_FLAG_RST,
)
from network.agent.rtt_tracker import RTTTracker
from network.agent.packet_loss_tracker import PacketLossTracker


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

MAX_FLOWS_PER_SAMPLE = 64
FLOW_ACTIVE_TIMEOUT_SEC = 120.0    # flow considered closed after 2 minutes of silence
BITS_PER_BYTE = 8


# ──────────────────────────────────────────────────────────────────────────────
# FlowRecord — output data structure (unchanged interface for ML pipeline)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FlowRecord:
    """
    Structured per-flow measurement record derived from live packet capture.
    Maintains the same field interface as before so downstream ML pipeline
    (feature extractor, congestion model) requires no changes.
    """
    timestamp: str
    device_id: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str           # "TCP", "UDP", "ICMP"
    throughput_mbps: float  # computed from captured byte counts
    has_rtt: bool
    rtt_ms: float           # from TCP handshake or data/ACK timing
    has_packet_loss: bool
    packet_loss_pct: float  # from TCP sequence gap analysis
    active_tcp_connections: int = 0
    active_udp_connections: int = 0
    total_active_connections: int = 0

    # Extended real-capture fields (bonus data for ML feature enrichment)
    retransmit_pct: float = 0.0         # TCP retransmit rate
    jitter_ms: Optional[float] = None   # RTT mean absolute deviation
    window_size: int = 0                # Last TCP advertised window (bytes)
    total_packets: int = 0              # packets in this flow during interval
    total_bytes: int = 0                # bytes in this flow during interval
    dup_ack_events: int = 0             # duplicate ACK events (RFC 5681)
    syn_count: int = 0                  # SYN packets seen
    fin_count: int = 0                  # FIN packets seen
    rst_count: int = 0                  # RST packets seen
    capture_method: str = "packet_sniff"


# ──────────────────────────────────────────────────────────────────────────────
# Per-flow tracking state (internal use only)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FlowState:
    """Internal state for a flow being tracked during the current sample interval."""
    flow_key: str
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: str

    # Byte / packet counters (reset each interval)
    bytes_this_interval: int = 0
    packets_this_interval: int = 0

    # TCP state flags
    is_established: bool = False
    is_closed: bool = False          # FIN or RST seen
    syn_count: int = 0
    fin_count: int = 0
    rst_count: int = 0
    last_window_size: int = 0

    # Timing
    first_seen: float = field(default_factory=time.monotonic)
    last_seen: float = field(default_factory=time.monotonic)


# ──────────────────────────────────────────────────────────────────────────────
# FlowMonitor — the core monitoring engine
# ──────────────────────────────────────────────────────────────────────────────

class FlowMonitor:
    """
    Live network flow monitor using real packet capture.

    Aggregates per-interval byte counts, RTT measurements, and loss events
    from the PacketSniffer, RTTTracker, and PacketLossTracker.

    Usage:
        monitor = FlowMonitor(device_id="h1", iface="eth0")
        monitor.start()
        ...
        records = monitor.collect_sample(interval_sec=1.0)
        monitor.stop()
    """

    def __init__(
        self,
        device_id: str = "h1",
        iface: Optional[str] = None,
        max_flows: int = MAX_FLOWS_PER_SAMPLE,
    ) -> None:
        self.device_id = device_id
        self.iface = iface
        self.max_flows = max_flows

        # Networking subsystems
        self._rtt_tracker = RTTTracker()
        self._loss_tracker = PacketLossTracker()
        self._sniffer = PacketSniffer(
            iface=iface,
            callback=self._on_packet,
        )

        # Flow state table
        self._flows: Dict[str, FlowState] = {}
        self._interval_start: float = time.monotonic()
        self._lock = threading.Lock()

        self.capture_mode: str = "not_started"

    def start(self) -> str:
        """Start packet capture. Returns the capture mode description."""
        self.capture_mode = self._sniffer.start()
        self._interval_start = time.monotonic()
        return self.capture_mode

    def stop(self) -> None:
        """Stop packet capture cleanly."""
        self._sniffer.stop()

    def collect_sample(self, interval_sec: float) -> Tuple[List[FlowRecord], int, int]:
        """
        Collect a measurement snapshot for the just-elapsed interval.

        Returns:
            (flow_records, tcp_active_count, udp_active_count)
        """
        now = time.monotonic()

        with self._lock:
            flow_snapshot = dict(self._flows)
            # Reset per-interval byte/packet counters
            for state in self._flows.values():
                state.bytes_this_interval = 0
                state.packets_this_interval = 0
        self._interval_start = now

        records: List[FlowRecord] = []
        tcp_active = 0
        udp_active = 0
        ts = get_current_timestamp_str()

        # Remove stale flows
        self._loss_tracker.expire_stale_flows()

        for flow_key, state in list(flow_snapshot.items())[:self.max_flows]:
            # Skip flows that have been idle for too long
            if (now - state.last_seen) > FLOW_ACTIVE_TIMEOUT_SEC:
                continue

            # ── Throughput ─────────────────────────────────────────────────
            bytes_captured = state.bytes_this_interval
            throughput_mbps = 0.0
            if interval_sec > 0:
                throughput_mbps = round(
                    (bytes_captured * BITS_PER_BYTE) / (interval_sec * 1_000_000.0), 4
                )

            # ── RTT (from RTTTracker using real TCP timings) ───────────────
            rtt_ms = self._rtt_tracker.get_rtt_for_flow_tuple(
                state.src_ip, state.src_port,
                state.dst_ip, state.dst_port,
                state.protocol,
            )
            has_rtt = rtt_ms is not None and state.protocol == "TCP"
            rtt_val = rtt_ms if has_rtt else 0.0

            # Get full RTT state for jitter
            jitter_ms = None
            rtt_flow_key = f"{state.src_ip}:{state.src_port}->{state.dst_ip}:{state.dst_port}/TCP"
            rtt_state = self._rtt_tracker.get_flow_rtt(rtt_flow_key)
            if rtt_state:
                jitter_ms = rtt_state.jitter_ms

            # ── Packet Loss (from PacketLossTracker using seq# analysis) ──
            loss_pct, retransmit_pct = self._loss_tracker.get_loss_for_flow(
                state.src_ip, state.src_port,
                state.dst_ip, state.dst_port,
            )
            has_loss = (loss_pct > 0.0 or retransmit_pct > 0.0) and state.protocol == "TCP"

            # ── Active connection counting ─────────────────────────────────
            is_active = not state.is_closed and (now - state.last_seen) < 60.0

            if state.protocol == "TCP" and is_active:
                tcp_active += 1
            elif state.protocol == "UDP" and is_active:
                udp_active += 1

            record = FlowRecord(
                timestamp=ts,
                device_id=self.device_id,
                src_ip=state.src_ip,
                dst_ip=state.dst_ip,
                src_port=state.src_port,
                dst_port=state.dst_port,
                protocol=state.protocol,
                throughput_mbps=throughput_mbps,
                has_rtt=has_rtt,
                rtt_ms=rtt_val,
                has_packet_loss=has_loss,
                packet_loss_pct=loss_pct,
                retransmit_pct=retransmit_pct,
                jitter_ms=jitter_ms,
                window_size=state.last_window_size,
                total_packets=state.packets_this_interval,
                total_bytes=bytes_captured,
                syn_count=state.syn_count,
                fin_count=state.fin_count,
                rst_count=state.rst_count,
                capture_method=self.capture_mode,
            )
            records.append(record)

        # Fill active connection counts
        total_active = tcp_active + udp_active
        for r in records:
            r.active_tcp_connections = tcp_active
            r.active_udp_connections = udp_active
            r.total_active_connections = total_active

        return records, tcp_active, udp_active

    # ── Packet callback ────────────────────────────────────────────────────────

    def _on_packet(self, pkt: CapturedPacket) -> None:
        """
        Called by PacketSniffer for every captured packet.
        Updates flow state and forwards to RTT/loss trackers.
        """
        if pkt.ip is None:
            return

        # Forward to RTT and loss trackers
        self._rtt_tracker.on_packet(pkt)
        self._loss_tracker.on_packet(pkt)

        now = pkt.timestamp or time.monotonic()

        # Build flow key
        if pkt.protocol_name == "TCP" and pkt.tcp:
            proto = "TCP"
            src_port = pkt.tcp.src_port
            dst_port = pkt.tcp.dst_port
        elif pkt.protocol_name == "UDP" and pkt.udp:
            proto = "UDP"
            src_port = pkt.udp.src_port
            dst_port = pkt.udp.dst_port
        elif pkt.protocol_name == "ICMP":
            proto = "ICMP"
            src_port = 0
            dst_port = 0
        else:
            return  # skip non-IP/unknown protocols

        # Use canonical flow key (smaller IP first for bidirectional tracking)
        fwd_key = f"{pkt.src_ip}:{src_port}->{pkt.dst_ip}:{dst_port}/{proto}"

        with self._lock:
            if fwd_key not in self._flows:
                self._flows[fwd_key] = FlowState(
                    flow_key=fwd_key,
                    src_ip=pkt.src_ip,
                    dst_ip=pkt.dst_ip,
                    src_port=src_port,
                    dst_port=dst_port,
                    protocol=proto,
                    first_seen=now,
                )

            state = self._flows[fwd_key]
            state.last_seen = now
            state.bytes_this_interval += pkt.packet_len
            state.packets_this_interval += 1

            # TCP-specific flag tracking
            if proto == "TCP" and pkt.tcp:
                tcp = pkt.tcp
                if tcp.flag_syn and not tcp.flag_ack:
                    state.syn_count += 1
                if tcp.flag_syn and tcp.flag_ack:
                    state.is_established = True
                if tcp.flag_fin:
                    state.fin_count += 1
                    state.is_closed = True
                if tcp.flag_rst:
                    state.rst_count += 1
                    state.is_closed = True
                if tcp.window_size > 0:
                    state.last_window_size = tcp.window_size

        # Prune excessively large flow tables
        with self._lock:
            if len(self._flows) > self.max_flows * 4:
                # Remove oldest idle flows
                sorted_flows = sorted(
                    self._flows.items(),
                    key=lambda item: item[1].last_seen
                )
                for k, _ in sorted_flows[:len(self._flows) - self.max_flows * 2]:
                    del self._flows[k]

    def get_sniffer_stats(self) -> Dict:
        """Return raw packet capture statistics."""
        return self._sniffer.get_stats()

    def get_rtt_stats(self) -> Dict:
        """Return RTT computation statistics."""
        return {
            "total_rtt_computed": self._rtt_tracker.get_total_rtt_computed(),
            "flows_with_rtt": sum(
                1 for f in self._rtt_tracker.get_all_flows().values()
                if f.last_rtt_ms is not None
            ),
        }

    def get_loss_stats(self):
        """Return overall packet loss statistics."""
        return self._loss_tracker.get_all_stats()


# ──────────────────────────────────────────────────────────────────────────────
# Legacy-compatible scan_active_flows() interface
# (Used by monitor_agent.py — wraps FlowMonitor for backward compatibility)
# ──────────────────────────────────────────────────────────────────────────────

_global_monitor: Optional[FlowMonitor] = None
_global_monitor_lock = threading.Lock()
_global_last_interval: float = time.monotonic()


def init_flow_monitor(device_id: str, iface: Optional[str] = None) -> str:
    """
    Initialize the global FlowMonitor instance and start packet capture.
    Call once at agent startup before scan_active_flows().

    Returns capture mode description string.
    """
    global _global_monitor, _global_last_interval

    with _global_monitor_lock:
        if _global_monitor is not None:
            _global_monitor.stop()

        _global_monitor = FlowMonitor(device_id=device_id, iface=iface)
        _global_last_interval = time.monotonic()
        mode = _global_monitor.start()

    return mode


def scan_active_flows(
    device_id: str,
    current_throughput: float,          # kept for API compat; now computed from packets
    max_flows: int = MAX_FLOWS_PER_SAMPLE,
    interval_sec: float = 1.0,
) -> Tuple[List[FlowRecord], int, int]:
    """
    Collect a snapshot of active flows from live packet capture.

    This is the single public interface consumed by monitor_agent.py.
    Automatically initializes the FlowMonitor on first call.

    Returns:
        (flow_records, tcp_active_count, udp_active_count)
    """
    global _global_monitor, _global_last_interval

    with _global_monitor_lock:
        if _global_monitor is None:
            # Auto-initialize if not yet started
            _global_monitor = FlowMonitor(device_id=device_id)
            _global_monitor.start()
            _global_last_interval = time.monotonic()
            # Sleep briefly so sniffer can capture some packets before first sample
            time.sleep(min(interval_sec, 0.5))

        now = time.monotonic()
        elapsed = now - _global_last_interval
        _global_last_interval = now

        records, tcp_active, udp_active = _global_monitor.collect_sample(
            interval_sec=elapsed if elapsed > 0 else interval_sec
        )

    return records, tcp_active, udp_active


def stop_flow_monitor() -> None:
    """Stop the global FlowMonitor. Call at agent shutdown."""
    global _global_monitor
    with _global_monitor_lock:
        if _global_monitor is not None:
            _global_monitor.stop()
            _global_monitor = None
