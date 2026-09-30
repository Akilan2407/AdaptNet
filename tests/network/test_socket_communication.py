"""
Automated unit & integration tests for Phase 5: C Socket Communication Module.
"""
import subprocess
import os
import time
import socket
import csv
import pytest

CONTROLLER_BIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../bin/network_controller"))
AGENT_BIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../bin/monitor_agent"))

@pytest.fixture(scope="module", autouse=True)
def ensure_binaries_built():
    if not (os.path.exists(CONTROLLER_BIN) and os.path.exists(AGENT_BIN)):
        subprocess.run(["make", "all"], check=True)
    assert os.path.exists(CONTROLLER_BIN)
    assert os.path.exists(AGENT_BIN)

def wait_for_server_ready(port, max_retries=20, delay=0.1):
    for _ in range(max_retries):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("127.0.0.1", port))
            return s
        except ConnectionRefusedError:
            time.sleep(delay)
    raise ConnectionRefusedError(f"Could not connect to port {port}")


def test_controller_help_flag():
    res = subprocess.run([CONTROLLER_BIN, "--help"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "Usage:" in res.stdout
    assert "--port" in res.stdout
    assert "--bind" in res.stdout

def test_single_agent_to_controller_socket_stream(tmp_path):
    port = 5401
    csv_file = str(tmp_path / "controller_received.csv")

    # Start controller process
    controller_proc = subprocess.Popen(
        [CONTROLLER_BIN, "--port", str(port), "--output", csv_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        s = wait_for_server_ready(port)
        s.close()

        # Run agent on h1 sending 2 samples with 1.0s interval
        agent_res = subprocess.run(
            [AGENT_BIN, "h1", "--server", "127.0.0.1", "--port", str(port), "--interval", "1.0", "--count", "2"],
            capture_output=True,
            text=True
        )
        assert agent_res.returncode == 0
        assert "Connected to controller" in agent_res.stdout
        assert "Streamed record to controller" in agent_res.stdout

        time.sleep(0.5) # Wait for flush

        # Verify controller received records in CSV
        assert os.path.exists(csv_file)
        with open(csv_file, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == [
                "timestamp", "device_id", "src_ip", "dst_ip", "src_port",
                "dst_port", "protocol", "throughput", "rtt", "packet_loss",
                "active_connections"
            ]
            rows = list(reader)
            assert len(rows) >= 2
            for r in rows:
                assert r[1] == "h1"
                assert r[6] in ["TCP", "UDP"]
    finally:
        controller_proc.terminate()
        controller_proc.wait(timeout=2)

def test_multi_agent_simultaneous_socket_stream(tmp_path):
    port = 5402
    csv_file = str(tmp_path / "multi_agents_received.csv")

    controller_proc = subprocess.Popen(
        [CONTROLLER_BIN, "--port", str(port), "--output", csv_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        time.sleep(0.3)

        # Spawn 5 agents concurrently (h1 to h5)
        agent_procs = []
        for host in ["h1", "h2", "h3", "h4", "h5"]:
            p = subprocess.Popen(
                [AGENT_BIN, host, "--server", "127.0.0.1", "--port", str(port), "--interval", "0.2", "--count", "2"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            agent_procs.append(p)

        for p in agent_procs:
            stdout, stderr = p.communicate(timeout=5)
            assert p.returncode == 0

        time.sleep(0.4)

        assert os.path.exists(csv_file)
        with open(csv_file, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
            device_ids = {r[1] for r in rows}
            assert {"h1", "h2", "h3", "h4", "h5"}.issubset(device_ids)
    finally:
        controller_proc.terminate()
        controller_proc.wait(timeout=2)

def test_agent_resilience_when_controller_unavailable(tmp_path):
    port = 5403
    # Start agent when controller is NOT running
    agent_res = subprocess.run(
        [AGENT_BIN, "h1", "--server", "127.0.0.1", "--port", str(port), "--interval", "0.2", "--count", "2"],
        capture_output=True,
        text=True
    )
    # Agent must not crash!
    assert agent_res.returncode == 0
    assert "Controller unavailable" in agent_res.stdout

def test_controller_malformed_record_handling(tmp_path):
    port = 5404
    csv_file = str(tmp_path / "malformed_test.csv")

    controller_proc = subprocess.Popen(
        [CONTROLLER_BIN, "--port", str(port), "--output", csv_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        time.sleep(0.3)
        # Send raw malformed strings directly
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", port))
        
        # Malformed packets: wrong field count, invalid protocol, invalid port
        s.sendall(b"this|is|a|bad|line\n")
        s.sendall(b"2026-09-12 15:20:01|h1|10.0.0.1|10.0.0.2|999999|5201|INVALID_PROTO|12.45|N/A|N/A|1\n")
        
        # Valid packet
        s.sendall(b"2026-09-12 15:20:01|h1|192.168.1.10|192.168.1.11|45120|5201|TCP|12.45|2.31|N/A|1\n")
        time.sleep(0.2)
        s.close()

        time.sleep(0.3)

        # Verify only the valid record was committed to CSV
        assert os.path.exists(csv_file)
        with open(csv_file, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0][1] == "h1"
            assert rows[0][6] == "TCP"
    finally:
        controller_proc.terminate()
        controller_proc.wait(timeout=2)
