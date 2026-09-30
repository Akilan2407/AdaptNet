"""Unit tests for Phase 13 QoS Policy Engine.

Covers the 16 required test scenarios specified in the project requirements:
1. LOW congestion + REAL_TIME
2. MEDIUM congestion + REAL_TIME
3. HIGH congestion + REAL_TIME
4. HIGH congestion + BULK_TRANSFER
5. MEDIUM congestion + WEB
6. LOW congestion + OTHER
7. Unknown traffic class
8. Missing congestion prediction
9. Missing cluster
10. Cluster adjustment
11. Priority clamping
12. Rule priority / order
13. Deterministic output
14. Reason generation
15. Rule ID generation
16. Input validation
"""

from pathlib import Path
import sys

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from ml.policy.config import PRIORITY_LEVELS, TRAFFIC_CLASSES
from ml.policy.priority import (
    priority_to_numeric,
    numeric_to_priority,
    apply_priority_adjustment,
    clamp_numeric,
)
from ml.policy.qos_policy_engine import QoSPolicyEngine
from ml.policy.policy_rules import find_matching_rule


@pytest.fixture
def engine() -> QoSPolicyEngine:
    """Fixture providing a standard QoS Policy Engine instance."""
    return QoSPolicyEngine()


# 1. LOW congestion + REAL_TIME
def test_low_congestion_real_time(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h1",
        "flow_id": "flow_rt_1",
        "traffic_class": "REAL_TIME",
        "predicted_congestion_class": "LOW",
        "cluster_id": 0,
    }
    decision = engine.evaluate(ctx)
    assert decision["final_priority"] == "HIGH"
    assert decision["predicted_congestion_class"] == "LOW"
    assert decision["traffic_class"] == "REAL_TIME"
    assert decision["policy_rule_id"] == "POLICY_LOW_CONGESTION_BASE"


# 2. MEDIUM congestion + REAL_TIME
def test_medium_congestion_real_time(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h1",
        "flow_id": "flow_rt_2",
        "traffic_class": "REAL_TIME",
        "predicted_congestion_class": "MEDIUM",
        "cluster_id": 0,
    }
    decision = engine.evaluate(ctx)
    assert decision["final_priority"] == "HIGH"
    assert decision["policy_rule_id"] == "POLICY_RT_MED_CONGESTION"


# 3. HIGH congestion + REAL_TIME
def test_high_congestion_real_time(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h1",
        "flow_id": "flow_rt_3",
        "traffic_class": "REAL_TIME",
        "predicted_congestion_class": "HIGH",
        "cluster_id": 1,
    }
    decision = engine.evaluate(ctx)
    assert decision["final_priority"] == "HIGH"
    assert decision["policy_rule_id"] == "POLICY_RT_HIGH_CONGESTION"


# 4. HIGH congestion + BULK_TRANSFER
def test_high_congestion_bulk_transfer(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h2",
        "flow_id": "flow_bulk_1",
        "traffic_class": "BULK_TRANSFER",
        "predicted_congestion_class": "HIGH",
        "cluster_id": 0,
    }
    decision = engine.evaluate(ctx)
    assert decision["final_priority"] == "LOW"
    assert decision["policy_rule_id"] == "POLICY_BULK_HIGH_CONGESTION"


# 5. MEDIUM congestion + WEB
def test_medium_congestion_web(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h3",
        "flow_id": "flow_web_1",
        "traffic_class": "WEB",
        "predicted_congestion_class": "MEDIUM",
        "cluster_id": 0,
    }
    decision = engine.evaluate(ctx)
    assert decision["final_priority"] == "MEDIUM"
    assert decision["policy_rule_id"] == "POLICY_WEB_MED_CONGESTION"


# 6. LOW congestion + OTHER
def test_low_congestion_other(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h4",
        "flow_id": "flow_other_1",
        "traffic_class": "OTHER",
        "predicted_congestion_class": "LOW",
        "cluster_id": 0,
    }
    decision = engine.evaluate(ctx)
    assert decision["final_priority"] == "NORMAL"
    assert decision["policy_rule_id"] == "POLICY_LOW_CONGESTION_BASE"


# 7. Unknown traffic class
def test_unknown_traffic_class(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h1",
        "flow_id": "flow_unknown_tc",
        "traffic_class": "BITTORRENT_P2P",  # Unrecognized class
        "predicted_congestion_class": "LOW",
        "cluster_id": 0,
    }
    decision = engine.evaluate(ctx)
    assert decision["traffic_class"] == "OTHER"
    assert decision["final_priority"] == "NORMAL"


# 8. Missing congestion prediction
def test_missing_congestion_prediction(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h2",
        "flow_id": "flow_no_pred",
        "traffic_class": "WEB",
        "predicted_congestion_class": None,
        "predicted_congestion_score": None,
        "cluster_id": 0,
    }
    decision = engine.evaluate(ctx)
    assert decision["predicted_congestion_class"] == "UNKNOWN"
    assert decision["final_priority"] == "MEDIUM"  # Default base priority for WEB
    assert decision["policy_rule_id"] == "POLICY_UNKNOWN_CONGESTION_FALLBACK"
    assert decision["input_completeness"] == "PARTIAL"


# 9. Missing cluster
def test_missing_cluster(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h5",
        "flow_id": "flow_no_cluster",
        "traffic_class": "BULK_TRANSFER",
        "predicted_congestion_class": "HIGH",
        "cluster_id": None,
    }
    decision = engine.evaluate(ctx)
    assert decision["cluster_id"] is None
    assert decision["user_profile_adjustment"] == 0
    assert decision["final_priority"] == "LOW"
    assert decision["input_completeness"] == "PARTIAL"


# 10. Cluster adjustment
def test_cluster_adjustment() -> None:
    # Configure custom engine with explicit cluster policy (+1 for cluster 2, -1 for cluster 3)
    custom_engine = QoSPolicyEngine(
        cluster_adjustments={0: 0, 1: 0, 2: 1, 3: -1}
    )
    # WEB has base priority MEDIUM (2). Cluster 2 gives +1 -> HIGH (3)
    ctx_plus = {
        "device_id": "dev_cluster_2",
        "flow_id": "flow_adj_1",
        "traffic_class": "WEB",
        "predicted_congestion_class": "LOW",
        "cluster_id": 2,
    }
    dec_plus = custom_engine.evaluate(ctx_plus)
    assert dec_plus["base_priority"] == "MEDIUM"
    assert dec_plus["user_profile_adjustment"] == 1
    assert dec_plus["final_priority"] == "HIGH"
    assert "increased to HIGH" in dec_plus["policy_reason"]

    # WEB has base priority MEDIUM (2). Cluster 3 gives -1 -> NORMAL (1)
    ctx_minus = {
        "device_id": "dev_cluster_3",
        "flow_id": "flow_adj_2",
        "traffic_class": "WEB",
        "predicted_congestion_class": "LOW",
        "cluster_id": 3,
    }
    dec_minus = custom_engine.evaluate(ctx_minus)
    assert dec_minus["user_profile_adjustment"] == -1
    assert dec_minus["final_priority"] == "NORMAL"
    assert "decreased to NORMAL" in dec_minus["policy_reason"]


# 11. Priority clamping
def test_priority_clamping() -> None:
    # Test helper arithmetic
    high_plus_one, num = apply_priority_adjustment("HIGH", 2)
    assert high_plus_one == "HIGH"
    assert num == 3

    low_minus_one, num_low = apply_priority_adjustment("LOW", -2)
    assert low_minus_one == "LOW"
    assert num_low == 0

    # Test via policy engine with extreme adjustments
    extreme_engine = QoSPolicyEngine(cluster_adjustments={9: 5, 8: -5})
    # REAL_TIME is HIGH (3). Cluster 9 adds +5 -> clamped to HIGH (3)
    dec_high = extreme_engine.evaluate({
        "device_id": "h1",
        "flow_id": "flow_clamp_1",
        "traffic_class": "REAL_TIME",
        "predicted_congestion_class": "HIGH",
        "cluster_id": 9,
    })
    assert dec_high["final_priority"] == "HIGH"

    # BULK_TRANSFER is LOW (0). Cluster 8 subtracts -5 -> clamped to LOW (0)
    dec_low = extreme_engine.evaluate({
        "device_id": "h2",
        "flow_id": "flow_clamp_2",
        "traffic_class": "BULK_TRANSFER",
        "predicted_congestion_class": "HIGH",
        "cluster_id": 8,
    })
    assert dec_low["final_priority"] == "LOW"


# 12. Rule priority / order
def test_rule_priority_order(engine: QoSPolicyEngine) -> None:
    # A specific HIGH congestion rule must override default base priority
    # BULK_TRANSFER normally has base LOW, but in HIGH congestion it matches specific rule
    dec_bulk_high = engine.evaluate({
        "device_id": "h1",
        "flow_id": "flow_order_1",
        "traffic_class": "BULK_TRANSFER",
        "predicted_congestion_class": "HIGH",
    })
    assert dec_bulk_high["policy_rule_id"] == "POLICY_BULK_HIGH_CONGESTION"

    # In LOW congestion, it hits the general LOW congestion rule
    dec_bulk_low = engine.evaluate({
        "device_id": "h1",
        "flow_id": "flow_order_2",
        "traffic_class": "BULK_TRANSFER",
        "predicted_congestion_class": "LOW",
    })
    assert dec_bulk_low["policy_rule_id"] == "POLICY_LOW_CONGESTION_BASE"


# 13. Deterministic output
def test_deterministic_output(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h1",
        "flow_id": "flow_repeat",
        "traffic_class": "INTERACTIVE",
        "predicted_congestion_class": "HIGH",
        "cluster_id": 1,
    }
    first_dec = engine.evaluate(ctx)
    for _ in range(10):
        re_dec = engine.evaluate(ctx)
        assert re_dec == first_dec


# 14. Reason generation
def test_reason_generation(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h1",
        "flow_id": "flow_reason",
        "traffic_class": "REAL_TIME",
        "predicted_congestion_class": "HIGH",
        "cluster_id": 1,
    }
    decision = engine.evaluate(ctx)
    assert decision["policy_reason"]
    assert len(decision["policy_reason"]) > 10
    assert "REAL_TIME" in decision["policy_reason"]
    assert "HIGH" in decision["policy_reason"]


# 15. Rule ID generation
def test_rule_id_generation(engine: QoSPolicyEngine) -> None:
    ctx = {
        "device_id": "h1",
        "flow_id": "flow_rule_id",
        "traffic_class": "DNS",
        "predicted_congestion_class": "HIGH",
        "cluster_id": 0,
    }
    decision = engine.evaluate(ctx)
    assert decision["policy_rule_id"] == "POLICY_DNS_HIGH_CONGESTION"


# 16. Input validation
def test_input_validation(engine: QoSPolicyEngine) -> None:
    # Context must be a dictionary
    with pytest.raises(ValueError, match="Input validation error"):
        engine.evaluate("not_a_dictionary")  # type: ignore

    # Numerical score conversion to congestion class
    score_ctx = {
        "device_id": "h1",
        "flow_id": "flow_score_test",
        "traffic_class": "WEB",
        "predicted_congestion_score": 0.85,  # Should resolve to HIGH
        "cluster_id": 0,
    }
    dec_score = engine.evaluate(score_ctx)
    assert dec_score["predicted_congestion_class"] == "HIGH"
    assert dec_score["final_priority"] == "MEDIUM"  # WEB in HIGH congestion -> MEDIUM

    # Invalid priority label in priority_to_numeric raises ValueError
    with pytest.raises(ValueError, match="Invalid priority label"):
        priority_to_numeric("ULTRA_HIGH")
