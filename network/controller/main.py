#!/usr/bin/env python3
"""Network Controller skeleton CLI entrypoint (converted from network/controller/main.c)."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from network.common.protocol import DEFAULT_CONTROLLER_PORT, DEFAULT_AGENT_PORT


def main() -> None:
    print("=====================================================")
    print("Adaptive Network Traffic Management - C Network Controller")
    print("Version: 0.1.0 (Phase 1 Skeleton)")
    print(f"Default Controller Port: {DEFAULT_CONTROLLER_PORT} | Agent Port: {DEFAULT_AGENT_PORT}")
    print("=====================================================")

    if len(sys.argv) > 1 and sys.argv[1].startswith("-v"):
        sys.exit(0)

    print("Network Controller initialized in standby mode.")
    sys.exit(0)


if __name__ == "__main__":
    main()
