"""
Unit and integration tests for C Network Monitoring Agent (Phase 4).
"""
import subprocess
import os
import csv
import pytest

BIN_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../bin/monitor_agent"))
AGENT_LOCAL_BIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../network/agent/monitor_agent"))

def test_monitor_agent_binary_exists():
    # Build if not already present
    if not os.path.exists(BIN_PATH):
        subprocess.run(["make", "all"], check=True)
    assert os.path.exists(BIN_PATH), "bin/monitor_agent binary must exist"

def test_monitor_agent_help_flag():
    result = subprocess.run([BIN_PATH, "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "--interval" in result.stdout
    assert "--host" in result.stdout

def test_monitor_agent_device_id_and_csv_generation(tmp_path):
    csv_file = str(tmp_path / "test_agent_metrics.csv")
    result = subprocess.run(
        [BIN_PATH, "h1", "--interval", "0.2", "--count", "2", "--output", csv_file],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Device ID       : h1" in result.stdout
    assert "Flow:" in result.stdout
    assert "Active Connections:" in result.stdout

    # Verify CSV file creation and column headers
    assert os.path.exists(csv_file)
    with open(csv_file, "r") as f:
        reader = csv.reader(f)
        header = next(reader)
        expected_header = [
            "timestamp", "device_id", "src_ip", "dst_ip", "src_port",
            "dst_port", "protocol", "throughput", "rtt", "packet_loss",
            "active_connections"
        ]
        assert header == expected_header

        rows = list(reader)
        assert len(rows) >= 2
        for r in rows:
            assert r[1] == "h1"
            assert r[6] in ["TCP", "UDP"]

def test_multiple_hosts_tagging(tmp_path):
    csv_file = str(tmp_path / "multi_hosts.csv")
    # Run for h2
    res2 = subprocess.run([BIN_PATH, "--host", "h2", "--interval", "0.2", "--count", "1", "--output", csv_file], capture_output=True, text=True)
    assert res2.returncode == 0

    # Run for h3
    res3 = subprocess.run([BIN_PATH, "--host", "h3", "--interval", "0.2", "--count", "1", "--output", csv_file], capture_output=True, text=True)
    assert res3.returncode == 0

    with open(csv_file, "r") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
        device_ids = {r[1] for r in rows}
        assert "h2" in device_ids
        assert "h3" in device_ids

def test_invalid_interval_error():
    result = subprocess.run([BIN_PATH, "h1", "--interval", "-1"], capture_output=True, text=True)
    assert result.returncode != 0
