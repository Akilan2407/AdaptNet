"""
Real-time packet sniffer using raw sockets.

On Linux:  Uses AF_PACKET / SOCK_RAW (ETH_P_ALL) to capture raw Ethernet frames.
           No external library required — works directly with OS raw socket API.

On macOS:  Uses AF_INET / SOCK_RAW / IPPROTO_TCP + IPPROTO_UDP via separate sockets,
           falling back to scapy if available.
On Windows: Uses scapy/WinPcap or Npcap for cross-platform packet capture.

Parses headers at each OSI layer:
  Layer 2 — Ethernet (dst/src MAC, EtherType)
  Layer 3 — IPv4 (src/dst IP, TTL, protocol, total length, checksum)
  Layer 4 — TCP (src/dst port, seq#, ack#, flags: SYN/ACK/FIN/RST/PSH/URG)
            UDP (src/dst port, length)
           ICMP (type, code, checksum)

All captured data is real — zero synthetic values.
"""

import struct
import socket
import threading
import time
import sys
import platform
import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable

# ──────────────────────────────────────────────────────────────────────────────
# Constants — Ethernet / IP / Transport
# ──────────────────────────────────────────────────────────────────────────────

ETHERTYPE_IPV4 = 0x0800
ETHERTYPE_ARP  = 0x0806
ETHERTYPE_IPV6 = 0x86DD

IPPROTO_ICMP = 1
IPPROTO_TCP  = 6
IPPROTO_UDP  = 17

# TCP flag bitmasks
TCP_FLAG_FIN = 0x01
TCP_FLAG_SYN = 0x02
TCP_FLAG_RST = 0x04
TCP_FLAG_PSH = 0x08
TCP_FLAG_ACK = 0x10
TCP_FLAG_URG = 0x20
TCP_FLAG_ECE = 0x40
TCP_FLAG_CWR = 0x80

ETHERNET_HEADER_LEN = 14   # bytes
IPV4_MIN_HEADER_LEN = 20   # bytes (no options)
TCP_MIN_HEADER_LEN  = 20   # bytes (no options)
UDP_HEADER_LEN      = 8    # bytes
ICMP_HEADER_LEN     = 8    # bytes


# ──────────────────────────────────────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class EthernetHeader:
    dst_mac: str
    src_mac: str
    ethertype: int


@dataclass
class IPv4Header:
    version: int
    ihl: int            # header length in 32-bit words
    dscp: int
    ecn: int
    total_length: int
    identification: int
    flags: int
    fragment_offset: int
    ttl: int
    protocol: int
    checksum: int
    src_ip: str
    dst_ip: str
    header_len_bytes: int


@dataclass
class TCPHeader:
    src_port: int
    dst_port: int
    seq_num: int
    ack_num: int
    data_offset: int    # header length in 32-bit words
    flags: int
    window_size: int
    checksum: int
    urgent_ptr: int
    # Decoded flag properties
    flag_syn: bool = False
    flag_ack: bool = False
    flag_fin: bool = False
    flag_rst: bool = False
    flag_psh: bool = False
    flag_urg: bool = False
    flag_ece: bool = False
    flag_cwr: bool = False


@dataclass
class UDPHeader:
    src_port: int
    dst_port: int
    length: int
    checksum: int


@dataclass
class ICMPHeader:
    icmp_type: int
    code: int
    checksum: int
    rest_of_header: int   # 4 bytes: identifier+sequence or pointer etc.


@dataclass
class CapturedPacket:
    """Complete parsed packet with all decoded headers and metadata."""
    timestamp: float           # monotonic capture time (seconds)
    capture_timestamp: str     # human-readable wall-clock
    iface: str                 # source network interface

    # Layer 2
    eth: Optional[EthernetHeader] = None

    # Layer 3
    ip: Optional[IPv4Header] = None

    # Layer 4
    tcp: Optional[TCPHeader] = None
    udp: Optional[UDPHeader] = None
    icmp: Optional[ICMPHeader] = None

    # Payload
    payload_len: int = 0

    # Derived convenience fields
    protocol_name: str = "UNKNOWN"   # "TCP", "UDP", "ICMP", "ARP", ...
    src_ip: str = ""
    dst_ip: str = ""
    src_port: int = 0
    dst_port: int = 0
    packet_len: int = 0


# ──────────────────────────────────────────────────────────────────────────────
# Header Parsing Functions
# ──────────────────────────────────────────────────────────────────────────────

def _mac_bytes_to_str(b: bytes) -> str:
    """Convert 6 raw bytes to colon-separated MAC address string."""
    return ":".join(f"{x:02x}" for x in b)


def parse_ethernet_header(raw: bytes) -> Optional[EthernetHeader]:
    """
    Parse a 14-byte Ethernet II frame header.
    Layout: [dst_mac 6B][src_mac 6B][ethertype 2B]
    """
    if len(raw) < ETHERNET_HEADER_LEN:
        return None
    dst_mac = _mac_bytes_to_str(raw[0:6])
    src_mac = _mac_bytes_to_str(raw[6:12])
    ethertype = struct.unpack("!H", raw[12:14])[0]
    return EthernetHeader(dst_mac=dst_mac, src_mac=src_mac, ethertype=ethertype)


def parse_ipv4_header(raw: bytes, offset: int = 0) -> Optional[IPv4Header]:
    """
    Parse IPv4 header from raw bytes starting at `offset`.
    RFC 791 Layout:
      [version+IHL 1B][DSCP+ECN 1B][total_length 2B]
      [identification 2B][flags+fragment_offset 2B]
      [TTL 1B][protocol 1B][checksum 2B]
      [src_ip 4B][dst_ip 4B]
      [options if IHL > 5]
    """
    if len(raw) < offset + IPV4_MIN_HEADER_LEN:
        return None

    byte0 = raw[offset]
    version = (byte0 >> 4) & 0xF
    ihl     = byte0 & 0xF           # in 32-bit words

    if version != 4 or ihl < 5:
        return None

    header_len_bytes = ihl * 4

    (dscp_ecn, total_length, identification,
     flags_frag, ttl, protocol, checksum) = struct.unpack(
        "!BHHHBBH", raw[offset + 1: offset + 12]
    )

    dscp = (dscp_ecn >> 2) & 0x3F
    ecn  = dscp_ecn & 0x03
    flags = (flags_frag >> 13) & 0x7
    fragment_offset = flags_frag & 0x1FFF

    src_ip = socket.inet_ntoa(raw[offset + 12: offset + 16])
    dst_ip = socket.inet_ntoa(raw[offset + 16: offset + 20])

    return IPv4Header(
        version=version,
        ihl=ihl,
        dscp=dscp,
        ecn=ecn,
        total_length=total_length,
        identification=identification,
        flags=flags,
        fragment_offset=fragment_offset,
        ttl=ttl,
        protocol=protocol,
        checksum=checksum,
        src_ip=src_ip,
        dst_ip=dst_ip,
        header_len_bytes=header_len_bytes,
    )


def parse_tcp_header(raw: bytes, offset: int = 0) -> Optional[TCPHeader]:
    """
    Parse TCP header from raw bytes at `offset`.
    RFC 793 Layout:
      [src_port 2B][dst_port 2B][seq_num 4B][ack_num 4B]
      [data_offset+reserved+flags 2B][window_size 2B]
      [checksum 2B][urgent_ptr 2B]
      [options if data_offset > 5]
    """
    if len(raw) < offset + TCP_MIN_HEADER_LEN:
        return None

    src_port, dst_port, seq_num, ack_num = struct.unpack(
        "!HHII", raw[offset: offset + 12]
    )

    doff_flags = struct.unpack("!H", raw[offset + 12: offset + 14])[0]
    data_offset = (doff_flags >> 12) & 0xF
    flags       = doff_flags & 0x1FF    # 9-bit flags field (RFC 3168 includes CWR/ECE)

    window_size, checksum, urgent_ptr = struct.unpack(
        "!HHH", raw[offset + 14: offset + 20]
    )

    return TCPHeader(
        src_port=src_port,
        dst_port=dst_port,
        seq_num=seq_num,
        ack_num=ack_num,
        data_offset=data_offset,
        flags=flags,
        window_size=window_size,
        checksum=checksum,
        urgent_ptr=urgent_ptr,
        flag_fin=(flags & TCP_FLAG_FIN) != 0,
        flag_syn=(flags & TCP_FLAG_SYN) != 0,
        flag_rst=(flags & TCP_FLAG_RST) != 0,
        flag_psh=(flags & TCP_FLAG_PSH) != 0,
        flag_ack=(flags & TCP_FLAG_ACK) != 0,
        flag_urg=(flags & TCP_FLAG_URG) != 0,
        flag_ece=(flags & TCP_FLAG_ECE) != 0,
        flag_cwr=(flags & TCP_FLAG_CWR) != 0,
    )


def parse_udp_header(raw: bytes, offset: int = 0) -> Optional[UDPHeader]:
    """
    Parse UDP header from raw bytes at `offset`.
    RFC 768 Layout: [src_port 2B][dst_port 2B][length 2B][checksum 2B]
    """
    if len(raw) < offset + UDP_HEADER_LEN:
        return None
    src_port, dst_port, length, checksum = struct.unpack(
        "!HHHH", raw[offset: offset + 8]
    )
    return UDPHeader(src_port=src_port, dst_port=dst_port, length=length, checksum=checksum)


def parse_icmp_header(raw: bytes, offset: int = 0) -> Optional[ICMPHeader]:
    """
    Parse ICMP header from raw bytes at `offset`.
    RFC 792 Layout: [type 1B][code 1B][checksum 2B][rest 4B]
    """
    if len(raw) < offset + ICMP_HEADER_LEN:
        return None
    icmp_type, code, checksum, rest = struct.unpack(
        "!BBHI", raw[offset: offset + 8]
    )
    return ICMPHeader(icmp_type=icmp_type, code=code, checksum=checksum, rest_of_header=rest)


def parse_full_packet(raw: bytes, iface: str = "unknown", has_ethernet: bool = True) -> Optional[CapturedPacket]:
    """
    Parse a complete raw network packet from wire bytes.

    Args:
        raw:          Raw bytes from socket.recv()
        iface:        Interface name this packet was captured on
        has_ethernet: True for AF_PACKET (includes Ethernet header),
                      False for AF_INET raw (IP header only, no Ethernet)
    """
    now_mono = time.monotonic()
    now_wall = time.strftime("%Y-%m-%d %H:%M:%S")
    pkt = CapturedPacket(
        timestamp=now_mono,
        capture_timestamp=now_wall,
        iface=iface,
        packet_len=len(raw),
    )

    offset = 0

    # ── Layer 2: Ethernet ──────────────────────────────────────────────────────
    if has_ethernet:
        eth = parse_ethernet_header(raw)
        if eth is None:
            return None
        pkt.eth = eth
        offset = ETHERNET_HEADER_LEN

        # Skip non-IPv4 frames (ARP, IPv6, etc.)
        if eth.ethertype == ETHERTYPE_ARP:
            pkt.protocol_name = "ARP"
            return pkt
        if eth.ethertype != ETHERTYPE_IPV4:
            return None   # unsupported; skip

    # ── Layer 3: IPv4 ─────────────────────────────────────────────────────────
    ip = parse_ipv4_header(raw, offset)
    if ip is None:
        return None
    pkt.ip = ip
    pkt.src_ip = ip.src_ip
    pkt.dst_ip = ip.dst_ip
    offset += ip.header_len_bytes

    # ── Layer 4: TCP / UDP / ICMP ─────────────────────────────────────────────
    if ip.protocol == IPPROTO_TCP:
        tcp = parse_tcp_header(raw, offset)
        if tcp is None:
            return None
        pkt.tcp = tcp
        pkt.src_port = tcp.src_port
        pkt.dst_port = tcp.dst_port
        pkt.protocol_name = "TCP"
        tcp_header_bytes = tcp.data_offset * 4
        payload_offset = offset + tcp_header_bytes
        pkt.payload_len = max(0, len(raw) - payload_offset)

    elif ip.protocol == IPPROTO_UDP:
        udp = parse_udp_header(raw, offset)
        if udp is None:
            return None
        pkt.udp = udp
        pkt.src_port = udp.src_port
        pkt.dst_port = udp.dst_port
        pkt.protocol_name = "UDP"
        pkt.payload_len = max(0, udp.length - UDP_HEADER_LEN)

    elif ip.protocol == IPPROTO_ICMP:
        icmp = parse_icmp_header(raw, offset)
        if icmp is None:
            return None
        pkt.icmp = icmp
        pkt.protocol_name = "ICMP"

    else:
        pkt.protocol_name = f"PROTO_{ip.protocol}"

    return pkt


# ──────────────────────────────────────────────────────────────────────────────
# Raw Socket Creation
# ──────────────────────────────────────────────────────────────────────────────

def _create_linux_raw_socket() -> Tuple[Optional[socket.socket], bool]:
    """
    Create AF_PACKET SOCK_RAW socket on Linux (captures all Ethernet frames).
    Requires root / CAP_NET_RAW.
    Returns (socket, has_ethernet_header=True).
    """
    try:
        # ETH_P_ALL = 0x0003 — receive all protocols
        ETH_P_ALL = 0x0003
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
        return s, True
    except PermissionError:
        return None, True
    except OSError:
        return None, True


def _create_macos_raw_socket() -> Tuple[Optional[socket.socket], bool]:
    """
    Create AF_INET SOCK_RAW socket on macOS/BSD capturing IP-level packets.
    Returns (socket, has_ethernet_header=False).
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_TCP)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
        return s, False
    except PermissionError:
        return None, False
    except OSError:
        return None, False


def create_capture_socket() -> Tuple[Optional[socket.socket], bool, str]:
    """
    Create best-available raw capture socket for the current platform.

    Returns:
        (socket_or_None, has_ethernet_header, description)
    """
    os_name = platform.system()

    if os_name == "Linux":
        sock, has_eth = _create_linux_raw_socket()
        if sock is not None:
            return sock, has_eth, "AF_PACKET/ETH_P_ALL (Linux raw Ethernet)"
        return None, False, "AF_PACKET failed — run as root"

    elif os_name == "Darwin":
        sock, has_eth = _create_macos_raw_socket()
        if sock is not None:
            return sock, has_eth, "AF_INET/SOCK_RAW (macOS IP-level)"
        return None, False, "AF_INET raw socket failed — run as root"

    else:
        return None, False, f"Use scapy on {os_name}; install Npcap for live capture"


# ──────────────────────────────────────────────────────────────────────────────
# Scapy-based Sniffer (fallback when raw sockets unavailable or for macOS)
# ──────────────────────────────────────────────────────────────────────────────

def _scapy_available() -> bool:
    try:
        import importlib
        spec = importlib.util.find_spec("scapy")
        return spec is not None
    except Exception:
        return False


class ScapySniffer:
    """Wraps scapy's sniff() to provide CapturedPacket objects."""

    def __init__(
        self,
        iface: Optional[str],
        bpf_filter: str = "",
        callback: Optional[Callable] = None,
        error_callback: Optional[Callable[[str], None]] = None,
    ):
        self.iface = iface
        self.bpf_filter = bpf_filter
        self.callback = callback
        self.error_callback = error_callback
        self.error: Optional[str] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _on_scapy_packet(self, scapy_pkt):
        """Convert a scapy packet into our CapturedPacket representation."""
        try:
            from scapy.layers.inet import IP, TCP, UDP, ICMP
            from scapy.layers.l2 import Ether

            pkt = CapturedPacket(
                timestamp=time.monotonic(),
                capture_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                iface=self.iface or "unknown",
                packet_len=len(scapy_pkt),
            )

            # Ethernet
            if scapy_pkt.haslayer(Ether):
                e = scapy_pkt[Ether]
                pkt.eth = EthernetHeader(
                    dst_mac=e.dst, src_mac=e.src,
                    ethertype=e.type
                )

            # IPv4
            if scapy_pkt.haslayer(IP):
                ip_layer = scapy_pkt[IP]
                pkt.ip = IPv4Header(
                    version=ip_layer.version,
                    ihl=ip_layer.ihl,
                    dscp=ip_layer.tos >> 2,
                    ecn=ip_layer.tos & 0x3,
                    total_length=ip_layer.len,
                    identification=ip_layer.id,
                    flags=int(ip_layer.flags),
                    fragment_offset=ip_layer.frag,
                    ttl=ip_layer.ttl,
                    protocol=ip_layer.proto,
                    checksum=ip_layer.chksum,
                    src_ip=ip_layer.src,
                    dst_ip=ip_layer.dst,
                    header_len_bytes=ip_layer.ihl * 4,
                )
                pkt.src_ip = ip_layer.src
                pkt.dst_ip = ip_layer.dst

            # TCP
            if scapy_pkt.haslayer(TCP):
                t = scapy_pkt[TCP]
                flags_int = int(t.flags)
                pkt.tcp = TCPHeader(
                    src_port=t.sport, dst_port=t.dport,
                    seq_num=t.seq, ack_num=t.ack,
                    data_offset=t.dataofs, flags=flags_int,
                    window_size=t.window, checksum=t.chksum,
                    urgent_ptr=t.urgptr,
                    flag_syn=bool(flags_int & TCP_FLAG_SYN),
                    flag_ack=bool(flags_int & TCP_FLAG_ACK),
                    flag_fin=bool(flags_int & TCP_FLAG_FIN),
                    flag_rst=bool(flags_int & TCP_FLAG_RST),
                    flag_psh=bool(flags_int & TCP_FLAG_PSH),
                    flag_urg=bool(flags_int & TCP_FLAG_URG),
                    flag_ece=bool(flags_int & TCP_FLAG_ECE),
                    flag_cwr=bool(flags_int & TCP_FLAG_CWR),
                )
                pkt.src_port = t.sport
                pkt.dst_port = t.dport
                pkt.protocol_name = "TCP"
                pkt.payload_len = len(t.payload)

            elif scapy_pkt.haslayer(UDP):
                u = scapy_pkt[UDP]
                pkt.udp = UDPHeader(
                    src_port=u.sport, dst_port=u.dport,
                    length=u.len, checksum=u.chksum
                )
                pkt.src_port = u.sport
                pkt.dst_port = u.dport
                pkt.protocol_name = "UDP"
                pkt.payload_len = len(u.payload)

            elif scapy_pkt.haslayer(ICMP):
                ic = scapy_pkt[ICMP]
                pkt.icmp = ICMPHeader(
                    icmp_type=ic.type, code=ic.code,
                    checksum=ic.chksum, rest_of_header=0
                )
                pkt.protocol_name = "ICMP"

            if self.callback:
                self.callback(pkt)

        except Exception:
            pass

    def start(self) -> None:
        from scapy.all import sniff as scapy_sniff

        def _sniff_loop():
            try:
                scapy_sniff(
                    iface=self.iface,
                    filter=self.bpf_filter,
                    prn=self._on_scapy_packet,
                    store=False,
                    stop_filter=lambda _: self._stop_event.is_set(),
                )
            except Exception as e:
                err_msg = str(e)
                if "winpcap is not installed" in err_msg.lower():
                    err_msg = "Npcap driver is not installed on Windows. Please install Npcap (https://npcap.com) with WinPcap-compatible mode or run terminal as Administrator."
                self.error = err_msg
                if self.error_callback:
                    self.error_callback(err_msg)

        self._thread = threading.Thread(target=_sniff_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)


# ──────────────────────────────────────────────────────────────────────────────
# Main Packet Sniffer Class
# ──────────────────────────────────────────────────────────────────────────────

class PacketSniffer:
    """
    Production packet sniffer that captures and parses live network traffic.

    Priority order:
      1. AF_PACKET raw socket (Linux, root)
      2. Scapy sniff() (cross-platform, root/Npcap)
      3. AF_INET raw TCP socket (macOS, root)

    Usage:
        sniffer = PacketSniffer(iface="eth0", callback=my_handler)
        sniffer.start()
        ...
        sniffer.stop()
    """

    def __init__(
        self,
        iface: Optional[str] = None,
        bpf_filter: str = "",
        callback: Optional[Callable[[CapturedPacket], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
        max_buffer: int = 10000,
    ):
        self.iface = iface
        self.bpf_filter = bpf_filter
        self.callback = callback
        self.error_callback = error_callback
        self.max_buffer = max_buffer

        self._packet_buffer: deque = deque(maxlen=max_buffer)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._capture_mode: str = "none"
        self._raw_sock: Optional[socket.socket] = None
        self._has_eth: bool = True
        self._scapy_sniffer: Optional[ScapySniffer] = None

        # Stats
        self.total_captured: int = 0
        self.total_tcp: int = 0
        self.total_udp: int = 0
        self.total_icmp: int = 0
        self.total_other: int = 0

    def _detect_mode(self) -> str:
        """Detect best available capture method."""
        if _scapy_available():
            if platform.system() == "Windows":
                try:
                    from scapy.all import conf
                    import ctypes
                    is_admin = bool(hasattr(ctypes, "windll") and ctypes.windll.shell32.IsUserAnAdmin())
                    if not conf.use_pcap and not is_admin:
                        return "no_capture (Npcap is not installed on Windows. Please install Npcap from https://npcap.com with WinPcap-compatible mode or run terminal as Administrator)"
                except Exception:
                    pass
            return "scapy"

        sock, has_eth, desc = create_capture_socket()
        if sock is not None:
            self._raw_sock = sock
            self._has_eth = has_eth
            if has_eth:
                return "raw_eth"
            else:
                return "raw_ip"

        return "none"

        sock, has_eth, desc = create_capture_socket()
        if sock is not None:
            self._raw_sock = sock
            self._has_eth = has_eth
            if has_eth:
                return "raw_eth"
            else:
                return "raw_ip"

        return "none"

    def _dispatch(self, pkt: CapturedPacket) -> None:
        """Store packet and invoke user callback."""
        with self._lock:
            self._packet_buffer.append(pkt)
            self.total_captured += 1
            if pkt.protocol_name == "TCP":
                self.total_tcp += 1
            elif pkt.protocol_name == "UDP":
                self.total_udp += 1
            elif pkt.protocol_name == "ICMP":
                self.total_icmp += 1
            else:
                self.total_other += 1

        if self.callback:
            try:
                self.callback(pkt)
            except Exception:
                pass

    def _raw_capture_loop(self) -> None:
        """Main receive loop for raw socket capture (Linux AF_PACKET or macOS raw)."""
        if self._raw_sock is None:
            return

        self._raw_sock.settimeout(0.5)
        iface_name = self.iface or "any"

        while not self._stop_event.is_set():
            try:
                raw, _ = self._raw_sock.recvfrom(65535)
                pkt = parse_full_packet(raw, iface=iface_name, has_ethernet=self._has_eth)
                if pkt is not None:
                    self._dispatch(pkt)
            except socket.timeout:
                continue
            except OSError:
                break

    def start(self) -> str:
        """Start capturing. Returns mode description string."""
        mode = self._detect_mode()
        self._capture_mode = mode

        if mode == "scapy":
            self._scapy_sniffer = ScapySniffer(
                iface=self.iface,
                bpf_filter=self.bpf_filter,
                callback=self._dispatch,
                error_callback=self.error_callback,
            )
            self._scapy_sniffer.start()
            return f"scapy (iface={self.iface or 'any'}, filter='{self.bpf_filter}')"

        elif mode in ("raw_eth", "raw_ip"):
            self._thread = threading.Thread(target=self._raw_capture_loop, daemon=True)
            self._thread.start()
            label = "AF_PACKET Ethernet" if mode == "raw_eth" else "AF_INET raw IP"
            return f"{label} (iface={self.iface or 'any'})"

        else:
            return mode if mode.startswith("no_capture") else "no_capture (insufficient privileges — run as root/sudo)"

    def stop(self) -> None:
        """Stop packet capture cleanly."""
        self._stop_event.set()

        if self._scapy_sniffer:
            self._scapy_sniffer.stop()

        if self._raw_sock:
            try:
                self._raw_sock.close()
            except Exception:
                pass

        if self._thread:
            self._thread.join(timeout=3.0)

    def get_recent_packets(self, max_count: int = 100) -> List[CapturedPacket]:
        """Return most recently captured packets (thread-safe)."""
        with self._lock:
            buf = list(self._packet_buffer)
        return buf[-max_count:]

    def get_stats(self) -> Dict:
        with self._lock:
            return {
                "total_captured": self.total_captured,
                "tcp": self.total_tcp,
                "udp": self.total_udp,
                "icmp": self.total_icmp,
                "other": self.total_other,
                "mode": self._capture_mode,
            }


# ──────────────────────────────────────────────────────────────────────────────
# Standalone test
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import signal as _signal

    print("=== Raw Packet Sniffer — Live Capture Test ===")
    print("(Ctrl+C to stop)\n")

    def on_packet(pkt: CapturedPacket):
        if pkt.protocol_name in ("TCP", "UDP"):
            flags_str = ""
            if pkt.tcp:
                t = pkt.tcp
                flags_str = " [" + "".join([
                    "S" if t.flag_syn else "",
                    "A" if t.flag_ack else "",
                    "F" if t.flag_fin else "",
                    "R" if t.flag_rst else "",
                    "P" if t.flag_psh else "",
                ]) + "]"
            print(
                f"[{pkt.capture_timestamp}] {pkt.protocol_name}{flags_str} "
                f"{pkt.src_ip}:{pkt.src_port} -> {pkt.dst_ip}:{pkt.dst_port} "
                f"len={pkt.packet_len}"
            )
        elif pkt.protocol_name == "ICMP" and pkt.icmp:
            print(
                f"[{pkt.capture_timestamp}] ICMP type={pkt.icmp.icmp_type} "
                f"code={pkt.icmp.code} {pkt.src_ip} -> {pkt.dst_ip}"
            )

    sniffer = PacketSniffer(iface=None, callback=on_packet)
    mode = sniffer.start()
    print(f"Capture mode: {mode}\n")

    def _stop(sig, frame):
        print("\n[*] Stopping sniffer...")
        sniffer.stop()
        stats = sniffer.get_stats()
        print(f"\nCapture Stats: {stats}")
        sys.exit(0)

    _signal.signal(_signal.SIGINT, _stop)

    while True:
        time.sleep(1)
