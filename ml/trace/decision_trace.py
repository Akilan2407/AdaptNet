"""Command-line Decision Trace Viewer and Execution Entrypoint (Phase 15)."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.trace.config import (
    DEFAULT_SUMMARY_JSON,
    DEFAULT_TRACES_CSV,
    DEFAULT_TRACES_JSONL,
)
from ml.trace.trace_builder import TraceBuilder
from ml.trace.trace_export import TraceExporter
from ml.trace.trace_report import generate_all_plots
from ml.trace.trace_schema import DecisionTrace
from ml.trace.trace_validator import TraceValidator


def format_human_readable_trace(trace: DecisionTrace) -> str:
    """Format a single DecisionTrace into a human-readable 7-stage chain."""
    lines = [
        "================================================",
        f"DECISION TRACE: {trace.trace_id}",
        "================================================",
        "",
        f"Timestamp : {trace.timestamp}",
        f"Device    : {trace.device_id}",
        f"Flow ID   : {trace.flow_id}",
        f"5-Tuple   : {trace.src_ip}:{trace.src_port} -> {trace.dst_ip}:{trace.dst_port} ({trace.protocol})",
        "",
        "[1] Monitoring (Telemetry)",
        f"  Throughput         : {trace.monitoring.get('throughput', 'N/A')} Mbps",
        f"  RTT                : {trace.monitoring.get('rtt', 'N/A')} ms",
        f"  Packet Loss        : {trace.monitoring.get('packet_loss', 'N/A')} %",
        f"  Active Connections : {trace.monitoring.get('active_connections', 'N/A')}",
        "",
        "[2] Features (Feature Extraction)",
        f"  Throughput (mbps)  : {trace.features.get('throughput_mbps', 'N/A')}",
        f"  RTT (ms)           : {trace.features.get('rtt_ms', 'N/A')}",
        f"  Loss Rate (%)      : {trace.features.get('packet_loss_percent', 'N/A')}",
        f"  TCP Flow Ratio     : {trace.features.get('tcp_flow_ratio', 'N/A')}",
        "",
        "[3] User Profile (K-Means Clustering)",
        f"  Cluster ID         : {trace.cluster_id if trace.cluster_id is not None else 'N/A'}",
        f"  Profile Label      : {trace.profile_label if trace.profile_label else 'N/A'}",
        "",
        "[4] Congestion Prediction (GRU Predictor)",
        f"  Predicted Score    : {trace.predicted_congestion_score if trace.predicted_congestion_score is not None else 'N/A'}",
        f"  Predicted Class    : {trace.predicted_congestion_class}",
        "",
        "[5] Traffic Classification (Rule Engine)",
        f"  Traffic Category   : {trace.traffic_class}",
        f"  Confidence         : {trace.classification_confidence}",
        f"  Reason             : {trace.classification_reason}",
        "",
        "[6] QoS Policy (Decision Engine)",
        f"  Base Priority      : {trace.base_priority}",
        f"  Congestion Adj     : {trace.congestion_adjustment:+d}",
        f"  Profile Adj        : {trace.user_profile_adjustment:+d}",
        f"  Final Priority     : {trace.final_priority}",
        f"  Policy Rule ID     : {trace.policy_rule_id}",
        f"  Policy Reason      : {trace.policy_reason}",
        "",
        "[7] Network Control (Adaptive Shaping)",
        f"  Action             : {trace.control_action if trace.control_action else 'N/A'}",
        f"  Target HTB Class   : {trace.control_target_class if trace.control_target_class else 'N/A'}",
        f"  Interface          : {trace.control_interface if trace.control_interface else 'N/A'}",
        f"  Enforcement Status : {trace.control_status}",
        f"  Rule Identifier    : {trace.control_rule_identifier if trace.control_rule_identifier else 'N/A'}",
        f"  Dry-Run Mode       : {trace.dry_run}",
        "",
        f"Trace Completeness   : {trace.trace_completeness}",
        f"Match Method         : {trace.match_method}",
        f"Temporal Delta       : {trace.timestamp_difference_ms:.1f} ms",
        "Reason Chain         : " + " -> ".join(trace.reason_chain),
        "================================================",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Phase 15 Decision Trace Viewer")
    parser.add_argument("--trace-id", type=str, help="View detailed 7-stage chain for specific trace ID")
    parser.add_argument("--device", type=str, help="Filter traces by device ID (e.g., h1)")
    parser.add_argument("--flow-id", type=str, help="Filter traces by flow ID substring")
    parser.add_argument("--status", type=str, help="Filter traces by control status (SUCCESS, DRY_RUN, SKIPPED)")
    parser.add_argument("--priority", type=str, help="Filter traces by final priority (HIGH, MEDIUM, NORMAL, LOW)")
    parser.add_argument("--summary", action="store_true", help="Display summary statistics only")

    args = parser.parse_args()

    builder = TraceBuilder()
    traces = builder.build_traces()

    if not traces:
        print("[!] No traces could be built. Check that input datasets exist in data/.")
        sys.exit(1)

    # Perform validation
    validation = TraceValidator.validate_traces_collection(traces)
    exporter = TraceExporter()
    summary = exporter.export_all(traces)
    generate_all_plots(summary)

    # Handle --trace-id
    if args.trace_id:
        target_id = args.trace_id.strip().upper()
        matched = [t for t in traces if t.trace_id.upper() == target_id]
        if not matched:
            print(f"[-] No trace found with trace_id '{args.trace_id}'")
            sys.exit(1)
        print(format_human_readable_trace(matched[0]))
        return

    # Handle filtering
    filtered = traces
    if args.device:
        filtered = [t for t in filtered if t.device_id.lower() == args.device.strip().lower()]
    if args.flow_id:
        filtered = [t for t in filtered if args.flow_id.strip() in t.flow_id]
    if args.status:
        filtered = [t for t in filtered if t.control_status.upper() == args.status.strip().upper()]
    if args.priority:
        filtered = [t for t in filtered if t.final_priority.upper() == args.priority.strip().upper()]

    if args.device or args.flow_id or args.status or args.priority:
        print("==========================================================================================")
        print(f"FILTERED DECISION TRACES ({len(filtered)} matches)")
        print("==========================================================================================")
        print(f"{'Trace ID':<12} {'Device':<8} {'Traffic Class':<16} {'Priority':<10} {'Control':<10} {'Status':<10} {'Completeness':<12}")
        print("-" * 90)
        for t in filtered:
            print(f"{t.trace_id:<12} {t.device_id:<8} {t.traffic_class:<16} {t.final_priority:<10} {t.control_target_class:<10} {t.control_status:<10} {t.trace_completeness:<12}")
        print("==========================================================================================")
        return

    # Default: print complete execution report
    print("========================================")
    print("PHASE 15 — DECISION TRACE MODULE")
    print("========================================")
    print(f"Total Traces Generated : {summary['total_traces']}")
    print(f"  Complete Traces      : {summary['complete_traces']}")
    print(f"  Partial Traces       : {summary['partial_traces']}")
    print(f"  Incomplete Traces    : {summary['incomplete_traces']}")
    print()
    print("Stage Match Rates:")
    print(f"  1. Monitoring        : {summary['monitoring_match_rate']}%")
    print(f"  2. Features          : {summary['feature_match_rate']}%")
    print(f"  3. Profile           : {summary['profile_match_rate']}%")
    print(f"  4. Congestion        : {summary['congestion_match_rate']}%")
    print(f"  5. Classification    : {summary['classification_match_rate']}%")
    print(f"  6. Policy            : {summary['policy_match_rate']}%")
    print(f"  7. Control           : {summary['control_match_rate']}%")
    print()
    print("Matching Methods:")
    print(f"  Exact Matches        : {summary['exact_match_count']}")
    print(f"  Tolerance Matches    : {summary['timestamp_tolerance_match_count']}")
    print(f"  Unmatched            : {summary['unmatched_count']}")
    print()
    print(f"Validation Status      : {'PASSED' if validation['is_valid'] else 'FAILED'}")
    if validation["errors"]:
        print("  Errors:")
        for err in validation["errors"][:5]:
            print(f"    - {err}")
    print()
    print("Generated Artifacts:")
    print(f"  CSV   : {DEFAULT_TRACES_CSV}")
    print(f"  JSONL : {DEFAULT_TRACES_JSONL}")
    print(f"  JSON  : {DEFAULT_SUMMARY_JSON}")
    print()
    print(f"Example Trace ID       : {traces[0].trace_id}")
    print(f"Example Reason Chain   : {' -> '.join(traces[0].reason_chain)}")
    print("Phase 15 Status        : COMPLETED")
    print("========================================")


if __name__ == "__main__":
    main()
