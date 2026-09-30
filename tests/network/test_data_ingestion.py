"""
Automated unit & integration tests for Phase 6: Network Data Ingestion Module.
"""
import subprocess
import os
import time
import socket
import json
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

def test_ingestion_valid_tcp_and_udp_records(tmp_path):
    port = 5501
    csv_file = str(tmp_path / "metrics.csv")
    jsonl_file = str(tmp_path / "metrics.jsonl")
    invalid_log = str(tmp_path / "invalid.log")

    controller_proc = subprocess.Popen(
        [CONTROLLER_BIN, "--port", str(port), "--output", csv_file, "--jsonl", jsonl_file, "--invalid-log", invalid_log],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        s = wait_for_server_ready(port)

        # 1. Valid TCP record
        s.sendall(b"2026-09-12 15:20:01|h1|192.168.1.10|192.168.1.11|45120|5201|TCP|12.45|2.31|N/A|1\n")
        # 2. Valid UDP record
        s.sendall(b"2026-09-12 15:20:02|h2|192.168.1.11|192.168.1.12|45672|5202|UDP|10.00|N/A|0.05|1\n")
        time.sleep(0.2)
        s.close()
        time.sleep(0.3)

        # Check CSV
        assert os.path.exists(csv_file)
        with open(csv_file, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == ["timestamp", "device_id", "src_ip", "dst_ip", "src_port", "dst_port", "protocol", "throughput", "rtt", "packet_loss", "active_connections"]
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0][1] == "h1" and rows[0][6] == "TCP"
            assert rows[1][1] == "h2" and rows[1][6] == "UDP"

        # Check JSONL
        assert os.path.exists(jsonl_file)
        with open(jsonl_file, "r") as f:
            lines = [json.loads(line) for line in f]
            assert len(lines) == 2
            assert lines[0]["device_id"] == "h1"
            assert lines[0]["protocol"] == "TCP"
            assert lines[0]["throughput"] == 12.45
            assert lines[0]["rtt"] == 2.31
            assert lines[0]["packet_loss"] is None

            assert lines[1]["device_id"] == "h2"
            assert lines[1]["protocol"] == "UDP"
            assert lines[1]["rtt"] is None
            assert lines[1]["packet_loss"] == 0.05
    finally:
        controller_proc.terminate()
        controller_proc.wait(timeout=2)

def test_ingestion_invalid_records_filtering(tmp_path):
    port = 5502
    csv_file = str(tmp_path / "metrics.csv")
    invalid_log = str(tmp_path / "invalid.log")

    controller_proc = subprocess.Popen(
        [CONTROLLER_BIN, "--port", str(port), "--output", csv_file, "--invalid-log", invalid_log],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        time.sleep(0.3)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", port))

        # 3. Missing fields (only 5 fields)
        s.sendall(b"2026-09-12 15:20:01|h1|192.168.1.10|192.168.1.11|5201\n")
        # 4. Invalid IP format
        s.sendall(b"2026-09-12 15:20:01|h1|999.999.999.999|192.168.1.11|45120|5201|TCP|12.45|N/A|N/A|1\n")
        # 5. Invalid Port (out of range)
        s.sendall(b"2026-09-12 15:20:01|h1|192.168.1.10|192.168.1.11|45120|99999|TCP|12.45|N/A|N/A|1\n")
        # 6. Invalid Protocol (HTTP)
        s.sendall(b"2026-09-12 15:20:01|h1|192.168.1.10|192.168.1.11|45120|5201|HTTP|12.45|N/A|N/A|1\n")
        # 7. Negative Throughput
        s.sendall(b"2026-09-12 15:20:01|h1|192.168.1.10|192.168.1.11|45120|5201|TCP|-5.00|N/A|N/A|1\n")
        # 8. Negative RTT
        s.sendall(b"2026-09-12 15:20:01|h1|192.168.1.10|192.168.1.11|45120|5201|TCP|12.45|-1.00|N/A|1\n")
        # 9. Invalid Packet Loss (> 100%)
        s.sendall(b"2026-09-12 15:20:01|h1|192.168.1.10|192.168.1.11|45120|5201|TCP|12.45|N/A|150.0|1\n")
        # One valid record
        s.sendall(b"2026-09-12 15:20:01|h1|192.168.1.10|192.168.1.11|45120|5201|TCP|12.45|N/A|N/A|1\n")

        time.sleep(0.3)
        s.close()
        time.sleep(0.3)

        # Verify only 1 record entered valid CSV
        with open(csv_file, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
            assert len(rows) == 1

        # Verify all 7 invalid records logged to invalid.log
        assert os.path.exists(invalid_log)
        with open(invalid_log, "r") as f:
            log_content = f.read()
            assert "REJECTED" in log_content
            assert "Invalid field count" in log_content
            assert "Invalid source IP" in log_content
            assert "Invalid destination port" in log_content
            assert "Invalid protocol" in log_content
            assert "Negative throughput" in log_content
            assert "Negative RTT" in log_content
            assert "Invalid packet loss" in log_content
    finally:
        controller_proc.terminate()
        controller_proc.wait(timeout=2)

def test_ingestion_duplicate_detection(tmp_path):
    port = 5503
    csv_file = str(tmp_path / "metrics.csv")
    invalid_log = str(tmp_path / "invalid.log")

    controller_proc = subprocess.Popen(
        [CONTROLLER_BIN, "--port", str(port), "--output", csv_file, "--invalid-log", invalid_log],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        time.sleep(0.3)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", port))

        # 10. Send identical record twice
        record = b"2026-09-12 15:20:01|h1|192.168.1.10|192.168.1.11|45120|5201|TCP|12.45|2.31|N/A|1\n"
        s.sendall(record)
        s.sendall(record) # duplicate!
        time.sleep(0.2)
        s.close()
        time.sleep(0.3)

        # CSV must contain only 1 instance
        with open(csv_file, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
            assert len(rows) == 1

        # Duplicate logged in invalid log
        with open(invalid_log, "r") as f:
            log_content = f.read()
            assert "Duplicate record detected" in log_content
    finally:
        controller_proc.terminate()
        controller_proc.wait(timeout=2)

def test_ingestion_ring_buffer_and_multi_device(tmp_path):
    port = 5504
    csv_file = str(tmp_path / "metrics.csv")

    # Buffer capacity of 5 records
    controller_proc = subprocess.Popen(
        [CONTROLLER_BIN, "--port", str(port), "--buffer-size", "5", "--output", csv_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    try:
        time.sleep(0.3)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", port))

        # Send 10 distinct records across 3 devices (h1, h2, h3)
        for i in range(10):
            host = f"h{(i % 3) + 1}"
            rec = f"2026-09-12 15:20:{i:02d}|{host}|192.168.1.{10+i}|192.168.1.20|{40000+i}|5201|TCP|{10.0+i}|N/A|N/A|1\n"
            s.sendall(rec.encode())

        time.sleep(0.3)
        s.close()
        time.sleep(0.3)

        # All 10 records are in CSV
        with open(csv_file, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
            assert len(rows) == 10
            devices = {r[1] for r in rows}
            assert devices == {"h1", "h2", "h3"}
    finally:
        controller_proc.terminate()
        controller_proc.wait(timeout=2)
