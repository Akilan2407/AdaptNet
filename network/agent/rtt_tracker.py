"""
RTT (Round-Trip Time) Tracker — computed directly from real TCP handshake timing.

Two complementary methods are implemented:

Method 1 — TCP SYN/SYN-ACK Timing (true network RTT):
  - When a TCP SYN is observed on a flow, the sender timestamp is recorded.
  - When the corresponding SYN-ACK arrives, the delta is the handshake RTT.
  - This mirrors how tools like Wireshark, tcptrace, and ss(8) compute RTT.

Method 2 — TCP Data/ACK Timing (per-segment RTT):
  - When a data segment is sent (PSH flag + payload > 0), record the seq#.
  - When the corresponding ACK (ack_num = seq + payload_len) is observed,
    the delta is the RTT for that segment.
  - This is the same approach used by TCP's RTO estimation (RFC 6298).

Method 3 — ICMP Echo Request/Reply RTT:
  - ICMP echo requests are tagged with (src_ip, identifier, sequence).
  - ICMP echo replies matching the identifier+sequence are used to
    compute RTT — exactly how `ping` works internally.

All values are in milliseconds (ms) from monotonic clock deltas.
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
    TCP_FLAG_PSH,
)


# ──────────────────────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────────────────────

# Flow key: (src_ip, src_port, dst_ip, dst_port, protocol)
FlowKey = Tuple[str, int, str, int, str]

MAX_RTT_HISTORY  = 50     # samples kept per flow
SYN_TIMEOUT_SEC  = 10.0   # expire unmatched SYNs after 10s
SEG_TIMEOUT_SEC  = 5.0    # expire unmatched data segments after 5s
ICMP_TIMEOUT_SEC = 5.0    # expire unmatched ICMP echo requests after 5s


@dataclass
class RTTSample:
    timestamp: float       # monotonic time when RTT was measured
    rtt_ms: float          # measured RTT in milliseconds
    method: str            # "syn_synack", "data_ack", "icmp_echo"
    flow_key: str          # human-readable flow ID


@dataclass
class FlowRTTState:
    """Tracks RTT state for a single flow."""
    flow_key: str
    rtt_samples: deque = field(default_factory=lambda: deque(maxlen=MAX_RTT_HISTORY))

    # SYN tracking (seq_num -> send_timestamp)
    pending_syns: Dict[int, float] = field(default_factory=dict)

    # Data segment tracking: (seq_num, expected_ack) -> send_timestamp
    pending_segs: Dict[Tuple[int, int], float] = field(default_factory=dict)

    # Computed metrics
    last_rtt_ms: Optional[float] = None
    mean_rtt_ms: Optional[float] = None
    min_rtt_ms:  Optional[float] = None
    max_rtt_ms:  Optional[float] = None
    jitter_ms:   Optional[float] = None    # mean absolute deviation of RTT

    def add_sample(self, rtt_ms: float, method: str) -> None:
        sample = RTTSample(
            timestamp=time.monotonic(),
            rtt_ms=rtt_ms,
            method=method,
            flow_key=self.flow_key,
        )
        self.rtt_samples.append(sample)
        self._update_stats()

    def _update_stats(self) -> None:
        if not self.rtt_samples:
            return
        values = [s.rtt_ms for s in self.rtt_samples]
        n = len(values)
        mean = sum(values) / n
        self.last_rtt_ms = values[-1]
        self.mean_rtt_ms = round(mean, 3)
        self.min_rtt_ms  = round(min(values), 3)
        self.max_rtt_ms  = round(max(values), 3)
        # Jitter = mean absolute deviation
        self.jitter_ms   = round(sum(abs(v - mean) for v in values) / n, 3)

    def expire_stale(self, now: float) -> None:
        """Remove stale pending entries to prevent memory growth."""
        self.pending_syns = {
            seq: ts for seq, ts in self.pending_syns.items()
            if (now - ts) < SYN_TIMEOUT_SEC
        }
        self.pending_segs = {
            key: ts for key, ts in self.pending_segs.items()
            if (now - ts) < SEG_TIMEOUT_SEC
        }


@dataclass
class ICMPEchoEntry:
    """Pending ICMP echo request."""
    src_ip: str
    dst_ip: str
    identifier: int
    seq_num: int
    send_time: float        # monotonic


# ──────────────────────────────────────────────────────────────────────────────
# RTT Tracker
# ──────────────────────────────────────────────────────────────────────────────

class RTTTracker:
    """
    Tracks Round-Trip Time for TCP flows and ICMP pings by observing
    real packet captures delivered from PacketSniffer callbacks.

    Thread-safe; designed to be called from PacketSniffer's callback.
    """

    def __init__(self) -> None:
        self._flows: Dict[str, FlowRTTState] = {}
        self._icmp_pending: Dict[Tuple[str, int, int], ICMPEchoEntry] = {}
        self._icmp_rtt_samples: deque = deque(maxlen=200)
        self._lock = threading.Lock()
        self._total_rtt_computed = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    def on_packet(self, pkt: CapturedPacket) -> None:
        """Process a captured packet to update RTT state. Thread-safe."""
        if pkt.ip is None:
            return

        proto = pkt.ip.protocol
        now = pkt.timestamp if pkt.timestamp else time.monotonic()

        with self._lock:
            if proto == IPPROTO_TCP and pkt.tcp is not None:
                self._process_tcp_packet(pkt, now)
            elif proto == IPPROTO_ICMP and pkt.icmp is not None:
                self._process_icmp_packet(pkt, now)

    def get_flow_rtt(self, flow_key: str) -> Optional[FlowRTTState]:
        """Return RTT state for a flow key (thread-safe)."""
        with self._lock:
            return self._flows.get(flow_key)

    def get_all_flows(self) -> Dict[str, FlowRTTState]:
        """Return snapshot of all tracked flows (thread-safe)."""
        with self._lock:
            return dict(self._flows)

    def get_rtt_for_flow_tuple(
        self,
        src_ip: str, src_port: int,
        dst_ip: str, dst_port: int,
        protocol: str = "TCP",
    ) -> Optional[float]:
        """
        Convenience: return last RTT (ms) for a 5-tuple.
        Checks both directions of the flow.
        """
        key1 = _flow_key(src_ip, src_port, dst_ip, dst_port, protocol)
        key2 = _flow_key(dst_ip, dst_port, src_ip, src_port, protocol)

        with self._lock:
            for key in (key1, key2):
                state = self._flows.get(key)
                if state and state.last_rtt_ms is not None:
                    return state.last_rtt_ms
        return None

    def get_total_rtt_computed(self) -> int:
        with self._lock:
            return self._total_rtt_computed

    # ── TCP RTT Processing ─────────────────────────────────────────────────────

    def _process_tcp_packet(self, pkt: CapturedPacket, now: float) -> None:
        tcp = pkt.tcp
        src_ip, dst_ip = pkt.src_ip, pkt.dst_ip
        src_port, dst_port = tcp.src_port, tcp.dst_port

        fwd_key = _flow_key(src_ip, src_port, dst_ip, dst_port, "TCP")
        rev_key = _flow_key(dst_ip, dst_port, src_ip, src_port, "TCP")

        # Method 1: SYN → SYN-ACK timing
        if tcp.flag_syn and not tcp.flag_ack:
            # Outbound SYN — record timestamp
            state = self._get_or_create_flow(fwd_key)
            state.pending_syns[tcp.seq_num] = now

        elif tcp.flag_syn and tcp.flag_ack:
            # SYN-ACK received — look for matching SYN in reverse direction
            rev_state = self._flows.get(rev_key)
            if rev_state:
                # SYN-ACK's ack_num = original SYN seq_num + 1
                original_syn_seq = tcp.ack_num - 1
                syn_ts = rev_state.pending_syns.pop(original_syn_seq, None)
                if syn_ts is not None:
                    rtt_ms = (now - syn_ts) * 1000.0
                    if 0.01 <= rtt_ms <= 30000.0:   # sanity: 0.01ms — 30s
                        rev_state.add_sample(rtt_ms, "syn_synack")
                        self._total_rtt_computed += 1

        # Method 2: Data segment → ACK timing
        if tcp.flag_psh and pkt.payload_len > 0:
            # Data segment sent: record (seq_num, expected_ack)
            expected_ack = (tcp.seq_num + pkt.payload_len) & 0xFFFFFFFF
            state = self._get_or_create_flow(fwd_key)
            state.pending_segs[(tcp.seq_num, expected_ack)] = now

        if tcp.flag_ack and not tcp.flag_syn:
            # ACK received: match against pending data segments in reverse direction
            rev_state = self._flows.get(rev_key)
            if rev_state:
                # Find segment where expected_ack == this ack_num
                matched_key = None
                for (seq, exp_ack), seg_ts in rev_state.pending_segs.items():
                    if exp_ack == tcp.ack_num:
                        rtt_ms = (now - seg_ts) * 1000.0
                        if 0.01 <= rtt_ms <= 30000.0:
                            rev_state.add_sample(rtt_ms, "data_ack")
                            self._total_rtt_computed += 1
                        matched_key = (seq, exp_ack)
                        break
                if matched_key:
                    rev_state.pending_segs.pop(matched_key, None)

        # Periodic cleanup
        fwd_state = self._flows.get(fwd_key)
        if fwd_state:
            fwd_state.expire_stale(now)

    # ── ICMP RTT Processing ────────────────────────────────────────────────────

    def _process_icmp_packet(self, pkt: CapturedPacket, now: float) -> None:
        icmp = pkt.icmp
        # ICMP type 8 = Echo Request, type 0 = Echo Reply
        ICMP_ECHO_REQUEST = 8
        ICMP_ECHO_REPLY   = 0

        rest = icmp.rest_of_header  # upper 16 bits = identifier, lower 16 bits = seq
        identifier = (rest >> 16) & 0xFFFF
        seq_num    = rest & 0xFFFF

        if icmp.icmp_type == ICMP_ECHO_REQUEST:
            entry = ICMPEchoEntry(
                src_ip=pkt.src_ip,
                dst_ip=pkt.dst_ip,
                identifier=identifier,
                seq_num=seq_num,
                send_time=now,
            )
            self._icmp_pending[(pkt.src_ip, identifier, seq_num)] = entry

        elif icmp.icmp_type == ICMP_ECHO_REPLY:
            # Reply arrives at dst=original_src
            pending_key = (pkt.dst_ip, identifier, seq_num)
            entry = self._icmp_pending.pop(pending_key, None)
            if entry is not None:
                rtt_ms = (now - entry.send_time) * 1000.0
                if 0.01 <= rtt_ms <= 30000.0:
                    sample = RTTSample(
                        timestamp=now,
                        rtt_ms=rtt_ms,
                        method="icmp_echo",
                        flow_key=f"{entry.src_ip}->ICMP->{entry.dst_ip}",
                    )
                    self._icmp_rtt_samples.append(sample)
                    self._total_rtt_computed += 1

        # Expire stale ICMP entries
        self._icmp_pending = {
            k: v for k, v in self._icmp_pending.items()
            if (now - v.send_time) < ICMP_TIMEOUT_SEC
        }

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _get_or_create_flow(self, key: str) -> FlowRTTState:
        if key not in self._flows:
            self._flows[key] = FlowRTTState(flow_key=key)
        return self._flows[key]


# ──────────────────────────────────────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────────────────────────────────────

def _flow_key(src_ip: str, src_port: int, dst_ip: str, dst_port: int, proto: str) -> str:
    return f"{src_ip}:{src_port}->{dst_ip}:{dst_port}/{proto}"
