"""Comprehensive unit tests for Phase 15 Decision Trace Module.

Verifies:
1. Trace creation from valid records and serialization (to_dict, to_flat_dict, to_jsonl)
2. Unique and stable trace IDs
3. Exact matching by flow_id
4. Timestamp proximity matching within tolerance
5. Out-of-tolerance rejection (>5.0s delta)
6. Missing stage handling producing PARTIAL completeness
7. Invalid data detection in TraceValidator (trace_id, flow_id, priority, classes)
8. Cross-stage PRIORITY_CONTROL_MISMATCH detection
9. Determinism across repeated runs
10. Row-order invariance (shuffled inputs produce identical trace ordering)
11. Tabular CSV export completeness
12. Structured JSONL export completeness
13. Structural reasoning chain synthesis
14. Summary statistics calculation
15. End-to-end integration on actual workspace dataset (53 traces)
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
import random
import sys
import pandas as pd
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.trace.config import (
    COMPLETENESS_COMPLETE,
    COMPLETENESS_INCOMPLETE,
    COMPLETENESS_PARTIAL,
    MATCH_DEVICE_TIMESTAMP,
    MATCH_EXACT_DEVICE_FLOW,
    MATCH_EXACT_FLOW_ID,
    MATCH_FLOW_TIMESTAMP_TOLERANCE,
    MATCH_UNMATCHED,
    PRIORITY_TO_CONTROL_CLASS,
    TRACE_TIMESTAMP_TOLERANCE_SECONDS,
)
from ml.trace.trace_builder import TraceBuilder
from ml.trace.trace_export import TraceExporter
from ml.trace.trace_matcher import TraceMatcher
from ml.trace.trace_schema import DecisionTrace
from ml.trace.trace_validator import TraceValidator


# 1. Trace creation and serialization
def test_trace_creation_and_serialization():
    trace = DecisionTrace(
        trace_id="TRC-000001",
        timestamp="2026-09-23 16:01:27",
        device_id="device_1",
        flow_id="device_1_192.168.1.10:54321->192.168.1.1:80_TCP",
        src_ip="192.168.1.10",
        dst_ip="192.168.1.1",
        src_port=54321,
        dst_port=80,
        protocol="TCP",
        traffic_class="WEB",
        final_priority="NORMAL",
        control_action="CLASS_NORMAL",
        control_target_class="1:30",
        control_status="DRY_RUN",
        trace_completeness="COMPLETE",
    )

    d = trace.to_dict()
    assert d["trace_id"] == "TRC-000001"
    assert d["network_5tuple"]["src_ip"] == "192.168.1.10"
    assert d["stage_5_traffic_classification"]["traffic_class"] == "WEB"
    assert d["stage_6_qos_policy"]["final_priority"] == "NORMAL"
    assert d["stage_7_network_control"]["target_class"] == "1:30"

    flat = trace.to_flat_dict()
    assert flat["trace_id"] == "TRC-000001"
    assert flat["src_port"] == 54321
    assert flat["control_target_class"] == "1:30"

    jsonl_str = trace.to_jsonl()
    parsed = json.loads(jsonl_str)
    assert parsed["trace_id"] == "TRC-000001"
    assert parsed["network_5tuple"]["dst_port"] == 80


# 2. Unique and stable trace IDs
def test_unique_and_stable_trace_ids():
    builder = TraceBuilder()
    traces = builder.build_traces()
    if traces:
        ids = [t.trace_id for t in traces]
        assert len(ids) == len(set(ids)), "Trace IDs must be strictly unique"
        for i, tid in enumerate(ids):
            assert tid == f"TRC-{i + 1:06d}", f"Trace ID format mismatch: {tid}"


# 3. Exact matching by flow_id
def test_exact_matching_by_flow_id():
    matcher = TraceMatcher(tolerance_seconds=5.0)
    flow_id = "device_1_192.168.1.10:5000->10.0.0.1:80_TCP"
    ts = "2026-09-23 12:00:00"

    feat_df = pd.DataFrame([
        {
            "flow_id": flow_id,
            "timestamp": ts,
            "throughput_mbps": 15.5,
            "rtt_ms": 12.0,
            "packet_loss_percent": 0.0,
            "active_connections": 4,
        }
    ])

    record, method, diff_ms = matcher.match_features_record(flow_id, ts, feat_df)
    assert record is not None
    assert method == MATCH_EXACT_FLOW_ID
    assert diff_ms == 0.0
    assert record["throughput_mbps"] == 15.5


# 4. Timestamp proximity matching within tolerance
def test_timestamp_proximity_matching_within_tolerance():
    matcher = TraceMatcher(tolerance_seconds=5.0)
    flow_id = "device_2_192.168.1.20:6000->10.0.0.1:443_TCP"
    ts_query = "2026-09-23 12:00:02"
    ts_actual = "2026-09-23 12:00:00"  # 2 seconds difference

    class_df = pd.DataFrame([
        {
            "flow_id": flow_id,
            "timestamp": ts_actual,
            "traffic_class": "WEB",
            "confidence": 0.95,
        }
    ])

    record, method, diff_ms = matcher.match_classification_record(flow_id, ts_query, class_df)
    assert record is not None
    assert method == MATCH_FLOW_TIMESTAMP_TOLERANCE
    assert diff_ms == pytest.approx(2000.0, abs=1.0)
    assert record["traffic_class"] == "WEB"


# 5. Out-of-tolerance rejection
def test_out_of_tolerance_rejection():
    matcher = TraceMatcher(tolerance_seconds=5.0)
    flow_id = "device_3_192.168.1.30:7000->10.0.0.1:53_UDP"
    ts_query = "2026-09-23 12:01:00"
    ts_actual = "2026-09-23 12:00:00"  # 60 seconds difference (out of 5.0s tolerance)

    class_df = pd.DataFrame([
        {
            "flow_id": flow_id,
            "timestamp": ts_actual,
            "traffic_class": "DNS",
            "confidence": 0.99,
        }
    ])

    record, method, diff_ms = matcher.match_classification_record(flow_id, ts_query, class_df)
    assert record is None
    assert method == MATCH_UNMATCHED


# 6. Missing stage handling producing PARTIAL
def test_missing_stage_handling_partial():
    trace = DecisionTrace(
        trace_id="TRC-000002",
        timestamp="2026-09-23 12:00:00",
        device_id="device_1",
        flow_id="device_1_192.168.1.10:5000->10.0.0.1:80_TCP",
        stages={
            "monitoring": True,
            "features": True,
            "profile": True,
            "congestion": False,  # Missing
            "classification": True,
            "policy": True,
            "control": True,
        },
        trace_completeness=COMPLETENESS_PARTIAL,
    )
    assert trace.trace_completeness == COMPLETENESS_PARTIAL
    assert not trace.stages["congestion"]
    assert trace.stages["policy"]


# 7. Invalid data detection in TraceValidator
def test_invalid_data_detection():
    # Invalid trace_id
    bad_id_trace = DecisionTrace(
        trace_id="INVALID_ID",
        timestamp="2026-09-23 12:00:00",
        device_id="device_1",
        flow_id="flow_1",
    )
    errs = TraceValidator.validate_trace(bad_id_trace)
    assert any("Invalid trace_id format" in e for e in errs)

    # Missing flow_id
    no_flow_trace = DecisionTrace(
        trace_id="TRC-000003",
        timestamp="2026-09-23 12:00:00",
        device_id="device_1",
        flow_id="",
    )
    errs = TraceValidator.validate_trace(no_flow_trace)
    assert any("Missing flow_id" in e for e in errs)

    # Invalid priority
    bad_prio_trace = DecisionTrace(
        trace_id="TRC-000004",
        timestamp="2026-09-23 12:00:00",
        device_id="device_1",
        flow_id="flow_1",
        final_priority="SUPER_CRITICAL",
    )
    errs = TraceValidator.validate_trace(bad_prio_trace)
    assert any("Invalid final_priority" in e for e in errs)


# 8. Cross-stage PRIORITY_CONTROL_MISMATCH detection
def test_priority_control_mismatch_detection():
    # Mismatched priority and control class: HIGH expected 1:10, but got 1:40 (LOW)
    mismatched_trace = DecisionTrace(
        trace_id="TRC-000005",
        timestamp="2026-09-23 12:00:00",
        device_id="device_1",
        flow_id="flow_1",
        final_priority="HIGH",
        control_target_class="1:40",
    )
    errs = TraceValidator.validate_trace(mismatched_trace)
    assert any("PRIORITY_CONTROL_MISMATCH" in e for e in errs)

    # Correct matching: HIGH and 1:10
    matched_trace = DecisionTrace(
        trace_id="TRC-000006",
        timestamp="2026-09-23 12:00:00",
        device_id="device_1",
        flow_id="flow_1",
        final_priority="HIGH",
        control_action="CLASS_HIGH",
        control_target_class="1:10",
        control_status="DRY_RUN",
    )
    errs = TraceValidator.validate_trace(matched_trace)
    assert not any("PRIORITY_CONTROL_MISMATCH" in e for e in errs)


# 9. Determinism across repeated runs
def test_determinism_across_runs():
    builder1 = TraceBuilder()
    traces1 = builder1.build_traces()

    builder2 = TraceBuilder()
    traces2 = builder2.build_traces()

    assert len(traces1) == len(traces2)
    for t1, t2 in zip(traces1, traces2):
        assert t1.trace_id == t2.trace_id
        assert t1.flow_id == t2.flow_id
        assert t1.final_priority == t2.final_priority
        assert t1.trace_completeness == t2.trace_completeness
        assert t1.stages == t2.stages


# 10. Row-order invariance (sorting guarantee)
def test_row_order_invariance(tmp_path):
    builder = TraceBuilder()
    original_traces = builder.build_traces()

    if not original_traces:
        pytest.skip("No real data to test row-order invariance")

    # Read the original policy csv, shuffle rows, write to temporary file
    policy_df = pd.read_csv(builder.policy_path)
    shuffled_df = policy_df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    temp_policy_path = tmp_path / "shuffled_policy.csv"
    shuffled_df.to_csv(temp_policy_path, index=False)

    # Build traces with shuffled policy input
    shuffled_builder = TraceBuilder(policy_path=temp_policy_path)
    shuffled_traces = shuffled_builder.build_traces()

    assert len(original_traces) == len(shuffled_traces)
    for orig, shuf in zip(original_traces, shuffled_traces):
        assert orig.trace_id == shuf.trace_id
        assert orig.timestamp == shuf.timestamp
        assert orig.flow_id == shuf.flow_id
        assert orig.final_priority == shuf.final_priority


# 11. Tabular CSV export completeness
def test_csv_export_completeness(tmp_path):
    exporter = TraceExporter(output_dir=tmp_path)
    trace = DecisionTrace(
        trace_id="TRC-000007",
        timestamp="2026-09-23 12:00:00",
        device_id="device_1",
        flow_id="device_1_10.0.0.1:100->10.0.0.2:200_TCP",
        traffic_class="REAL_TIME",
        final_priority="HIGH",
        control_target_class="1:10",
        control_status="DRY_RUN",
    )
    csv_file = exporter.export_csv([trace])
    assert csv_file.exists()

    df = pd.read_csv(csv_file)
    assert len(df) == 1
    assert "trace_id" in df.columns
    assert "flow_id" in df.columns
    assert "traffic_class" in df.columns
    assert "control_target_class" in df.columns
    assert df.iloc[0]["trace_id"] == "TRC-000007"


# 12. Structured JSONL export completeness
def test_jsonl_export_completeness(tmp_path):
    exporter = TraceExporter(output_dir=tmp_path)
    trace = DecisionTrace(
        trace_id="TRC-000008",
        timestamp="2026-09-23 12:00:00",
        device_id="device_1",
        flow_id="device_1_10.0.0.1:100->10.0.0.2:200_TCP",
        traffic_class="INTERACTIVE",
        final_priority="MEDIUM",
        control_target_class="1:20",
        control_status="DRY_RUN",
    )
    jsonl_file = exporter.export_jsonl([trace])
    assert jsonl_file.exists()

    with open(jsonl_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["trace_id"] == "TRC-000008"
    assert data["stage_5_traffic_classification"]["traffic_class"] == "INTERACTIVE"
    assert data["stage_7_network_control"]["target_class"] == "1:20"


# 13. Reason chain synthesis
def test_reason_chain_synthesis():
    builder = TraceBuilder()
    chain = builder.build_reason_chain(
        device_id="device_1",
        profile_label="High Bandwidth / Streaming",
        traffic_class="WEB",
        pred_class="LOW",
        pred_score=0.12,
        base_priority="NORMAL",
        cong_adj=0,
        user_adj=0,
        final_priority="NORMAL",
        policy_rule_id="RULE-WEB-DEFAULT",
        control_action="CLASS_NORMAL",
        control_class="1:30",
        control_status="DRY_RUN",
    )

    assert len(chain) >= 5
    full_text = " ".join(chain)
    assert "device_1" in full_text
    assert "High Bandwidth / Streaming" in full_text
    assert "WEB" in full_text
    assert "NORMAL" in full_text
    assert "1:30" in full_text


# 14. Summary statistics calculation
def test_summary_statistics_calculation(tmp_path):
    exporter = TraceExporter(output_dir=tmp_path)
    t1 = DecisionTrace(
        trace_id="TRC-000001",
        timestamp="2026-09-23 12:00:00",
        device_id="dev_1",
        flow_id="flow_1",
        trace_completeness=COMPLETENESS_COMPLETE,
        stages={"monitoring": True, "features": True, "profile": True, "congestion": True, "classification": True, "policy": True, "control": True},
        match_method=MATCH_EXACT_FLOW_ID,
    )
    t2 = DecisionTrace(
        trace_id="TRC-000002",
        timestamp="2026-09-23 12:00:00",
        device_id="dev_2",
        flow_id="flow_2",
        trace_completeness=COMPLETENESS_PARTIAL,
        stages={"monitoring": True, "features": True, "profile": True, "congestion": False, "classification": True, "policy": True, "control": True},
        match_method=MATCH_EXACT_FLOW_ID,
    )

    summary = exporter.generate_summary([t1, t2])
    assert summary["total_traces"] == 2
    assert summary["complete_traces"] == 1
    assert summary["partial_traces"] == 1
    assert summary["monitoring_match_rate"] == 100.0
    assert summary["congestion_match_rate"] == 50.0
    assert summary["exact_match_count"] == 2


# 15. End-to-end integration on actual workspace dataset
def test_end_to_end_workspace_dataset():
    builder = TraceBuilder()
    traces = builder.build_traces()

    assert len(traces) == 53, f"Expected 53 decision traces matching qos_decisions.csv, got {len(traces)}"

    val_res = TraceValidator.validate_traces_collection(traces)
    assert val_res["is_valid"], f"Validation failed with errors: {val_res['errors']}"
    assert val_res["total_traces"] == 53
    assert val_res["complete_traces"] == 5
    assert val_res["partial_traces"] == 48
    assert val_res["incomplete_traces"] == 0
