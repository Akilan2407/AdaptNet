#!/usr/bin/env python3
"""Monitoring Agent skeleton CLI entrypoint (converted from network/agent/main.c)."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from network.common.protocol import PROTOCOL_MAGIC, HEADER_SIZE, TELEMETRY_SIZE


def main() -> None:
    print("=====================================================")
    print("Adaptive Network Traffic Management - C Monitoring Agent")
    print("Version: 0.1.0 (Phase 1 Skeleton)")
    print(f"Protocol Magic: 0x{PROTOCOL_MAGIC:X} | Header Size: {HEADER_SIZE} bytes")
    print(f"Telemetry Metric Size: {TELEMETRY_SIZE} bytes")
    print("=====================================================")

    if len(sys.argv) > 1 and sys.argv[1].startswith("-v"):
        sys.exit(0)

    print("Monitoring Agent initialized in standby mode.")
    sys.exit(0)


if __name__ == "__main__":
    main()
