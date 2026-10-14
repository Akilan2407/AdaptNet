#!/usr/bin/env python3
"""Multi-threaded TCP network controller & data ingestion server (converted from network_controller.h/.c)."""

from dataclasses import dataclass
from pathlib import Path
import select
import signal
import socket
import sys
from typing import List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from network.controller.client_handler import start_client_handler
from network.ingestion.data_ingestion import (
    data_ingestion_destroy,
    data_ingestion_init,
    data_ingestion_print_stats,
)


DEFAULT_CONTROLLER_BIND_IP = "0.0.0.0"
DEFAULT_CONTROLLER_LISTEN_PORT = 5000
DEFAULT_METRICS_CSV = "data/monitoring/network_metrics.csv"
DEFAULT_METRICS_JSONL = "data/monitoring/network_metrics.jsonl"
DEFAULT_INVALID_LOG = "data/monitoring/invalid_records.log"
DEFAULT_BUFFER_CAPACITY = 1000


@dataclass
class ControllerConfig:
    bind_ip: str = DEFAULT_CONTROLLER_BIND_IP
    port: int = DEFAULT_CONTROLLER_LISTEN_PORT
    output_csv: str = DEFAULT_METRICS_CSV
    output_jsonl: str = DEFAULT_METRICS_JSONL
    invalid_log: str = DEFAULT_INVALID_LOG
    buffer_size: int = DEFAULT_BUFFER_CAPACITY
    verbose: bool = True


def print_usage(prog_name: str = "network_controller") -> None:
    print(f"Usage: {prog_name} [OPTIONS]\n")
    print("Options:")
    print(f"  --port <port>         Port to listen on (default: {DEFAULT_CONTROLLER_LISTEN_PORT})")
    print(f"  --bind <ip>           IP address to bind to (default: {DEFAULT_CONTROLLER_BIND_IP})")
    print("  --buffer-size <N>     In-memory circular ring buffer capacity (default: 1000)")
    print(f"  --output <csv_file>   CSV output path for validated records (default: {DEFAULT_METRICS_CSV})")
    print(f"  --jsonl <jsonl_file>  JSON Lines output path (default: {DEFAULT_METRICS_JSONL})")
    print(f"  --invalid-log <file>  Invalid/rejected records log path (default: {DEFAULT_INVALID_LOG})")
    print("  --help, -h            Display this help message")


def parse_controller_args(argv: List[str]) -> ControllerConfig:
    config = ControllerConfig()
    i = 1
    n = len(argv)

    while i < n:
        arg = argv[i]
        if arg in ("--help", "-h"):
            print_usage(argv[0])
            sys.exit(0)
        elif arg == "--port" and i + 1 < n:
            i += 1
            val_str = argv[i]
            try:
                val = int(val_str)
                if val <= 0 or val > 65535:
                    sys.stderr.write(f"[ERROR] Invalid port: {val_str}\n")
                    sys.exit(1)
                config.port = val
            except ValueError:
                sys.stderr.write(f"[ERROR] Invalid port: {val_str}\n")
                sys.exit(1)
        elif arg == "--bind" and i + 1 < n:
            i += 1
            config.bind_ip = argv[i]
        elif arg == "--buffer-size" and i + 1 < n:
            i += 1
            config.buffer_size = int(argv[i])
            if config.buffer_size == 0:
                config.buffer_size = DEFAULT_BUFFER_CAPACITY
        elif arg == "--output" and i + 1 < n:
            i += 1
            config.output_csv = argv[i]
        elif arg == "--jsonl" and i + 1 < n:
            i += 1
            config.output_jsonl = argv[i]
        elif arg == "--invalid-log" and i + 1 < n:
            i += 1
            config.invalid_log = argv[i]
        else:
            sys.stderr.write(f"[ERROR] Unknown option '{arg}'\n")
            print_usage(argv[0])
            sys.exit(1)
        i += 1

    return config


def run_network_controller(config: ControllerConfig) -> int:
    running = True

    def sig_handler(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # Initialize Data Ingestion Pipeline
    if data_ingestion_init(
        buffer_size=config.buffer_size,
        csv_path=config.output_csv,
        jsonl_path=config.output_jsonl,
        invalid_log_path=config.invalid_log,
    ) != 0:
        sys.stderr.write("[!] Failed to initialize Data Ingestion Pipeline\n")
        return 1

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((config.bind_ip, config.port))
        server_sock.listen(128)
        server_sock.setblocking(False)
    except Exception as exc:
        sys.stderr.write(f"[!] Bind/Listen to {config.bind_ip}:{config.port} failed: {exc}\n")
        data_ingestion_destroy()
        return 1

    print("=========================================================")
    print("C Network Controller & Data Ingestion Hub (Phase 6)")
    print(f"Listening On    : {config.bind_ip}:{config.port}")
    print(f"Buffer Capacity : {config.buffer_size} records")
    print(f"CSV Storage     : {config.output_csv}")
    print(f"JSONL Storage   : {config.output_jsonl}")
    print(f"Invalid Log     : {config.invalid_log}")
    print("Status          : Ingestion Active (Ctrl+C to quit)")
    print("=========================================================")

    try:
        while running:
            # Non-blocking poll for incoming connections
            readable, _, _ = select.select([server_sock], [], [], 0.2)
            if not running:
                break
            if readable:
                try:
                    client_sock, client_addr = server_sock.accept()
                    client_sock.setblocking(True)
                    start_client_handler(client_sock, client_addr)
                except BlockingIOError:
                    pass
                except Exception:
                    if not running:
                        break
    finally:
        print("\n[*] Shutting down C Network Controller & Ingestion Engine...")
        try:
            server_sock.close()
        except Exception:
            pass

        data_ingestion_print_stats()
        data_ingestion_destroy()
        print("[*] Controller & Ingestion Engine stopped cleanly.")

    return 0


def main() -> None:
    config = parse_controller_args(sys.argv)
    ret = run_network_controller(config)
    sys.exit(ret)


if __name__ == "__main__":
    main()
