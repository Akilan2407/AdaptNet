#!/usr/bin/env python3
"""Synthetic LAN Network Telemetry Generator.

Generates rich, physically consistent multi-device time-series telemetry
incorporating realistic traffic regimes (nominal, burst, bufferbloat, packet loss).
Populates data/monitoring/network_metrics.csv to provide realistic training
data for user profiling (Phase 8), GRU congestion forecasting (Phase 9-10),
and SHAP explainability (Phase 16).
"""

import argparse
import math
from pathlib import Path
import random
import sys
from typing import List, Dict, Any

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "monitoring" / "network_metrics.csv"

HOST_CONFIG = {
    "h1": {"ip": "192.168.1.10", "role": "bulk_transfer_streaming"},
    "h2": {"ip": "192.168.1.11", "role": "interactive_web"},
    "h3": {"ip": "192.168.1.12", "role": "udp_streaming_gaming"},
    "h4": {"ip": "192.168.1.13", "role": "database_sync"},
    "h5": {"ip": "192.168.1.14", "role": "heavy_congestion_sink"},
}


def generate_synthetic_telemetry(
    duration_seconds: int = 1200,
    interval_seconds: int = 2,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    random_seed: int = 42,
) -> int:
    """Generate continuous multi-host network telemetry records."""
    random.seed(random_seed)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base_time_epoch = 1789228800  # 2026-09-12 16:00:00 UTC
    hosts = list(HOST_CONFIG.keys())
    records = []

    steps = duration_seconds // interval_seconds

    for step in range(steps):
        t_sec = step * interval_seconds
        timestamp = base_time_epoch + t_sec
        time_str = (
            f"2026-09-12 {16 + (t_sec // 3600):02d}:"
            f"{(t_sec % 3600) // 60:02d}:{t_sec % 60:02d}"
        )

        # Progress through 4 global network regime phases
        # Phase 1: 0 - 25% (Calm / Baseline)
        # Phase 2: 25 - 55% (Growing traffic / Streaming load)
        # Phase 3: 55 - 80% (Peak congestion / Bufferbloat / Packet drops)
        # Phase 4: 80 - 100% (Recovery / Cool down)
        phase_ratio = t_sec / float(duration_seconds)
        if phase_ratio < 0.25:
            global_congestion = 0.10 + 0.10 * math.sin(step * 0.1)
        elif phase_ratio < 0.55:
            global_congestion = 0.35 + 0.20 * math.sin(step * 0.12)
        elif phase_ratio < 0.80:
            global_congestion = 0.75 + 0.20 * math.sin(step * 0.08)
        else:
            global_congestion = 0.25 + 0.15 * math.sin(step * 0.1)

        global_congestion = max(0.02, min(0.98, global_congestion))

        for host in hosts:
            role = HOST_CONFIG[host]["role"]
            src_ip = HOST_CONFIG[host]["ip"]
            # Pick a destination host different from self
            dst_host = random.choice([h for h in hosts if h != host])
            dst_ip = HOST_CONFIG[dst_host]["ip"]

            if role == "bulk_transfer_streaming":
                # High throughput, moderate to high connections
                tp = 25.0 + 60.0 * global_congestion + random.uniform(-4.0, 6.0)
                rtt = 5.0 + 55.0 * global_congestion + random.uniform(-2.0, 4.0)
                loss = (global_congestion ** 2) * 5.5 + random.uniform(0.0, 0.4)
                conn = int(6 + 16 * global_congestion + random.randint(-1, 2))
                proto = "TCP" if random.random() < 0.85 else "UDP"
                dst_port = 5201 if proto == "TCP" else 5001

            elif role == "interactive_web":
                # Low to medium throughput, quick RTT, low loss
                tp = 3.0 + 18.0 * (global_congestion * 0.6) + random.uniform(-1.0, 2.0)
                rtt = 3.0 + 20.0 * global_congestion + random.uniform(-1.0, 3.0)
                loss = (global_congestion ** 3) * 1.5 + random.uniform(0.0, 0.1)
                conn = int(2 + 6 * global_congestion + random.randint(0, 1))
                proto = "TCP"
                dst_port = 443 if random.random() < 0.7 else 80

            elif role == "udp_streaming_gaming":
                # Balanced UDP/TCP, sensitive to jitter & loss
                tp = 10.0 + 45.0 * global_congestion + random.uniform(-3.0, 4.0)
                rtt = 4.0 + 40.0 * global_congestion + random.uniform(-2.0, 5.0)
                loss = (global_congestion ** 1.8) * 4.5 + random.uniform(0.0, 0.5)
                conn = int(3 + 8 * global_congestion + random.randint(-1, 1))
                proto = "UDP" if random.random() < 0.70 else "TCP"
                dst_port = 5004 if proto == "UDP" else 5201

            elif role == "database_sync":
                # Steady throughput, periodic spikes
                burst = 25.0 if (step % 15 == 0) else 0.0
                tp = 8.0 + 35.0 * global_congestion + burst + random.uniform(-2.0, 3.0)
                rtt = 4.0 + 35.0 * global_congestion + random.uniform(-1.5, 2.5)
                loss = (global_congestion ** 2.2) * 2.8 + random.uniform(0.0, 0.2)
                conn = int(4 + 10 * global_congestion + random.randint(0, 2))
                proto = "TCP"
                dst_port = 5432

            else:  # heavy_congestion_sink (h5)
                # Suffers severe bufferbloat during congestion peaks
                if phase_ratio >= 0.50 and phase_ratio <= 0.82:
                    tp = 65.0 + 32.0 * global_congestion + random.uniform(-3.0, 5.0)
                    rtt = 45.0 + 95.0 * global_congestion + random.uniform(-5.0, 15.0)
                    loss = 3.5 + 8.0 * (global_congestion ** 1.5) + random.uniform(0.0, 1.2)
                    conn = int(14 + 11 * global_congestion + random.randint(-1, 2))
                else:
                    tp = 10.0 + 25.0 * global_congestion + random.uniform(-2.0, 3.0)
                    rtt = 5.0 + 25.0 * global_congestion + random.uniform(-1.0, 3.0)
                    loss = 0.1 + 1.0 * global_congestion + random.uniform(0.0, 0.1)
                    conn = int(3 + 6 * global_congestion + random.randint(0, 1))
                proto = "TCP" if random.random() < 0.80 else "UDP"
                dst_port = 5201

            # Bounds clamping
            tp = max(0.1, round(tp, 2))
            rtt_val = max(1.0, round(rtt, 2)) if proto == "TCP" else "N/A"
            loss_val = max(0.0, min(100.0, round(loss, 2)))
            conn = max(1, conn)
            src_port = random.randint(32768, 61000)

            records.append({
                "timestamp": time_str,
                "device_id": host,
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "src_port": src_port,
                "dst_port": dst_port,
                "protocol": proto,
                "throughput": f"{tp:.2f}",
                "rtt": f"{rtt_val:.2f}" if rtt_val != "N/A" else "N/A",
                "packet_loss": f"{loss_val:.2f}",
                "active_connections": conn,
            })

    # Write to CSV
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("timestamp,device_id,src_ip,dst_ip,src_port,dst_port,protocol,throughput,rtt,packet_loss,active_connections\n")
        for r in records:
            f.write(
                f"{r['timestamp']},{r['device_id']},{r['src_ip']},{r['dst_ip']},"
                f"{r['src_port']},{r['dst_port']},{r['protocol']},{r['throughput']},"
                f"{r['rtt']},{r['packet_loss']},{r['active_connections']}\n"
            )

    return len(records)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic LAN network telemetry.")
    parser.add_argument("--duration", type=int, default=1200, help="Total simulation duration in seconds (default 1200).")
    parser.add_argument("--interval", type=int, default=2, help="Sample interval in seconds (default 2).")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Path to output CSV.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")

    args = parser.parse_args()
    count = generate_synthetic_telemetry(
        duration_seconds=args.duration,
        interval_seconds=args.interval,
        output_path=args.output,
        random_seed=args.seed,
    )
    print(f"[+] Successfully generated {count} telemetry records at: {args.output}")


if __name__ == "__main__":
    main()
