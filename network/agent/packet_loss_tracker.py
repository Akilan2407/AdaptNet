"""
Packet Loss Tracker — computes real packet loss from live captured traffic.

Four complementary detection methods used together:

Method 1 — TCP Sequence Number Gap Detection:
  Per RFC 793, a sender increments the sequence number by the number of bytes
  sent. By tracking the highest expected next-seq# and observing gaps in
  the received sequence space, we detect dropped packets.
  This is the same algorithm used by tcpdump, Wireshark, and ss(8).

Method 2 — TCP Duplicate ACK / Triple-Dup ACK Detection:
  Per RFC 5681 (TCP Fast Retransmit), three consecutive duplicate ACKs
  (same ack_num, no data) indicate a packet was lost in transit.
  We count duplicate ACK events per flow.

Method 3 — TCP Retransmission Detection:
  A retransmission is detected when a segment's seq_num is strictly less than
  the expected next seq# for that flow — i.e., the sender is re-sending
  data that was already acknowledged or expected to be in-flight.

Method 4 — ICMP Destination Unreachable / Time Exceeded:
  ICMP type 3 (Destination Unreachable) and type 11 (Time Exceeded)
  indicate packet drops at intermediate routers or firewalls.

All packet loss metrics are derived from real captured packets.
No synthetic values are used.
"""

import time
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from network.agent.packet_sniffer import (
    CapturedPacket,
    IPPROTO_TCP,
    IPPROTO_ICMP,
    TCP_FLAG_SYN,
    TCP_FLAG_ACK,
    TCP_FLAG_FIN,
    TCP_FLAG_RST,
    TCP_FLAG_PSH,
)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

ICMP_TYPE_DEST_UNREACHABLE = 3
ICMP_TYPE_TIME_EXCEEDED    = 11
ICMP_TYPE_ECHO_REQUEST     = 8
ICMP_TYPE_ECHO_REPLY       = 0

TRIPLE_DUP_ACK_THRESHOLD = 3     # RFC 5681: 3 dupacks = loss signal
SEQ_WINDOW_SIZE           = 65535 # bytes — seq space wrapping window
MAX_FLOW_HISTORY          = 1000  # max sequence numbers tracked per flow

FLOW_EXPIRE_SEC = 120.0           # expire inactive flows after 2 minutes


# ──────────────────────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FlowLossState:
    """Packet loss state tracked per TCP flow (unidirectional)."""
    flow_key: str

    # Sequence number tracking
    next_expected_seq: Optional[int] = None   # what we expect next
    max_seen_seq: int = 0                      # highest seq+len seen

    # Counters (real events from wire)
    total_segments: int = 0
    lost_segments: int = 0      # sequence gaps detected
    retransmits: int = 0        # retransmitted segments
    out_of_order: int = 0       # out-of-order arrivals (not necessarily lost)

    # Duplicate ACK tracking
    last_ack_num: Optional[int] = None
    dup_ack_count: int = 0
    total_dup_acks: int = 0
    triple_dup_ack_events: int = 0

    # Timestamps
    last_seen: float = field(default_factory=time.monotonic)

    @property
    def packet_loss_pct(self) -> float:
        """Real packet loss percentage based on seq-gap detection."""
        total = self.total_segments + self.lost_segments
        if total == 0:
            return 0.0
        return round((self.lost_segments / total) * 100.0, 4)

    @property
    def retransmit_rate_pct(self) -> float:
        """Percentage of segments that were retransmissions."""
        if self.total_segments == 0:
            return 0.0
        return round((self.retransmits / self.total_segments) * 100.0, 4)


@dataclass
class ICMPLossEvent:
    """An ICMP-signaled packet drop event."""
    timestamp: float
    src_ip: str         # original packet source
    dst_ip: str         # original packet destination
    icmp_type: int      # 3 = dest unreachable, 11 = time exceeded
    icmp_code: int      # sub-type (e.g., code 0 = net unreachable)
    reporter_ip: str    # which router/host sent the ICMP message


@dataclass
class OverallLossStats:
    """Aggregate loss statistics across all flows."""
    total_segments: int = 0
    total_losses: int = 0
    total_retransmits: int = 0
    total_dup_acks: int = 0
    total_triple_dup_acks: int = 0
    icmp_loss_events: int = 0
    flows_tracked: int = 0

    @property
    def overall_loss_pct(self) -> float:
        total = self.total_segments + self.total_losses
        if total == 0:
            return 0.0
        return round((self.total_losses / total) * 100.0, 4)


# ──────────────────────────────────────────────────────────────────────────────
# Packet Loss Tracker
# ──────────────────────────────────────────────────────────────────────────────

class PacketLossTracker:
    """
    Tracks real packet loss by monitoring TCP sequence numbers and ACKs
    from live captured packets. No synthetic values.

    Usage:
        tracker = PacketLossTracker()
        sniffer = PacketSniffer(callback=tracker.on_packet)
        sniffer.start()
        ...
        loss_pct = tracker.get_loss_for_flow(src_ip, src_port, dst_ip, dst_port)
    """

    def __init__(self) -> None:
        self._flows: Dict[str, FlowLossState] = {}
        self._icmp_events: deque = deque(maxlen=500)
        self._lock = threading.Lock()

    # ── Public API ─────────────────────────────────────────────────────────────

    def on_packet(self, pkt: CapturedPacket) -> None:
        """Process a captured packet. Thread-safe."""
        if pkt.ip is None:
            return

        now = pkt.timestamp if pkt.timestamp else time.monotonic()
        proto = pkt.ip.protocol

        with self._lock:
            if proto == IPPROTO_TCP and pkt.tcp is not None:
                self._process_tcp(pkt, now)
            elif proto == IPPROTO_ICMP and pkt.icmp is not None:
                self._process_icmp(pkt, now)

    def get_loss_for_flow(
        self,
        src_ip: str, src_port: int,
        dst_ip: str, dst_port: int,
    ) -> Tuple[float, float]:
        """
        Returns (packet_loss_pct, retransmit_rate_pct) for a flow.
        Checks both directions.
        """
        key1 = _flow_key(src_ip, src_port, dst_ip, dst_port)
        key2 = _flow_key(dst_ip, dst_port, src_ip, src_port)

        with self._lock:
            for key in (key1, key2):
                state = self._flows.get(key)
                if state and state.total_segments > 0:
                    return state.packet_loss_pct, state.retransmit_rate_pct
        return 0.0, 0.0

    def get_all_stats(self) -> OverallLossStats:
        """Return aggregate loss statistics across all tracked flows."""
        with self._lock:
            stats = OverallLossStats()
            stats.flows_tracked = len(self._flows)
            stats.icmp_loss_events = len(self._icmp_events)
            for state in self._flows.values():
                stats.total_segments    += state.total_segments
                stats.total_losses      += state.lost_segments
                stats.total_retransmits += state.retransmits
                stats.total_dup_acks    += state.total_dup_acks
                stats.total_triple_dup_acks += state.triple_dup_ack_events
            return stats

    def get_icmp_loss_events(self, max_count: int = 50) -> List[ICMPLossEvent]:
        """Return recent ICMP-signaled loss events."""
        with self._lock:
            events = list(self._icmp_events)
        return events[-max_count:]

    def expire_stale_flows(self) -> int:
        """Remove flows that have been silent for > FLOW_EXPIRE_SEC. Returns count removed."""
        now = time.monotonic()
        with self._lock:
            stale = [k for k, v in self._flows.items() if (now - v.last_seen) > FLOW_EXPIRE_SEC]
            for k in stale:
                del self._flows[k]
        return len(stale)

    # ── TCP Sequence Analysis ──────────────────────────────────────────────────

    def _process_tcp(self, pkt: CapturedPacket, now: float) -> None:
        tcp = pkt.tcp
        key = _flow_key(pkt.src_ip, tcp.src_port, pkt.dst_ip, tcp.dst_port)
        state = self._get_or_create_flow(key)
        state.last_seen = now

        # ─ Method 3: Duplicate ACK detection ─────────────────────────────────
        # Pure ACK with no payload and same ack_num as last seen = duplicate ACK
        is_pure_ack = (
            tcp.flag_ack
            and not tcp.flag_syn
            and not tcp.flag_fin
            and pkt.payload_len == 0
        )

        if is_pure_ack:
            # We need the reverse direction state to check for dupacks
            rev_key = _flow_key(pkt.dst_ip, tcp.dst_port, pkt.src_ip, tcp.src_port)
            rev_state = self._get_or_create_flow(rev_key)
            rev_state.last_seen = now

            if rev_state.last_ack_num is not None and tcp.ack_num == rev_state.last_ack_num:
                rev_state.dup_ack_count += 1
                rev_state.total_dup_acks += 1

                if rev_state.dup_ack_count == TRIPLE_DUP_ACK_THRESHOLD:
                    rev_state.triple_dup_ack_events += 1
            else:
                rev_state.dup_ack_count = 0

            rev_state.last_ack_num = tcp.ack_num
            return   # pure ACKs don't carry sequence data to analyze

        # ─ Skip SYN/FIN/RST (they occupy 1 byte in seq space but carry no data) ─
        if tcp.flag_syn or tcp.flag_rst:
            if tcp.flag_syn:
                state.next_expected_seq = (tcp.seq_num + 1) & 0xFFFFFFFF
                state.max_seen_seq = state.next_expected_seq
            return

        if pkt.payload_len == 0:
            # FIN or ACK without data — advance seq by 1 for FIN
            if tcp.flag_fin:
                state.next_expected_seq = (tcp.seq_num + 1) & 0xFFFFFFFF
            return

        # ─ Data segment analysis ──────────────────────────────────────────────
        seg_seq   = tcp.seq_num
        seg_len   = pkt.payload_len
        seg_end   = (seg_seq + seg_len) & 0xFFFFFFFF

        state.total_segments += 1

        if state.next_expected_seq is None:
            # First data segment — initialize state
            state.next_expected_seq = seg_end
            state.max_seen_seq = seg_end
            return

        expected = state.next_expected_seq

        # ─ Method 3: Retransmission detection ────────────────────────────────
        # Retransmit = seq_num < expected (re-sending already-received data)
        if _seq_lt(seg_seq, expected):
            state.retransmits += 1
            # Update next_expected if this retransmit fills a gap
            if _seq_lt(expected, seg_end):
                state.next_expected_seq = seg_end
                if _seq_lt(state.max_seen_seq, seg_end):
                    state.max_seen_seq = seg_end
            return

        # ─ Method 1: Sequence gap detection ──────────────────────────────────
        # gap = seq_num > expected → bytes between expected and seq_num were lost
        if _seq_gt(seg_seq, expected):
            gap_bytes = _seq_diff(seg_seq, expected)

            # Heuristic: reasonable gap sizes (not wrap-around artifacts)
            if 1 <= gap_bytes <= 1_500_000:  # up to ~1000 full-size packets
                state.lost_segments += 1     # count as 1 loss event per gap
                state.out_of_order += 1

        # Advance expected sequence to end of this segment
        if _seq_lte(state.next_expected_seq, seg_end):
            state.next_expected_seq = seg_end
        if _seq_lt(state.max_seen_seq, seg_end):
            state.max_seen_seq = seg_end

    # ── ICMP Loss Detection ────────────────────────────────────────────────────

    def _process_icmp(self, pkt: CapturedPacket, now: float) -> None:
        icmp = pkt.icmp
        if icmp.icmp_type not in (ICMP_TYPE_DEST_UNREACHABLE, ICMP_TYPE_TIME_EXCEEDED):
            return

        event = ICMPLossEvent(
            timestamp=now,
            src_ip=pkt.src_ip,    # router/host sending the ICMP message
            dst_ip=pkt.dst_ip,    # original sender that gets notified
            icmp_type=icmp.icmp_type,
            icmp_code=icmp.code,
            reporter_ip=pkt.src_ip,
        )
        self._icmp_events.append(event)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_or_create_flow(self, key: str) -> FlowLossState:
        if key not in self._flows:
            self._flows[key] = FlowLossState(flow_key=key)
        return self._flows[key]


# ──────────────────────────────────────────────────────────────────────────────
# TCP Sequence Number Arithmetic (handles 32-bit wraparound)
# ──────────────────────────────────────────────────────────────────────────────

_SEQ_HALF = 0x80000000   # 2^31

def _seq_lt(a: int, b: int) -> bool:
    """Return True if sequence number a < b (with wrap-around)."""
    return ((b - a) & 0xFFFFFFFF) < _SEQ_HALF and a != b

def _seq_gt(a: int, b: int) -> bool:
    """Return True if sequence number a > b (with wrap-around)."""
    return _seq_lt(b, a)

def _seq_lte(a: int, b: int) -> bool:
    return a == b or _seq_lt(a, b)

def _seq_diff(a: int, b: int) -> int:
    """Unsigned difference a - b in sequence space (a >= b assumed)."""
    return (a - b) & 0xFFFFFFFF


# ──────────────────────────────────────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────────────────────────────────────

def _flow_key(src_ip: str, src_port: int, dst_ip: str, dst_port: int) -> str:
    return f"{src_ip}:{src_port}->{dst_ip}:{dst_port}"
