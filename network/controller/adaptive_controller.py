#!/usr/bin/env python3
"""Phase 14 Adaptive Traffic Controller (converted from adaptive_controller.c)."""

import csv
from pathlib import Path
import sys
from typing import List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from network.controller.control_config import (
    DEFAULT_CONTROL_ACTIONS_CSV,
    DEFAULT_CONTROL_STATE_CSV,
    DEFAULT_DRY_RUN,
    DEFAULT_QOS_DECISIONS_CSV,
)
from network.controller.control_interface import (
    CommandType,
    ControlRequest,
    ControlStatus,
    dispatch_control_request,
    init_control_subsystem,
    shutdown_control_subsystem,
)
from network.controller.control_logger import (
    ControlLogEntry,
    log_control_action,
)
from network.controller.flow_mapper import parse_flow_id
from network.controller.tc_manager import parse_priority_string


def print_usage(prog_name: str = "adaptive_controller") -> None:
    print(f"Usage: {prog_name} [OPTIONS]\n")
    print("Phase 14 Adaptive Traffic Controller (Linux / Mininet)\n")
    print("Options:")
    print("  --apply-csv <file>   Load Phase 13 QoS decisions CSV and apply controls")
    print(f"                       (default: {DEFAULT_QOS_DECISIONS_CSV})")
    print("  --dry-run            Simulate control actions without modifying kernel (DEFAULT)")
    print("  --enforce            Execute actual tc commands (Linux/Mininet only)")
    print("  --rollback           Reset and remove all project-applied tc rules")
    print("  --status             Display active controller rules")
    print("  --help, -h           Show this help message")


def main() -> None:
    csv_path: Optional[str] = None
    dry_run: bool = DEFAULT_DRY_RUN
    do_rollback: bool = False
    do_status: bool = False

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--apply-csv" and i + 1 < len(args):
            i += 1
            csv_path = args[i]
        elif arg == "--dry-run":
            dry_run = True
        elif arg == "--enforce":
            dry_run = False
        elif arg == "--rollback":
            do_rollback = True
        elif arg == "--status":
            do_status = True
        elif arg in ("--help", "-h"):
            print_usage(sys.argv[0])
            sys.exit(0)
        else:
            sys.stderr.write(f"Unknown option: {arg}\n")
            print_usage(sys.argv[0])
            sys.exit(1)
        i += 1

    init_control_subsystem(dry_run)

    if do_rollback:
        print(f"[*] Executing Rollback on all managed interfaces (dry_run={'true' if dry_run else 'false'})...")
        req = ControlRequest(command=CommandType.CMD_RESET, dry_run=dry_run)
        ok, resp = dispatch_control_request(req)
        print(f"[+] Rollback completed. Status: {resp.status_str} ({resp.executed_command})")
        shutdown_control_subsystem()
        sys.exit(0)

    if do_status:
        req = ControlRequest(command=CommandType.CMD_STATUS, dry_run=dry_run)
        ok, resp = dispatch_control_request(req)
        print(f"[*] Controller Status: {resp.status_str} ({resp.executed_command})")
        shutdown_control_subsystem()
        sys.exit(0)

    if not csv_path:
        csv_path = DEFAULT_QOS_DECISIONS_CSV

    csv_file = Path(csv_path)
    if not csv_file.exists():
        sys.stderr.write(f"[-] Error: Failed to open decisions CSV at '{csv_path}'\n")
        shutdown_control_subsystem()
        sys.exit(1)

    print("========================================")
    print("PHASE 14 — ADAPTIVE TRAFFIC CONTROLLER")
    print("========================================")
    print(f"Mode: {'DRY-RUN (Safe Simulation)' if dry_run else 'ENFORCE (Active Kernel Actuation)'}")
    print(f"Input Decisions: {csv_path}\n")

    total_processed = 0
    total_applied = 0
    total_updated = 0
    total_skipped = 0
    total_failed = 0

    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_processed += 1
                ts = row.get("timestamp", "")
                device_id = row.get("device_id", "")
                flow_id = row.get("flow_id", "")
                traffic_class = row.get("traffic_class", "OTHER")
                cong_class = row.get("predicted_congestion_class", "UNKNOWN")
                priority_str = row.get("final_priority", "NORMAL")
                completeness = row.get("input_completeness", "COMPLETE")

                # Fallback Behavior: If input is PARTIAL, skip restriction and log as SKIPPED
                if completeness != "COMPLETE":
                    skip_log = ControlLogEntry(
                        timestamp=ts,
                        device_id=device_id,
                        flow_id=flow_id,
                        traffic_class=traffic_class,
                        predicted_congestion_class=cong_class,
                        final_priority=priority_str,
                        action="APPLY",
                        status="SKIPPED",
                        dry_run=dry_run,
                        error_message="Input completeness PARTIAL; default handling retained",
                    )
                    log_control_action(skip_log)
                    total_skipped += 1
                    continue

                tuple_val = parse_flow_id(flow_id)
                if tuple_val is None:
                    total_failed += 1
                    continue

                prio = parse_priority_string(priority_str)
                req = ControlRequest(
                    command=CommandType.CMD_APPLY,
                    device_id=tuple_val.device_id,
                    flow_id=flow_id,
                    src_ip=tuple_val.src_ip,
                    dst_ip=tuple_val.dst_ip,
                    src_port=tuple_val.src_port,
                    dst_port=tuple_val.dst_port,
                    protocol=tuple_val.protocol,
                    traffic_class=traffic_class,
                    predicted_congestion_class=cong_class,
                    priority=prio,
                    interface=tuple_val.interface,
                    dry_run=dry_run,
                )

                ok, resp = dispatch_control_request(req)
                if resp.status in (ControlStatus.CTRL_STATUS_SUCCESS, ControlStatus.CTRL_STATUS_DRY_RUN):
                    total_applied += 1
                elif resp.status == ControlStatus.CTRL_STATUS_SKIPPED:
                    total_skipped += 1
                else:
                    total_failed += 1

    except Exception as exc:
        sys.stderr.write(f"[-] Error reading decisions CSV: {exc}\n")
        shutdown_control_subsystem()
        sys.exit(1)

    print("Control Processing Summary:")
    print(f"  Total Decisions Evaluated : {total_processed}")
    print(f"  Rules Applied / Simulated : {total_applied}")
    print(f"  Rules Updated             : {total_updated}")
    print(f"  Rules Skipped (Fallback)  : {total_skipped}")
    print(f"  Operations Failed         : {total_failed}")
    print("\nOutputs:")
    print(f"  Actions Log : {DEFAULT_CONTROL_ACTIONS_CSV}")
    print(f"  State Log   : {DEFAULT_CONTROL_STATE_CSV}")
    print("========================================")

    shutdown_control_subsystem()
    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
