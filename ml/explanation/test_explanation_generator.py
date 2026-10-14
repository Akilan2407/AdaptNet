"""Comprehensive Unit Test Suite for Phase 17: Natural-Language Explanation Module.

Tests 15 critical requirements:
1. Complete trace explanation generation (STATUS_SUCCESS)
2. Missing SHAP handling produces STATUS_PARTIAL without crashing
3. Missing policy handling does not invent policy reasons
4. Failed control action correctly reported as FAILED
5. Dry-run mode correctly identified as simulated
6. SHAP direction semantics (increased / decreased)
7. Exact policy reason fidelity from Phase 13
8. Control action and status fidelity from Phase 14
9. Trace ID preservation across pipeline
10. Determinism across repeated generations
11. Tabular CSV export completeness
12. Structured JSONL export completeness
13. Human-readable text report formatting
14. Summary statistics and distribution calculation
15. Prevention of invented causality (no 'caused the congestion' assertions)
"""

import json
from pathlib import Path
import sys
import pandas as pd
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.explanation.config import (
    DEFAULT_EXPLANATIONS_CSV,
    DEFAULT_EXPLANATIONS_JSONL,
    DEFAULT_REPORT_TXT,
    DEFAULT_SUMMARY_JSON,
    STATUS_FAILED,
    STATUS_PARTIAL,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
)
from ml.explanation.explanation_builder import ExplanationBuilder, ExplanationRecord
from ml.explanation.explanation_generator import ExplanationGenerator
from ml.explanation.explanation_templates import ExplanationTemplates
from ml.explanation.explanation_validator import ExplanationValidator


# 1. Complete trace explanation generation
def test_complete_trace_explanation():
    trace = {
        "trace_id": "TRC-000047",
        "timestamp": "2026-09-12 16:01:27",
        "device_id": "h1",
        "flow_id": "h1_192.168.1.10:45672->192.168.1.11:5201_TCP",
        "throughput_mbps": 10.5,
        "rtt_ms": 15.0,
        "packet_loss_percent": 0.0,
        "active_connections": 4,
        "total_flow_count": 1,
        "predicted_congestion_score": 0.3644,
        "predicted_congestion_class": "MEDIUM",
        "traffic_class": "BULK_TRANSFER",
        "classification_confidence": 1.0,
        "policy_rule_id": "POLICY_BULK_MED_CONGESTION",
        "base_priority": "LOW",
        "final_priority": "LOW",
        "policy_reason": "BULK_TRANSFER traffic during MEDIUM predicted congestion received LOW priority.",
        "cluster_id": 1,
        "profile_label": "High-Flow-Activity",
        "control_action": "APPLY",
        "control_target_class": "1:40",
        "control_status": "DRY_RUN",
        "control_interface": "s1-eth1",
    }
    shap = {
        "top_contributors": [
            {"feature": "total_flow_count", "value": 1.0, "shap_value": -0.0087, "direction": "decreased"},
            {"feature": "cluster_id", "value": 1.0, "shap_value": 0.0062, "direction": "increased"},
        ]
    }

    rec = ExplanationBuilder.build_record(trace, shap_record=shap)
    assert rec.explanation_status == STATUS_SUCCESS
    assert "0.3644" in rec.explanation_text
    assert "MEDIUM" in rec.explanation_text
    assert "total_flow_count" in rec.explanation_text
    assert "decreased" in rec.explanation_text
    assert "dry-run mode" in rec.explanation_text


# 2. Missing SHAP handling produces STATUS_PARTIAL
def test_missing_shap_handling():
    trace = {
        "trace_id": "TRC-000001",
        "timestamp": "2026-09-12 15:24:45",
        "device_id": "h1",
        "flow_id": "flow_1",
        "predicted_congestion_score": None,
        "predicted_congestion_class": "UNKNOWN",
        "traffic_class": "BULK_TRANSFER",
        "policy_rule_id": "POLICY_UNKNOWN_CONGESTION_FALLBACK",
        "final_priority": "LOW",
        "policy_reason": "Fallback default LOW priority.",
        "control_status": "SKIPPED",
    }
    # No SHAP record provided
    rec = ExplanationBuilder.build_record(trace, shap_record=None)
    assert rec.explanation_status == STATUS_PARTIAL
    assert "Detailed SHAP feature attributions were not available" in rec.explanation_text


# 3. Missing policy handling
def test_missing_policy_does_not_invent():
    trace = {
        "trace_id": "TRC-000099",
        "device_id": "h2",
        "flow_id": "flow_2",
        "policy_rule_id": "",
        "policy_reason": "",
        "final_priority": "NORMAL",
    }
    rec = ExplanationBuilder.build_record(trace, shap_record=None)
    assert "Policy rationale:" not in rec.explanation_text


# 4. Failed control action correctly reported
def test_failed_control_action():
    text = ExplanationTemplates.format_network_control(
        action="APPLY", target_class="1:10", status="FAILED", interface="eth0"
    )
    assert "failed" in text.lower()
    assert "not applied" in text.lower()


# 5. Dry-run mode correctly identified
def test_dry_run_identification():
    text = ExplanationTemplates.format_network_control(
        action="APPLY", target_class="1:30", status="DRY_RUN", interface="s1-eth1"
    )
    assert "simulated in dry-run mode" in text
    assert "not applied to the live network" in text


# 6. SHAP direction semantics
def test_shap_direction_semantics():
    contribs = [
        {"feature": "packet_loss_percent", "value": 2.5, "shap_value": 0.05, "direction": "increased"},
        {"feature": "throughput_mbps", "value": 15.0, "shap_value": -0.03, "direction": "decreased"},
    ]
    text = ExplanationTemplates.format_shap_contributions(contribs)
    assert "packet_loss_percent (2.5) increased the predicted congestion score" in text
    assert "throughput_mbps (15.0) decreased the predicted congestion score" in text


# 7. Exact policy reason fidelity from Phase 13
def test_policy_reason_fidelity():
    trace = {
        "trace_id": "TRC-000047",
        "policy_rule_id": "RULE_123",
        "final_priority": "HIGH",
        "policy_reason": "Exact deterministic reason from Phase 13.",
    }
    rec = ExplanationBuilder.build_record(trace)
    assert "Exact deterministic reason from Phase 13." in rec.explanation_text
    assert rec.policy_decision["reason"] == "Exact deterministic reason from Phase 13."


# 8. Control action and status fidelity from Phase 14
def test_control_fidelity():
    trace = {
        "trace_id": "TRC-000047",
        "control_action": "CLASS_HIGH",
        "control_target_class": "1:10",
        "control_status": "SUCCESS",
        "control_interface": "s1-eth1",
        "policy_rule_id": "RULE_1",
    }
    rec = ExplanationBuilder.build_record(trace)
    assert rec.network_action["action"] == "CLASS_HIGH"
    assert rec.network_action["target_class"] == "1:10"
    assert rec.network_action["status"] == "SUCCESS"
    assert "successfully applied the CLASS_HIGH traffic control action" in rec.explanation_text


# 9. Trace ID preservation
def test_trace_id_preservation():
    generator = ExplanationGenerator()
    records, _ = generator.generate_all_explanations()
    assert len(records) >= 50
    for i, r in enumerate(records, start=1):
        assert r.trace_id == f"TRC-{i:06d}"


# 10. Determinism across repeated generations
def test_explanation_determinism():
    generator = ExplanationGenerator()
    records1, _ = generator.generate_all_explanations()
    records2, _ = generator.generate_all_explanations()

    assert len(records1) == len(records2)
    for r1, r2 in zip(records1, records2):
        assert r1.trace_id == r2.trace_id
        assert r1.explanation_status == r2.explanation_status
        assert r1.explanation_text == r2.explanation_text


# 11. Tabular CSV export completeness
def test_csv_export_completeness():
    generator = ExplanationGenerator()
    records, _ = generator.generate_all_explanations()

    csv_path = generator.output_dir / "natural_language_explanations.csv"
    assert csv_path.exists()
    df = pd.read_csv(csv_path)
    assert len(df) == len(records)
    assert "trace_id" in df.columns
    assert "explanation_text" in df.columns
    assert "explanation_status" in df.columns
    assert "policy_rule_id" in df.columns


# 12. Structured JSONL export completeness
def test_jsonl_export_completeness():
    generator = ExplanationGenerator()
    records, _ = generator.generate_all_explanations()

    jsonl_path = generator.output_dir / "natural_language_explanations.jsonl"
    assert jsonl_path.exists()
    with open(jsonl_path, "r", encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    assert len(lines) == len(records)
    assert all("trace_id" in item for item in lines)
    assert all("explanation_text" in item for item in lines)


# 13. Human-readable text report formatting
def test_text_report_formatting():
    generator = ExplanationGenerator()
    generator.generate_all_explanations()

    report_path = generator.output_dir / "explanation_report.txt"
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "NETWORK DECISION EXPLANATIONS REPORT" in content
    assert "CONGESTION PREDICTION" in content
    assert "MAIN MODEL CONTRIBUTIONS (SHAP)" in content
    assert "QOS POLICY DECISION" in content
    assert "NETWORK CONTROL ACTION" in content


# 14. Summary statistics calculation
def test_summary_statistics():
    generator = ExplanationGenerator()
    records, summary = generator.generate_all_explanations()

    assert summary["total_traces"] == len(records)
    assert summary["successful_explanations"] >= 3
    assert summary["policy_explanation_coverage"] == 100.0
    assert "top_features" in summary
    assert "priority_distribution" in summary


# 15. Prevention of invented causality
def test_no_invented_causality():
    generator = ExplanationGenerator()
    records, _ = generator.generate_all_explanations()

    for r in records:
        text = r.explanation_text.lower()
        # Strictly forbid asserting real-world causation
        assert "caused the congestion" not in text
        assert "caused congestion" not in text
        assert "user caused" not in text
