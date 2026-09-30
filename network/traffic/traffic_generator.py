#!/usr/bin/env python3
"""
Traffic Generation Engine.
Orchestrates realistic TCP and UDP traffic flows using iperf3 within Mininet LAN topologies.

Features:
- Configurable scenarios (tcp, udp, multi_tcp, multi_udp, mixed, congestion)
- Host-to-IP resolution
- Automatic iperf3 server provisioning prior to client startup
- Process lifecycle management and guaranteed cleanup
- Structured JSON and human-readable logging to data/traffic_logs/
- Simulation fallback for non-Linux / test environments
"""

import os
import sys

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import time
import json
import signal
import shutil
import argparse
import subprocess
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional

from network.traffic.config import (
    FlowConfig,
    DEFAULT_LOG_DIR,
    DEFAULT_DURATION,
    DEFAULT_UDP_BANDWIDTH,
    get_default_host_ip
)
from network.traffic.traffic_scenarios import get_scenario_flows, SCENARIO_BUILDERS

# Check for Mininet
try:
    from mininet.net import Mininet
    MININET_AVAILABLE = True
except ImportError:
    MININET_AVAILABLE = False


class TrafficGenerator:
    """
    Orchestrates TCP and UDP traffic generation using iperf3.
    """

    def __init__(
        self,
        mininet_net: Optional[Any] = None,
        log_dir: str = DEFAULT_LOG_DIR,
        dry_run: bool = False
    ):
        self.net = mininet_net
        self.log_dir = log_dir
        self.dry_run = dry_run or (not MININET_AVAILABLE and mininet_net is None)
        self.server_procs: List[subprocess.Popen] = []
        self.client_procs: List[subprocess.Popen] = []
        self.active_servers: Dict[str, List[int]] = {} # host -> [ports]
        self.results: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

        os.makedirs(self.log_dir, exist_ok=True)
        self._check_iperf3()

    def _check_iperf3(self):
        """Check if iperf3 is available in system PATH."""
        self.iperf3_path = shutil.which("iperf3")
        if not self.iperf3_path and not self.dry_run:
            print("[WARNING] iperf3 binary not found in PATH. Operating in simulation mode.")
            self.dry_run = True

    def resolve_host_ip(self, host_name: str) -> str:
        """Resolve Mininet host object or host name string to its IPv4 address."""
        if self.net:
            try:
                host_obj = self.net.get(host_name)
                return host_obj.IP()
            except Exception:
                pass
        return get_default_host_ip(host_name)

    def start_iperf_server(self, host_name: str, port: int, protocol: str = "tcp") -> bool:
        """Start an iperf3 server on the designated host."""
        host_ip = self.resolve_host_ip(host_name)
        proto_str = protocol.upper()

        print(f"  [+] Starting {proto_str} Server on {host_name} ({host_ip}:{port})")

        if self.dry_run:
            with self._lock:
                self.active_servers.setdefault(host_name, []).append(port)
            return True

        # Mininet host execution
        if self.net:
            host_obj = self.net.get(host_name)
            cmd = f"iperf3 -s -p {port} -D"
            host_obj.cmd(cmd)
            with self._lock:
                self.active_servers.setdefault(host_name, []).append(port)
            return True

        # Local host fallback execution
        cmd = [self.iperf3_path or "iperf3", "-s", "-p", str(port)]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with self._lock:
            self.server_procs.append(proc)
            self.active_servers.setdefault(host_name, []).append(port)
        return True

    def run_iperf_client(self, flow: FlowConfig) -> Dict[str, Any]:
        """Execute an iperf3 client generating traffic to the server."""
        flow.validate()
        dst_ip = self.resolve_host_ip(flow.dst_host)
        src_ip = self.resolve_host_ip(flow.src_host)
        proto_upper = flow.protocol.upper()

        print(f"\n  [>] Starting {proto_upper} Client: {flow.src_host} ({src_ip}) -> {flow.dst_host} ({dst_ip}:{flow.port})")
        print(f"      Protocol : {proto_upper}")
        print(f"      Duration : {flow.duration}s")
        if flow.protocol.lower() == "udp":
            print(f"      Bandwidth: {flow.bandwidth}")
        if flow.parallel > 1:
            print(f"      Parallel : {flow.parallel} streams")

        result = {
            "flow_id": flow.flow_id,
            "src_host": flow.src_host,
            "src_ip": src_ip,
            "dst_host": flow.dst_host,
            "dst_ip": dst_ip,
            "protocol": flow.protocol.lower(),
            "port": flow.port,
            "duration": flow.duration,
            "bandwidth_target": flow.bandwidth if flow.protocol.lower() == "udp" else "auto",
            "parallel_streams": flow.parallel,
            "status": "pending",
            "throughput_mbps": 0.0,
            "packet_loss_pct": 0.0,
            "timestamp": datetime.now().isoformat()
        }

        if self.dry_run:
            # Simulate realistic network transmission
            time.sleep(min(flow.duration, 1.0)) # accelerated simulation sleep
            result["status"] = "completed"
            if flow.protocol.lower() == "udp":
                target_mbps = float(flow.bandwidth.replace("M", "").replace("K", "").replace("G", ""))
                result["throughput_mbps"] = round(target_mbps * 0.98, 2)
                result["packet_loss_pct"] = 0.02
            else:
                result["throughput_mbps"] = round(94.5 * flow.parallel, 2)
                result["packet_loss_pct"] = 0.0
            print(f"  [✓] Simulated {proto_upper} Flow Completed: {result['throughput_mbps']} Mbps")
            return result

        # Real iperf3 execution
        cmd = [
            self.iperf3_path or "iperf3",
            "-c", dst_ip,
            "-p", str(flow.port),
            "-t", str(flow.duration),
            "-J" # Output JSON
        ]

        if flow.protocol.lower() == "udp":
            cmd.extend(["-u", "-b", flow.bandwidth])
        if flow.parallel > 1:
            cmd.extend(["-P", str(flow.parallel)])

        try:
            if self.net:
                src_obj = self.net.get(flow.src_host)
                raw_output = src_obj.cmd(" ".join(cmd))
            else:
                proc_out = subprocess.run(cmd, capture_output=True, text=True, timeout=flow.duration + 5)
                raw_output = proc_out.stdout

            # Parse JSON output from iperf3
            data = json.loads(raw_output)
            end_stats = data.get("end", {})
            if flow.protocol.lower() == "udp":
                udp_stats = end_stats.get("sum", {})
                bps = udp_stats.get("bits_per_second", 0)
                loss = udp_stats.get("lost_percent", 0.0)
            else:
                tcp_stats = end_stats.get("sum_received", end_stats.get("sum_sent", {}))
                bps = tcp_stats.get("bits_per_second", 0)
                loss = 0.0

            result["status"] = "completed"
            result["throughput_mbps"] = round(bps / 1e6, 2)
            result["packet_loss_pct"] = round(loss, 2)
            print(f"  [✓] Flow Completed: {result['throughput_mbps']} Mbps (Loss: {result['packet_loss_pct']}%)")
        except Exception as e:
            result["status"] = "error"
            result["error_message"] = str(e)
            print(f"  [!] Flow Error: {e}")

        return result

    def run_scenario(self, flows: List[FlowConfig], scenario_name: str = "custom") -> List[Dict[str, Any]]:
        """
        Execute a complete scenario of flows concurrently.
        1. Start all required iperf3 servers on destination hosts.
        2. Launch client flows simultaneously using worker threads.
        3. Collect logs and clean up processes.
        """
        print("\n" + "=" * 65)
        print(f"Executing Traffic Scenario: '{scenario_name.upper()}' ({len(flows)} Flows)")
        print("=" * 65)

        # Step 1: Identify and start required servers
        unique_servers = set()
        for f in flows:
            unique_servers.add((f.dst_host, f.port, f.protocol))

        print("\n[*] Phase 1: Provisioning Destination iperf3 Servers...")
        for dst_host, port, proto in unique_servers:
            self.start_iperf_server(dst_host, port, proto)

        time.sleep(0.5) # Allow server ports to bind

        # Step 2: Concurrently launch client flows
        print("\n[*] Phase 2: Launching Client Traffic Streams...")
        results = []
        threads = []

        def worker(flow_spec):
            res = self.run_iperf_client(flow_spec)
            with self._lock:
                results.append(res)

        for flow in flows:
            t = threading.Thread(target=worker, args=(flow,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.results.extend(results)

        # Step 3: Save Logs
        self._save_logs(scenario_name, results)

        # Step 4: Cleanup
        self.stop_all()

        print("\n" + "=" * 65)
        print(f"Scenario '{scenario_name}' Finished. Results Saved to {self.log_dir}")
        print("=" * 65 + "\n")

        return results

    def _save_logs(self, scenario_name: str, results: List[Dict[str, Any]]):
        """Save structured JSON log and summary report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = os.path.join(self.log_dir, f"{scenario_name}_{timestamp}.json")
        log_file = os.path.join(self.log_dir, f"{scenario_name}_{timestamp}.log")

        log_payload = {
            "scenario": scenario_name,
            "timestamp": timestamp,
            "flow_count": len(results),
            "results": results
        }

        with open(json_file, "w") as f:
            json.dump(log_payload, f, indent=2)

        with open(log_file, "w") as f:
            f.write(f"Traffic Scenario Execution Log: {scenario_name.upper()}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write("=" * 60 + "\n")
            for r in results:
                f.write(f"Flow ID   : {r.get('flow_id')}\n")
                f.write(f"Route     : {r.get('src_host')} ({r.get('src_ip')}) -> {r.get('dst_host')} ({r.get('dst_ip')}:{r.get('port')})\n")
                f.write(f"Protocol  : {r.get('protocol', '').upper()}\n")
                f.write(f"Duration  : {r.get('duration')}s\n")
                f.write(f"Bitrate   : {r.get('throughput_mbps')} Mbps\n")
                f.write(f"Loss Pct  : {r.get('packet_loss_pct')}%\n")
                f.write(f"Status    : {r.get('status')}\n")
                f.write("-" * 60 + "\n")

        print(f"  [i] Log written: {json_file}")
        print(f"  [i] Summary log: {log_file}")

    def stop_all(self):
        """Stop all running iperf3 servers and child processes."""
        print("\n[*] Cleaning up active iperf3 processes...")

        # Terminate Popen processes
        for proc in self.server_procs + self.client_procs:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        # Mininet host cleanup
        if self.net:
            for host_name in self.active_servers:
                try:
                    host_obj = self.net.get(host_name)
                    host_obj.cmd("killall -9 iperf3 2>/dev/null")
                except Exception:
                    pass

        self.server_procs.clear()
        self.client_procs.clear()
        self.active_servers.clear()
        print("[*] All traffic generator processes stopped.\n")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Adaptive Network Traffic Generator (Phase 3)")
    parser.add_argument(
        "--scenario",
        type=str,
        default="tcp",
        choices=["tcp", "udp", "multi_tcp", "multi_udp", "mixed", "congestion"],
        help="Predefined traffic scenario to execute"
    )
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Flow duration in seconds")
    parser.add_argument("--bandwidth", type=str, default=DEFAULT_UDP_BANDWIDTH, help="UDP target bandwidth (e.g., 10M, 80M)")
    parser.add_argument("--src", type=str, default="h1", help="Source host (for single-flow scenarios)")
    parser.add_argument("--dst", type=str, default="h2", help="Destination host (for single-flow scenarios)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate traffic without spawning real iperf3 processes")
    parser.add_argument("--log-dir", type=str, default=DEFAULT_LOG_DIR, help="Directory to save execution logs")
    return parser.parse_args()


def main():
    args = parse_arguments()

    # Build flow specifications
    flows = get_scenario_flows(
        scenario_name=args.scenario,
        duration=args.duration,
        bandwidth=args.bandwidth,
        src=args.src,
        dst=args.dst
    )

    # Initialize generator and run scenario
    generator = TrafficGenerator(log_dir=args.log_dir, dry_run=args.dry_run)

    # Handle graceful exit on SIGINT
    def signal_handler(sig, frame):
        print("\n[!] Received interrupt signal. Stopping traffic generator...")
        generator.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        generator.run_scenario(flows, scenario_name=args.scenario)
    finally:
        generator.stop_all()


if __name__ == "__main__":
    main()
