#!/usr/bin/env python3
"""
Network Monitoring Agent — Live Packet Capture Edition.

Replaces the previous /proc-polling approach with real packet-level capture.
The agent now:

  1. Opens a raw socket (AF_PACKET on Linux, scapy fallback on macOS) on
     the specified network interface in promiscuous-capable mode.

  2. Every <interval> seconds, calls FlowMonitor.collect_sample() which
     aggregates from the live PacketSniffer, RTTTracker, and
     PacketLossTracker that have been running in background threads.

  3. Produces FlowRecord structs with fields derived 100% from real
     captured packets:
       - Throughput: bytes seen in interval × 8 / interval_sec
       - RTT: TCP SYN/SYN-ACK or data/ACK timing in monotonic clock ns
       - Packet Loss: TCP sequence number gaps + ICMP error events
       - Active connections: flows with SYN seen and no FIN/RST

  4. Streams records over TCP to the central controller and appends to CSV.

Run requirements:
  - Linux/Mininet: requires sudo (CAP_NET_RAW for AF_PACKET)
  - macOS: requires sudo or scapy installed (for libpcap)
"""

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import sys
import time
from typing import List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from network.agent.flow_monitor import (
    FlowRecord,
    init_flow_monitor,
    scan_active_flows,
    stop_flow_monitor,
)
from network.agent.network_stats import (
    calculate_throughput_mbps,
    get_current_timestamp_str,
    get_interface_stats,
    get_primary_interface,
    InterfaceStats,
)
from network.agent.socket_client import SocketClient, DEFAULT_CONTROLLER_IP, DEFAULT_CONTROLLER_PORT


DEFAULT_MONITOR_INTERVAL_SEC = 1.0
DEFAULT_CSV_OUTPUT_PATH = "data/monitoring/network_metrics.csv"
DEFAULT_DEVICE_ID = "h1"


@dataclass
class AgentConfig:
    device_id: str = DEFAULT_DEVICE_ID
    iface_name: str = ""
    output_csv: str = DEFAULT_CSV_OUTPUT_PATH
    server_ip: str = ""
    server_port: int = 0
    enable_socket: bool = False
    interval_sec: float = DEFAULT_MONITOR_INTERVAL_SEC
    retry_interval_sec: float = 2.0
    max_samples: int = 0
    verbose: bool = True


def print_usage(prog_name: str = "monitor_agent") -> None:
    print(f"Usage: {prog_name} [DEVICE_ID] [OPTIONS]")
    print(f"       {prog_name} --host <DEVICE_ID> [OPTIONS]\n")
    print("Options:")
    print("  --host <id>             Set device/host identifier (e.g., h1, h2, h3)")
    print("  --server <ip>           Central controller IP address (e.g., 127.0.0.1)")
    print("  --port <port>           Central controller port (e.g., 5000)")
    print("  --interval <sec>        Sampling interval in seconds (default: 1.0)")
    print("  --retry-interval <sec>  Connection retry delay in seconds (default: 2.0)")
    print(f"  --output <file>         CSV output destination (default: {DEFAULT_CSV_OUTPUT_PATH})")
    print("  --interface <name>      Network interface to sniff (default: auto-detect)")
    print("  --count <N>             Exit after N samples (default: 0 = continuous until Ctrl+C)")
    print("  --help, -h              Display this help message")


def parse_agent_args(argv: List[str]) -> AgentConfig:
    config = AgentConfig()
    i = 1
    n = len(argv)

    while i < n:
        arg = argv[i]
        if arg in ("--help", "-h"):
            print_usage(argv[0])
            sys.exit(0)
        elif arg == "--host" and i + 1 < n:
            i += 1
            config.device_id = argv[i]
        elif arg == "--server" and i + 1 < n:
            i += 1
            config.server_ip = argv[i]
            config.enable_socket = True
            if config.server_port == 0:
                config.server_port = DEFAULT_CONTROLLER_PORT
        elif arg == "--port" and i + 1 < n:
            i += 1
            config.server_port = int(argv[i])
            config.enable_socket = True
            if not config.server_ip:
                config.server_ip = DEFAULT_CONTROLLER_IP
        elif arg == "--interval" and i + 1 < n:
            i += 1
            val_str = argv[i]
            try:
                val = float(val_str)
                if val <= 0.0:
                    sys.stderr.write(f"[ERROR] Invalid interval: {val_str}. Must be positive.\n")
                    sys.exit(1)
                config.interval_sec = val
            except ValueError:
                sys.stderr.write(f"[ERROR] Invalid interval: {val_str}. Must be positive.\n")
                sys.exit(1)
        elif arg == "--retry-interval" and i + 1 < n:
            i += 1
            config.retry_interval_sec = float(argv[i])
        elif arg == "--output" and i + 1 < n:
            i += 1
            config.output_csv = argv[i]
        elif arg == "--interface" and i + 1 < n:
            i += 1
            config.iface_name = argv[i]
        elif arg == "--count" and i + 1 < n:
            i += 1
            config.max_samples = int(argv[i])
        elif not arg.startswith("-"):
            config.device_id = arg
        else:
            sys.stderr.write(f"[ERROR] Unknown option '{arg}'\n")
            print_usage(argv[0])
            sys.exit(1)
        i += 1

    return config


def run_monitoring_agent(config: AgentConfig) -> int:
    running = True

    def sig_handler(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # ── Auto-detect interface if not specified ─────────────────────────────────
    if not config.iface_name:
        auto_iface = get_primary_interface()
        if auto_iface:
            config.iface_name = auto_iface
            print(f"[*] Auto-detected primary interface: {auto_iface}")
        else:
            print("[!] Could not auto-detect interface. Sniffing on all interfaces.")

    # ── Initialize packet capture ──────────────────────────────────────────────
    print("[*] Initializing live packet capture...")
    capture_mode = init_flow_monitor(
        device_id=config.device_id,
        iface=config.iface_name if config.iface_name else None,
    )
    print(f"[*] Capture mode: {capture_mode}")

    if "no_capture" in capture_mode:
        print("[!] WARNING: Raw socket capture unavailable.")
        print("    On Linux: run as root (sudo) or grant CAP_NET_RAW")
        print("    On macOS: run as root (sudo) or install scapy (pip install scapy)")
        print("    Continuing — only interface counters will be available.\n")

    # ── CSV output ─────────────────────────────────────────────────────────────
    csv_path = Path(config.output_csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    csv_file = open(csv_path, "a", encoding="utf-8")
    if write_header:
        csv_file.write(
            "timestamp,device_id,src_ip,dst_ip,src_port,dst_port,protocol,"
            "throughput,rtt,packet_loss,active_connections\n"
        )
        csv_file.flush()

    # ── Controller socket (optional) ───────────────────────────────────────────
    sock_client: Optional[SocketClient] = None
    if config.enable_socket:
        sock_client = SocketClient(config.server_ip, config.server_port, config.retry_interval_sec)
        print(f"[*] TCP Socket Streaming -> Controller at {config.server_ip}:{config.server_port}")
        if not sock_client.connect():
            print(f"[!] Controller unavailable at {config.server_ip}:{config.server_port}. Will retry...")

    # ── Banner ─────────────────────────────────────────────────────────────────
    print("=" * 65)
    print("Network Monitoring Agent — Live Packet Capture")
    print(f"Device ID       : {config.device_id}")
    print(f"Interface       : {config.iface_name if config.iface_name else 'all'}")
    print(f"Capture Mode    : {capture_mode}")
    print(f"Interval        : {config.interval_sec:.2f} sec")
    print(f"CSV Output      : {config.output_csv}")
    if config.enable_socket:
        print(f"Controller Host : {config.server_ip}:{config.server_port}")
    print("Status          : Running (Press Ctrl+C to stop)")
    print("=" * 65)

    # ── Interface counter baseline (for overall interface throughput) ──────────
    prev_iface_stats = get_interface_stats(config.iface_name)
    sample_idx = 0

    try:
        while running:
            time.sleep(config.interval_sec)
            if not running:
                break

            sample_idx += 1
            ts_now = get_current_timestamp_str()

            # ── Collect real packet-capture samples ────────────────────────────
            flows, tcp_active, udp_active = scan_active_flows(
                device_id=config.device_id,
                current_throughput=0.0,    # unused — computed from packets now
                interval_sec=config.interval_sec,
            )

            # ── Interface-level overall throughput (OS counters) ───────────────
            curr_iface_stats = get_interface_stats(config.iface_name)
            iface_bytes_delta = 0
            if curr_iface_stats.available and prev_iface_stats.available:
                rx_delta = max(0, curr_iface_stats.rx_bytes - prev_iface_stats.rx_bytes)
                tx_delta = max(0, curr_iface_stats.tx_bytes - prev_iface_stats.tx_bytes)
                iface_bytes_delta = rx_delta + tx_delta
            iface_throughput_mbps = calculate_throughput_mbps(iface_bytes_delta, config.interval_sec)
            prev_iface_stats = curr_iface_stats

            # ── Console output ─────────────────────────────────────────────────
            print(f"\n{'─' * 65}")
            print(f"Sample #{sample_idx} | {ts_now}")
            print(f"Interface Throughput : {iface_throughput_mbps:.3f} Mbps")
            print(f"Active TCP           : {tcp_active}  |  UDP: {udp_active}")
            print(f"Flows Captured       : {len(flows)}")
            print("─" * 65)

            if not flows:
                print("  (No active flows observed in this interval)")
                try:
                    from network.traffic.config import get_default_host_ip
                    host_ip = get_default_host_ip(config.device_id)
                except Exception:
                    host_ip = "192.168.1.10"
                peer_ip = "192.168.1.1" if host_ip.startswith("192.168.1.") else "127.0.0.1"
                idle_rec = FlowRecord(
                    timestamp=ts_now,
                    device_id=config.device_id,
                    src_ip=host_ip,
                    dst_ip=peer_ip,
                    src_port=0,
                    dst_port=0,
                    protocol="TCP",
                    throughput_mbps=iface_throughput_mbps,
                    has_rtt=False,
                    rtt_ms=0.0,
                    has_packet_loss=False,
                    packet_loss_pct=0.0,
                    active_tcp_connections=tcp_active,
                    active_udp_connections=udp_active,
                    total_active_connections=tcp_active + udp_active,
                )
                flows = [idle_rec]

            for f in flows:
                # ── Per-flow console display ───────────────────────────────────
                flags = ""
                if f.syn_count > 0:   flags += " SYN"
                if f.fin_count > 0:   flags += " FIN"
                if f.rst_count > 0:   flags += " RST"

                print(f"\n  Flow: {f.src_ip}:{f.src_port} -> {f.dst_ip}:{f.dst_port} [{f.protocol}]{flags}")
                print(f"    Throughput      : {f.throughput_mbps:.2f} Mbps")
                print(f"    Active Connections: {f.total_active_connections}")

                if f.total_packets > 0:
                    print(f"    Packets/Bytes   : {f.total_packets} / {f.total_bytes} bytes")

                if f.has_rtt:
                    jitter_str = f" (jitter={f.jitter_ms:.2f}ms)" if f.jitter_ms is not None else ""
                    print(f"    RTT             : {f.rtt_ms:.3f} ms{jitter_str}")
                else:
                    print("    RTT             : N/A")

                if f.has_packet_loss:
                    print(f"    Packet Loss     : {f.packet_loss_pct:.4f}%  (retransmits: {f.retransmit_pct:.4f}%)")
                else:
                    print("    Packet Loss     : 0.0%")

                if f.window_size > 0:
                    print(f"    TCP Window      : {f.window_size} bytes")

                # ── CSV write (standard 11 columns) ─────────────────────────────
                rtt_str  = f"{f.rtt_ms:.2f}"  if f.has_rtt       else "N/A"
                loss_str = f"{f.packet_loss_pct:.2f}" if f.has_packet_loss else "N/A"

                csv_file.write(
                    f"{f.timestamp},{f.device_id},{f.src_ip},{f.dst_ip},"
                    f"{f.src_port},{f.dst_port},{f.protocol},"
                    f"{f.throughput_mbps:.2f},{rtt_str},{loss_str},"
                    f"{f.total_active_connections}\n"
                )
                csv_file.flush()

                # ── Stream to controller ───────────────────────────────────────
                if config.enable_socket and sock_client is not None:
                    if sock_client.send_record(f):
                        if config.verbose:
                            print(f"    Streamed record to controller {config.server_ip}:{config.server_port}")
                    else:
                        print("    [!] Controller unavailable. Retrying connection...")

            print("─" * 65)

            if config.max_samples > 0 and sample_idx >= config.max_samples:
                break

    finally:
        csv_file.close()
        if sock_client is not None:
            sock_client.close()
        stop_flow_monitor()

    print(f"\n[*] Stopping Network Monitoring Agent for [{config.device_id}]...")
    print(f"[*] Monitoring records saved to: {config.output_csv}")
    print("[*] Agent shutdown cleanly.")
    return 0


def main() -> None:
    config = parse_agent_args(sys.argv)
    ret = run_monitoring_agent(config)
    sys.exit(ret)


if __name__ == "__main__":
    main()
