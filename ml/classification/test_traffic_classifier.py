"""Unit Test Suite for Phase 12 Traffic Classification Module.

Tests 15 critical requirements:
1. TCP port 80 -> WEB
2. TCP port 443 -> WEB
3. UDP port 53 -> DNS
4. TCP port 53 -> DNS
5. TCP port 22 -> INTERACTIVE
6. Port-range matching (e.g. UDP 3478 -> REAL_TIME)
7. Unknown port -> OTHER
8. Unknown protocol handling
9. Invalid port handling
10. Deterministic flow ID generation
11. Confidence score generation
12. Reason string explainability
13. Output DataFrame schema verification
14. No packet payload inspection assertion
15. Deterministic rule priority enforcement
"""

import pandas as pd
import pytest

from ml.classification.classification_rules import (
    evaluate_port_rules,
    is_port_in_range,
    is_valid_port,
    matches_port_spec,
    normalize_protocol,
)
from ml.classification.config import (
    CONFIDENCE_EXACT_PORT,
    CONFIDENCE_PORT_RANGE,
    CONFIDENCE_UNKNOWN,
    PORT_RULES,
    RULE_PRIORITY,
    TRAFFIC_CLASSES,
)
from ml.classification.feature_rules import evaluate_secondary_feature_rules
from ml.classification.traffic_classifier import (
    TrafficClassifier,
    generate_deterministic_flow_id,
)


@pytest.fixture
def classifier():
    return TrafficClassifier()


# 1. TCP port 80 classification
def test_tcp_port_80_web(classifier):
    flow = {"protocol": "TCP", "src_port": 54321, "dst_port": 80}
    res = classifier.classify_flow(flow)
    assert res["traffic_class"] == "WEB"
    assert res["classification_confidence"] == CONFIDENCE_EXACT_PORT
    assert "80" in res["classification_reason"]
    assert "WEB" in res["classification_reason"]


# 2. TCP port 443 classification
def test_tcp_port_443_web(classifier):
    flow = {"protocol": "TCP", "src_port": 49152, "dst_port": 443}
    res = classifier.classify_flow(flow)
    assert res["traffic_class"] == "WEB"
    assert res["classification_confidence"] == CONFIDENCE_EXACT_PORT
    assert "443" in res["classification_reason"]


# 3. UDP port 53 classification
def test_udp_port_53_dns(classifier):
    flow = {"protocol": "UDP", "src_port": 53210, "dst_port": 53}
    res = classifier.classify_flow(flow)
    assert res["traffic_class"] == "DNS"
    assert res["classification_confidence"] == CONFIDENCE_EXACT_PORT
    assert "DNS" in res["classification_reason"]


# 4. TCP port 53 classification
def test_tcp_port_53_dns(classifier):
    flow = {"protocol": "TCP", "src_port": 53211, "dst_port": 53}
    res = classifier.classify_flow(flow)
    assert res["traffic_class"] == "DNS"
    assert res["classification_confidence"] == CONFIDENCE_EXACT_PORT


# 5. TCP port 22 classification
def test_tcp_port_22_interactive(classifier):
    flow = {"protocol": "TCP", "src_port": 45000, "dst_port": 22}
    res = classifier.classify_flow(flow)
    assert res["traffic_class"] == "INTERACTIVE"
    assert res["classification_confidence"] == CONFIDENCE_EXACT_PORT
    assert "INTERACTIVE" in res["classification_reason"]


# 6. Port-range matching
def test_port_range_matching(classifier):
    # UDP 3478 is within WebRTC/STUN range 3478-3481
    flow = {"protocol": "UDP", "src_port": 40000, "dst_port": 3478}
    res = classifier.classify_flow(flow)
    assert res["traffic_class"] == "REAL_TIME"
    assert res["classification_confidence"] == CONFIDENCE_PORT_RANGE
    assert "range" in res["classification_reason"]

    # Also test RTP range 5004
    flow_rtp = {"protocol": "UDP", "src_port": 40000, "dst_port": 5004}
    res_rtp = classifier.classify_flow(flow_rtp)
    assert res_rtp["traffic_class"] == "REAL_TIME"


# 7. Unknown port classification
def test_unknown_port_other(classifier):
    flow = {"protocol": "TCP", "src_port": 49999, "dst_port": 49998}
    res = classifier.classify_flow(flow)
    assert res["traffic_class"] == "OTHER"
    assert res["classification_confidence"] == CONFIDENCE_UNKNOWN
    assert "No configured metadata rule matched" in res["classification_reason"]


# 8. Unknown protocol handling
def test_unknown_protocol(classifier):
    flow = {"protocol": "XYZ_PROTOCOL", "src_port": 80, "dst_port": 443}
    res = classifier.classify_flow(flow)
    # Should not match TCP-specific web rules
    assert res["traffic_class"] == "OTHER"
    assert res["classification_confidence"] == 0.0


# 9. Invalid port handling
def test_invalid_port_handling(classifier):
    assert not is_valid_port(0)
    assert not is_valid_port(70000)
    assert not is_valid_port(-1)
    assert not is_valid_port("invalid")
    assert not is_valid_port(None)

    flow = {"protocol": "TCP", "src_port": "bad_port", "dst_port": 80}
    res = classifier.classify_flow(flow)
    # Valid dst_port=80 still matches WEB safely
    assert res["traffic_class"] == "WEB"


# 10. Flow ID generation
def test_flow_id_generation():
    row = {
        "device_id": "h1",
        "src_ip": "192.168.1.10",
        "dst_ip": "192.168.1.11",
        "src_port": 45672,
        "dst_port": 5201,
        "protocol": "TCP",
    }
    fid = generate_deterministic_flow_id(row)
    assert fid == "h1_192.168.1.10:45672->192.168.1.11:5201_TCP"

    # Preserves existing flow_id if already present
    row_with_id = dict(row, flow_id="custom_flow_123")
    assert generate_deterministic_flow_id(row_with_id) == "custom_flow_123"


# 11. Confidence generation
def test_confidence_generation(classifier):
    for port, proto, expected_conf in [
        (80, "TCP", 1.0),
        (3479, "UDP", 0.85),
        (49999, "TCP", 0.0),
    ]:
        res = classifier.classify_flow({"protocol": proto, "src_port": 50000, "dst_port": port})
        assert res["classification_confidence"] == expected_conf
        assert 0.0 <= res["classification_confidence"] <= 1.0


# 12. Reason generation
def test_reason_generation(classifier):
    res_web = classifier.classify_flow({"protocol": "TCP", "src_port": 50000, "dst_port": 80})
    assert len(res_web["classification_reason"]) > 5
    assert "WEB" in res_web["classification_reason"]

    res_unknown = classifier.classify_flow({"protocol": "UDP", "src_port": 50000, "dst_port": 49999})
    assert "No configured metadata rule matched" in res_unknown["classification_reason"]


# 13. Output schema
def test_output_schema(classifier):
    sample_df = pd.DataFrame([{
        "timestamp": "2026-09-12 15:24:45",
        "device_id": "h1",
        "src_ip": "192.168.1.10",
        "dst_ip": "192.168.1.11",
        "src_port": 45672,
        "dst_port": 5201,
        "protocol": "TCP",
        "throughput_mbps": 15.0,
        "rtt_ms": 2.5,
        "packet_loss_percent": 0.0,
        "active_connections": 2,
    }])
    classified = classifier.classify_dataset(sample_df)

    required_cols = [
        "timestamp", "device_id", "flow_id", "src_ip", "dst_ip", "src_port", "dst_port",
        "protocol", "throughput_mbps", "rtt_ms", "packet_loss_percent", "active_connections",
        "traffic_class", "classification_confidence", "classification_reason"
    ]
    for col in required_cols:
        assert col in classified.columns

    assert classified["traffic_class"].iloc[0] == "BULK_TRANSFER"
    assert classified["classification_confidence"].iloc[0] == 1.0


# 14. No payload inspection assertion
def test_no_payload_inspection(classifier):
    """Assert classifier functions strictly on metadata without expecting packet payload fields."""
    metadata_only_flow = {
        "protocol": "TCP",
        "src_port": 12345,
        "dst_port": 443,
        # No payload, no data packets, no payload bytes
    }
    res = classifier.classify_flow(metadata_only_flow)
    assert res["traffic_class"] == "WEB"
    assert "payload" not in res
    assert "packet_data" not in res


# 15. Rule priority when multiple rules match
def test_rule_priority_determinism():
    """Verify that when multiple rules could apply, evaluation priority is strictly deterministic."""
    # Construct a custom rule set where port 9999 is defined in BOTH Rule A and Rule B
    custom_rules = {
        "DNS": {"protocols": ["TCP"], "ports": [9999], "ranges": []},
        "WEB": {"protocols": ["TCP"], "ports": [9999], "ranges": []},
    }

    # If priority is DNS then WEB -> must pick DNS
    classifier_dns_first = TrafficClassifier(port_rules=custom_rules, priority=["DNS", "WEB", "OTHER"])
    res1 = classifier_dns_first.classify_flow({"protocol": "TCP", "src_port": 1234, "dst_port": 9999})
    assert res1["traffic_class"] == "DNS"

    # If priority is WEB then DNS -> must pick WEB
    classifier_web_first = TrafficClassifier(port_rules=custom_rules, priority=["WEB", "DNS", "OTHER"])
    res2 = classifier_web_first.classify_flow({"protocol": "TCP", "src_port": 1234, "dst_port": 9999})
    assert res2["traffic_class"] == "WEB"
