"""
Network interface statistics — real OS counters only.

Sources (in priority order):
  1. Linux: /proc/net/dev — byte/packet/error counters per interface
  2. Cross-platform: psutil.net_io_counters() — wraps OS network APIs
  3. No synthetic fallback — if neither source works, zeros are returned
     with a clear error flag so callers know data is unavailable.

Also provides:
  - Real interface enumeration (list all non-loopback interfaces)
  - Real ICMP echo-based RTT probe (like ping, using raw ICMP socket)
  - Jitter calculation from consecutive RTT samples
"""

import os
import socket
import struct
import sys
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class InterfaceStats:
    """Snapshot of network interface packet and byte counters from the OS."""
    iface: str = "eth0"
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    rx_errors: int = 0
    tx_errors: int = 0
    rx_dropped: int = 0
    tx_dropped: int = 0
    timestamp: float = 0.0
    source: str = "unknown"     # "proc", "psutil", or "unavailable"
    available: bool = True      # False if OS could not provide data


@dataclass
class RTTProbeResult:
    """Result of an ICMP echo RTT probe."""
    target_ip: str
    rtt_ms: Optional[float]     # None if unreachable
    ttl: Optional[int]          # TTL from reply
    success: bool
    error: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# Timestamps
# ──────────────────────────────────────────────────────────────────────────────

def get_current_timestamp_str() -> str:
    """Current wall-clock time as YYYY-MM-DD HH:MM:SS."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def get_current_timestamp_ms() -> int:
    """Current epoch time in milliseconds."""
    return int(time.time() * 1000)


# ──────────────────────────────────────────────────────────────────────────────
# Throughput Calculation
# ──────────────────────────────────────────────────────────────────────────────

def calculate_throughput_mbps(bytes_delta: int, interval_seconds: float) -> float:
    """
    Convert a byte delta over a time interval to Mbps.
    bytes_delta must come from real OS interface counters.
    """
    if interval_seconds <= 0.0 or bytes_delta < 0:
        return 0.0
    return float(bytes_delta * 8.0) / float(interval_seconds * 1_000_000.0)


# ──────────────────────────────────────────────────────────────────────────────
# Interface Enumeration
# ──────────────────────────────────────────────────────────────────────────────

def list_interfaces() -> List[str]:
    """
    Return a list of all non-loopback network interfaces available on this host.
    Uses /proc/net/dev on Linux, psutil elsewhere.
    """
    ifaces: List[str] = []

    # Linux: /proc/net/dev
    if os.path.exists("/proc/net/dev"):
        try:
            with open("/proc/net/dev", "r") as f:
                lines = f.readlines()
            for line in lines[2:]:
                if ":" in line:
                    name = line.split(":")[0].strip()
                    if name and name != "lo":
                        ifaces.append(name)
            if ifaces:
                return ifaces
        except Exception:
            pass

    # psutil (macOS / Windows / BSD)
    try:
        import psutil
        for name in psutil.net_io_counters(pernic=True):
            if not name.startswith("lo"):
                ifaces.append(name)
        return ifaces
    except Exception:
        pass

    return []


def get_primary_interface() -> Optional[str]:
    """
    Return the name of the primary non-loopback network interface.
    Uses the routing table to find the interface with a default route on Linux,
    falls back to the first non-loopback interface.
    """
    # Try Linux routing table
    if os.path.exists("/proc/net/route"):
        try:
            with open("/proc/net/route", "r") as f:
                for line in f.readlines()[1:]:
                    fields = line.strip().split()
                    if len(fields) >= 4:
                        iface = fields[0]
                        destination = fields[1]
                        gateway = fields[2]
                        # Default route: destination == 00000000
                        if destination == "00000000" and gateway != "00000000":
                            return iface
        except Exception:
            pass

    # Fall back to first available non-loopback interface
    ifaces = list_interfaces()
    return ifaces[0] if ifaces else None


# ──────────────────────────────────────────────────────────────────────────────
# Interface Statistics — Real OS Counters
# ──────────────────────────────────────────────────────────────────────────────

def _read_linux_interface_stats(target_iface: Optional[str]) -> Optional[InterfaceStats]:
    """
    Parse /proc/net/dev on Linux.

    /proc/net/dev format (2 header lines, then per-iface lines):
    face |bytes    packets errs drop fifo frame compressed multicast|
         bytes    packets errs drop fifo colls carrier compressed
    eth0: 12345678 12345 0 0 0 0 0 0 | 9876543 9876 0 0 0 0 0 0
    Field indices after splitting on ':':
      RX: [0]=bytes [1]=packets [2]=errs [3]=drop
      TX: [8]=bytes [9]=packets [10]=errs [11]=drop
    """
    if not os.path.exists("/proc/net/dev"):
        return None

    try:
        with open("/proc/net/dev", "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines[2:]:
            if ":" not in line:
                continue
            name_part, data_part = line.split(":", 1)
            ifname = name_part.strip()
            fields = data_part.split()

            if len(fields) < 16:
                continue

            match = (
                (target_iface and ifname == target_iface)
                or (not target_iface and ifname != "lo")
            )

            if match:
                return InterfaceStats(
                    iface=ifname,
                    rx_bytes=int(fields[0]),
                    tx_bytes=int(fields[8]),
                    rx_packets=int(fields[1]),
                    tx_packets=int(fields[9]),
                    rx_errors=int(fields[2]),
                    tx_errors=int(fields[10]),
                    rx_dropped=int(fields[3]),
                    tx_dropped=int(fields[11]),
                    timestamp=time.monotonic(),
                    source="proc",
                    available=True,
                )
    except Exception:
        pass

    return None


def _read_psutil_interface_stats(target_iface: Optional[str]) -> Optional[InterfaceStats]:
    """
    Read interface stats via psutil (covers macOS, BSD, Windows).
    psutil wraps OS-specific APIs (getifaddrs, sysctl, etc.).
    """
    try:
        import psutil

        counters = psutil.net_io_counters(pernic=True)

        if target_iface and target_iface in counters:
            c = counters[target_iface]
            return InterfaceStats(
                iface=target_iface,
                rx_bytes=c.bytes_recv,
                tx_bytes=c.bytes_sent,
                rx_packets=c.packets_recv,
                tx_packets=c.packets_sent,
                rx_errors=c.errin,
                tx_errors=c.errout,
                rx_dropped=c.dropin,
                tx_dropped=c.dropout,
                timestamp=time.monotonic(),
                source="psutil",
                available=True,
            )

        # Auto-select first non-loopback interface
        for name, c in counters.items():
            if not name.startswith("lo"):
                return InterfaceStats(
                    iface=name,
                    rx_bytes=c.bytes_recv,
                    tx_bytes=c.bytes_sent,
                    rx_packets=c.packets_recv,
                    tx_packets=c.packets_sent,
                    rx_errors=c.errin,
                    tx_errors=c.errout,
                    rx_dropped=c.dropin,
                    tx_dropout=c.dropout,
                    timestamp=time.monotonic(),
                    source="psutil",
                    available=True,
                )
    except Exception:
        pass

    return None


def get_interface_stats(iface_name: Optional[str] = None) -> InterfaceStats:
    """
    Query current interface statistics from the OS.

    Returns real data from /proc/net/dev (Linux) or psutil (macOS/cross-platform).
    If no real data is available, returns an InterfaceStats with available=False
    and all counters at 0.  No synthetic/fabricated values.
    """
    # 1. Linux /proc/net/dev
    linux_stats = _read_linux_interface_stats(iface_name)
    if linux_stats is not None:
        return linux_stats

    # 2. psutil (macOS / cross-platform)
    psutil_stats = _read_psutil_interface_stats(iface_name)
    if psutil_stats is not None:
        return psutil_stats

    # 3. Data unavailable — return zero-valued struct with flag
    return InterfaceStats(
        iface=iface_name if iface_name else "unknown",
        rx_bytes=0,
        tx_bytes=0,
        rx_packets=0,
        tx_packets=0,
        rx_errors=0,
        tx_errors=0,
        rx_dropped=0,
        tx_dropped=0,
        timestamp=time.monotonic(),
        source="unavailable",
        available=False,
    )


# ──────────────────────────────────────────────────────────────────────────────
# ICMP Echo RTT Probe (real ping implementation)
# ──────────────────────────────────────────────────────────────────────────────

def _compute_icmp_checksum(data: bytes) -> int:
    """
    RFC 1071 one's complement checksum for ICMP packets.
    Pads to even length if needed.
    """
    if len(data) % 2 != 0:
        data += b'\x00'
    s = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        s += word
    # Fold 32-bit sum into 16 bits
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return ~s & 0xFFFF


def probe_icmp_rtt(
    target_ip: str,
    timeout_sec: float = 2.0,
    seq: int = 1,
    identifier: Optional[int] = None,
) -> RTTProbeResult:
    """
    Send a real ICMP Echo Request and measure RTT to target_ip.
    Requires root/CAP_NET_RAW on Linux, admin on macOS.

    This is the same mechanism as the ping(8) command.

    Returns:
        RTTProbeResult with rtt_ms populated on success.
    """
    if identifier is None:
        identifier = os.getpid() & 0xFFFF

    try:
        # Create raw ICMP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        sock.settimeout(timeout_sec)

        # Build ICMP Echo Request:
        # [type=8][code=0][checksum=?][identifier][sequence][payload=timestamp]
        payload = struct.pack("!d", time.monotonic())   # 8 bytes: send timestamp
        header_no_checksum = struct.pack("!BBHHH", 8, 0, 0, identifier, seq)
        packet = header_no_checksum + payload

        # Compute checksum and rebuild with it
        checksum = _compute_icmp_checksum(packet)
        header = struct.pack("!BBHHH", 8, 0, checksum, identifier, seq)
        packet = header + payload

        # Record send time (monotonic, high-resolution)
        send_time = time.monotonic()
        sock.sendto(packet, (target_ip, 0))

        # Wait for Echo Reply
        while True:
            try:
                raw_data, addr = sock.recvfrom(1024)
            except socket.timeout:
                return RTTProbeResult(
                    target_ip=target_ip,
                    rtt_ms=None,
                    ttl=None,
                    success=False,
                    error=f"Timeout after {timeout_sec}s",
                )

            recv_time = time.monotonic()

            # raw_data includes the IP header (20 bytes) + ICMP header + payload
            ip_header_len = (raw_data[0] & 0xF) * 4
            if len(raw_data) < ip_header_len + 8:
                continue

            icmp_type = raw_data[ip_header_len]
            icmp_code = raw_data[ip_header_len + 1]
            recv_id   = struct.unpack("!H", raw_data[ip_header_len + 4: ip_header_len + 6])[0]
            recv_seq  = struct.unpack("!H", raw_data[ip_header_len + 6: ip_header_len + 8])[0]
            ttl       = raw_data[8]   # TTL field in IP header

            # ICMP type 0 = Echo Reply, validate identifier and sequence
            if icmp_type == 0 and recv_id == identifier and recv_seq == seq:
                rtt_ms = (recv_time - send_time) * 1000.0
                return RTTProbeResult(
                    target_ip=target_ip,
                    rtt_ms=round(rtt_ms, 3),
                    ttl=ttl,
                    success=True,
                )
            # Continue waiting if reply is for a different identifier/sequence

    except PermissionError:
        return RTTProbeResult(
            target_ip=target_ip,
            rtt_ms=None,
            ttl=None,
            success=False,
            error="Permission denied — requires root/CAP_NET_RAW",
        )
    except OSError as exc:
        return RTTProbeResult(
            target_ip=target_ip,
            rtt_ms=None,
            ttl=None,
            success=False,
            error=str(exc),
        )
    finally:
        try:
            sock.close()
        except Exception:
            pass


def probe_rtt_multi(
    target_ip: str,
    count: int = 4,
    timeout_sec: float = 1.0,
) -> Dict:
    """
    Send `count` ICMP Echo Requests and return RTT statistics.
    Equivalent to `ping -c <count> <target>`.

    Returns:
        {
          "min_ms": float, "max_ms": float, "mean_ms": float,
          "jitter_ms": float, "sent": int, "received": int,
          "loss_pct": float, "samples": [float, ...]
        }
    """
    samples: List[float] = []
    identifier = os.getpid() & 0xFFFF

    for seq in range(1, count + 1):
        result = probe_icmp_rtt(target_ip, timeout_sec=timeout_sec, seq=seq, identifier=identifier)
        if result.success and result.rtt_ms is not None:
            samples.append(result.rtt_ms)
        time.sleep(0.1)   # standard inter-probe gap

    received = len(samples)
    sent = count
    loss_pct = round(((sent - received) / sent) * 100.0, 2) if sent > 0 else 0.0

    if not samples:
        return {
            "min_ms": None, "max_ms": None, "mean_ms": None,
            "jitter_ms": None, "sent": sent, "received": 0,
            "loss_pct": 100.0, "samples": [],
        }

    mean_ms = sum(samples) / len(samples)
    jitter_ms = sum(abs(s - mean_ms) for s in samples) / len(samples)

    return {
        "min_ms":    round(min(samples), 3),
        "max_ms":    round(max(samples), 3),
        "mean_ms":   round(mean_ms, 3),
        "jitter_ms": round(jitter_ms, 3),
        "sent":      sent,
        "received":  received,
        "loss_pct":  loss_pct,
        "samples":   [round(s, 3) for s in samples],
    }
