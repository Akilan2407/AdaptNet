"""Unit tests for Phase 14 Adaptive Traffic Control Module.

Verifies:
1. Priority mapping (LOW -> 1:40, NORMAL -> 1:30, MEDIUM -> 1:20, HIGH -> 1:10)
2. Input validation: invalid IP rejection
3. Input validation: invalid port rejection
4. Input validation: invalid protocol rejection
5. Input validation: invalid priority rejection
6. Input validation: unknown device rejection
7. Input validation: unknown interface rejection
8. DRY_RUN mode safety guarantee
9. Duplicate rule prevention
10. Dynamic policy updates (HIGH -> MEDIUM, MEDIUM -> LOW, LOW -> HIGH)
11. Rollback operation
12. Failure handling
13. Determinism guarantee
14. Incomplete input fallback
15. Flow 5-tuple parsing
16. State table tracking
"""

from pathlib import Path
import sys
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.control.config import PRIORITY_TO_CLASS
from ml.control.control_validator import ControlValidator
from ml.control.decision_loader import DecisionLoader
from ml.control.dry_run import DryRunExecutor


@pytest.fixture
def executor():
    return DryRunExecutor()


# 1. Priority mapping
def test_priority_mapping():
    assert PRIORITY_TO_CLASS["LOW"] == "1:40"
    assert PRIORITY_TO_CLASS["NORMAL"] == "1:30"
    assert PRIORITY_TO_CLASS["MEDIUM"] == "1:20"
    assert PRIORITY_TO_CLASS["HIGH"] == "1:10"


# 2. Input validation: invalid IP
def test_invalid_ip_rejection():
    assert not ControlValidator.validate_ip("999.999.999.999")
    assert not ControlValidator.validate_ip("not_an_ip")
    assert not ControlValidator.validate_ip("192.168.1.300")
    assert ControlValidator.validate_ip("192.168.1.10")


# 3. Input validation: invalid port
def test_invalid_port_rejection():
    assert not ControlValidator.validate_port(0)
    assert not ControlValidator.validate_port(70000)
    assert not ControlValidator.validate_port("invalid")
    assert ControlValidator.validate_port(5201)
    assert ControlValidator.validate_port(80)


# 4. Input validation: invalid protocol
def test_invalid_protocol_rejection():
    assert not ControlValidator.validate_protocol("ICMP")
    assert not ControlValidator.validate_protocol("IGMP")
    assert ControlValidator.validate_protocol("TCP")
    assert ControlValidator.validate_protocol("UDP")


# 5. Input validation: invalid priority
def test_invalid_priority_rejection():
    assert not ControlValidator.validate_priority("CRITICAL")
    assert not ControlValidator.validate_priority("BEST_EFFORT")
    assert ControlValidator.validate_priority("HIGH")
    assert ControlValidator.validate_priority("LOW")


# 6. Input validation: unknown device
def test_unknown_device_rejection():
    assert not ControlValidator.validate_device("rogue_host")
    assert not ControlValidator.validate_device("h99")
    assert ControlValidator.validate_device("h1")


# 7. Input validation: unknown interface
def test_unknown_interface_rejection():
    assert not ControlValidator.validate_interface("eth99")
    assert not ControlValidator.validate_interface("wlan0")
    assert ControlValidator.validate_interface("s1-eth1")
    assert ControlValidator.validate_interface("lo")


# 8. DRY_RUN mode safety guarantee
def test_dry_run_safety(executor):
    intent = {
        "device_id": "h1",
        "flow_id": "flow_test_1",
        "src_ip": "192.168.1.10",
        "dst_ip": "192.168.1.11",
        "src_port": 45672,
        "dst_port": 5201,
        "protocol": "TCP",
        "final_priority": "LOW",
        "interface": "s1-eth1",
        "is_fallback": False,
    }
    result = executor.process_intent(intent)
    assert result["status"] == "DRY_RUN"
    assert result["action"] == "APPLY"
    assert "tc filter add dev s1-eth1" in result["command"]
    assert "flowid 1:40" in result["command"]


# 9. Duplicate rule prevention
def test_duplicate_rule_prevention(executor):
    intent = {
        "device_id": "h1",
        "flow_id": "flow_test_dup",
        "src_ip": "192.168.1.10",
        "dst_ip": "192.168.1.11",
        "src_port": 45672,
        "dst_port": 5201,
        "protocol": "TCP",
        "final_priority": "MEDIUM",
        "interface": "s1-eth1",
        "is_fallback": False,
    }
    res1 = executor.process_intent(intent)
    assert res1["status"] == "DRY_RUN"
    assert res1["action"] == "APPLY"

    # Second identical intent
    res2 = executor.process_intent(intent)
    assert res2["status"] == "SKIPPED"
    assert "Identical rule already active" in res2["error_message"]


# 10. Dynamic policy updates
def test_dynamic_policy_updates(executor):
    intent = {
        "device_id": "h2",
        "flow_id": "flow_dyn_1",
        "src_ip": "192.168.1.11",
        "dst_ip": "192.168.1.12",
        "src_port": 50000,
        "dst_port": 5201,
        "protocol": "TCP",
        "final_priority": "HIGH",
        "interface": "s1-eth2",
        "is_fallback": False,
    }
    # Initial HIGH
    res_high = executor.process_intent(intent)
    assert res_high["action"] == "APPLY"
    assert res_high["target_class"] == "1:10"

    # Update to MEDIUM
    intent["final_priority"] = "MEDIUM"
    res_med = executor.process_intent(intent)
    assert res_med["action"] == "UPDATE"
    assert res_med["target_class"] == "1:20"
    assert "tc filter change" in res_med["command"]

    # Update to LOW
    intent["final_priority"] = "LOW"
    res_low = executor.process_intent(intent)
    assert res_low["action"] == "UPDATE"
    assert res_low["target_class"] == "1:40"


# 11. Rollback operation
def test_rollback(executor):
    intent = {
        "device_id": "h3",
        "flow_id": "flow_rb_1",
        "src_ip": "192.168.1.12",
        "dst_ip": "192.168.1.13",
        "src_port": 50001,
        "dst_port": 5201,
        "protocol": "TCP",
        "final_priority": "LOW",
        "interface": "s1-eth3",
        "is_fallback": False,
    }
    executor.process_intent(intent)
    assert len(executor.active_rules) == 1

    rb_results = executor.rollback()
    assert len(rb_results) == 1
    assert rb_results[0]["action"] == "RESET"
    assert "tc qdisc del dev s1-eth3 root" in rb_results[0]["command"]
    assert len(executor.active_rules) == 0


# 12. Failure handling
def test_failure_handling(executor):
    invalid_intent = {
        "device_id": "h1",
        "flow_id": "flow_fail_1",
        "src_ip": "999.999.999.999",  # Invalid IP
        "dst_ip": "192.168.1.11",
        "src_port": 45672,
        "dst_port": 5201,
        "protocol": "TCP",
        "final_priority": "LOW",
        "interface": "s1-eth1",
        "is_fallback": False,
    }
    result = executor.process_intent(invalid_intent)
    assert result["status"] == "FAILED"
    assert "Invalid source IP" in result["error_message"]


# 13. Determinism guarantee
def test_determinism(executor):
    intent = {
        "device_id": "h4",
        "flow_id": "flow_det_1",
        "src_ip": "192.168.1.13",
        "dst_ip": "192.168.1.14",
        "src_port": 50002,
        "dst_port": 5201,
        "protocol": "TCP",
        "final_priority": "NORMAL",
        "interface": "s1-eth4",
        "is_fallback": False,
    }
    res1 = executor.process_intent(intent)
    cmd1 = res1["command"]
    executor.rollback()

    res2 = executor.process_intent(intent)
    cmd2 = res2["command"]
    assert cmd1 == cmd2


# 14. Incomplete input fallback
def test_incomplete_input_fallback(executor):
    partial_intent = {
        "device_id": "h5",
        "flow_id": "flow_fallback_1",
        "src_ip": "192.168.1.14",
        "dst_ip": "192.168.1.10",
        "src_port": 50003,
        "dst_port": 5201,
        "protocol": "TCP",
        "final_priority": "LOW",
        "interface": "s1-eth5",
        "is_fallback": True,  # PARTIAL input
    }
    result = executor.process_intent(partial_intent)
    assert result["status"] == "SKIPPED"
    assert "PARTIAL" in result["error_message"]


# 15. Flow 5-tuple parsing
def test_flow_5tuple_parsing():
    flow_str = "h1_192.168.1.10:45672->192.168.1.11:5201_TCP"
    parsed = DecisionLoader.parse_flow_id(flow_str)
    assert parsed is not None
    assert parsed["device_id"] == "h1"
    assert parsed["src_ip"] == "192.168.1.10"
    assert parsed["src_port"] == 45672
    assert parsed["dst_ip"] == "192.168.1.11"
    assert parsed["dst_port"] == 5201
    assert parsed["protocol"] == "TCP"


# 16. State table tracking
def test_state_table_tracking(executor):
    intent = {
        "device_id": "h1",
        "flow_id": "flow_state_track",
        "src_ip": "192.168.1.10",
        "dst_ip": "192.168.1.11",
        "src_port": 45672,
        "dst_port": 5201,
        "protocol": "TCP",
        "final_priority": "HIGH",
        "interface": "s1-eth1",
        "is_fallback": False,
    }
    res = executor.process_intent(intent)
    assert res["status"] == "DRY_RUN"
    assert "flow_state_track" in executor.active_rules
    assert executor.active_rules["flow_state_track"]["target_class"] == "1:10"
