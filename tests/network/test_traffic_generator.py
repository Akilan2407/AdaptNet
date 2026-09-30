"""
Unit tests for Traffic Generation Module (Phase 3).
"""
import os
import pytest
from network.traffic.config import FlowConfig, get_default_host_ip
from network.traffic.traffic_scenarios import (
    get_scenario_flows,
    build_scenario_tcp,
    build_scenario_udp,
    build_scenario_multi_tcp,
    build_scenario_multi_udp,
    build_scenario_mixed,
    build_scenario_congestion
)
from network.traffic.traffic_generator import TrafficGenerator

def test_flow_validation():
    valid_flow = FlowConfig("f1", "h1", "h2", "tcp", duration=10, port=5201)
    assert valid_flow.validate() is True

    invalid_proto = FlowConfig("f2", "h1", "h2", "icmp")
    with pytest.raises(ValueError, match="Invalid protocol"):
        invalid_proto.validate()

    invalid_duration = FlowConfig("f3", "h1", "h2", "tcp", duration=-5)
    with pytest.raises(ValueError, match="Duration must be positive"):
        invalid_duration.validate()

    invalid_port = FlowConfig("f4", "h1", "h2", "tcp", port=80)
    with pytest.raises(ValueError, match="Port must be between 1024 and 65535"):
        invalid_port.validate()

def test_host_ip_resolution():
    assert get_default_host_ip("h1") == "192.168.1.10"
    assert get_default_host_ip("h2") == "192.168.1.11"
    assert get_default_host_ip("h10") == "192.168.1.19"

    with pytest.raises(ValueError, match="Invalid host name format"):
        get_default_host_ip("invalid_host")

def test_all_scenarios_build():
    tcp_flows = get_scenario_flows("tcp", duration=5)
    assert len(tcp_flows) == 1
    assert tcp_flows[0].protocol == "tcp"

    udp_flows = get_scenario_flows("udp", duration=5, bandwidth="20M")
    assert len(udp_flows) == 1
    assert udp_flows[0].protocol == "udp"
    assert udp_flows[0].bandwidth == "20M"

    multi_tcp = get_scenario_flows("multi_tcp")
    assert len(multi_tcp) == 3

    multi_udp = get_scenario_flows("multi_udp")
    assert len(multi_udp) == 3

    mixed = get_scenario_flows("mixed")
    assert len(mixed) == 4
    protos = {f.protocol for f in mixed}
    assert "tcp" in protos and "udp" in protos

    congestion = get_scenario_flows("congestion")
    assert len(congestion) == 4

def test_traffic_generator_run(tmp_path):
    log_dir = str(tmp_path / "traffic_logs")
    generator = TrafficGenerator(log_dir=log_dir, dry_run=True)

    flows = build_scenario_mixed(duration=1)
    results = generator.run_scenario(flows, scenario_name="test_mixed")

    assert len(results) == len(flows)
    for r in results:
        assert r["status"] == "completed"
        assert r["throughput_mbps"] > 0

    log_files = os.listdir(log_dir)
    assert any(f.endswith(".json") for f in log_files)
    assert any(f.endswith(".log") for f in log_files)
