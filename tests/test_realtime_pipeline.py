"""Unit and Integration Tests for Real-Time Packet Capture and ML Pipeline.

Tests:
1. Packet Normalization (TCP, UDP, ICMP, missing fields, zero synthetic data)
2. Flow Aggregation (5-tuple grouping, packet/byte metrics, rate estimation, idle timeout)
3. Model Inference (Traffic Classification, K-Means Profiling, GRU Congestion Forecasting)
4. QoS Policy Synthesis and Decision Traces
5. RealTimePipelineManager End-to-End Execution
6. Flask REST API Live Pipeline Endpoints
"""

import time
import pytest
from ml.realtime.packet_normalizer import PacketNormalizer, NormalizedPacket
from ml.realtime.flow_aggregator import RealTimeFlowAggregator, AggregatedFlow
from ml.realtime.model_runner import RealTimeModelRunner
from ml.realtime.pipeline_manager import RealTimePipelineManager
from backend.app import create_app


# ── 1. Packet Normalization Tests ─────────────────────────────────────────────

def test_packet_normalization_tcp():
    norm = PacketNormalizer()
    raw_tcp = {
        "timestamp": "2026-10-14 18:00:00",
        "interface": "eth0",
        "protocol": "TCP",
        "src_ip": "192.168.1.10",
        "dst_ip": "192.168.1.11",
        "src_port": 50222,
        "dst_port": 443,
        "packet_len": 1500,
        "payload_len": 1460,
        "tcp_flags": ["SYN", "ACK"],
        "tcp_flags_str": "SA",
        "window_size": 65535,
        "ttl": 64,
    }
    pkt = norm.normalize(raw_tcp)
    assert isinstance(pkt, NormalizedPacket)
    assert pkt.protocol == "TCP"
    assert pkt.src_port == 50222
    assert pkt.dst_port == 443
    assert "SYN" in pkt.tcp_flags
    assert pkt.packet_len == 1500


def test_packet_normalization_missing_fields():
    norm = PacketNormalizer()
    minimal = {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2"}
    pkt = norm.normalize(minimal)
    assert pkt.protocol == "OTHER"
    assert pkt.src_port == 0
    assert pkt.dst_port == 0
    assert pkt.packet_len == 0
    assert pkt.tcp_flags == []


# ── 2. Flow Aggregation Tests ─────────────────────────────────────────────────

def test_flow_aggregation_grouping_and_rates():
    aggregator = RealTimeFlowAggregator(idle_timeout_seconds=5.0, update_interval_seconds=0.1)
    norm = PacketNormalizer()

    t0 = time.time()
    for i in range(5):
        pkt = norm.normalize({
            "timestamp": t0 + i * 0.05,
            "epoch_timestamp": t0 + i * 0.05,
            "src_ip": "192.168.1.10",
            "dst_ip": "192.168.1.11",
            "src_port": 50100,
            "dst_port": 80,
            "protocol": "TCP",
            "packet_len": 1000,
            "payload_len": 960,
        })
        aggregator.add_packet(pkt)

    flows = aggregator.get_active_flows()
    assert len(flows) == 1
    flow = flows[0]
    assert flow.packet_count == 5
    assert flow.byte_count == 5000
    assert flow.device_id == "h1"
    assert flow.throughput_mbps > 0.0


def test_flow_aggregation_idle_eviction():
    aggregator = RealTimeFlowAggregator(idle_timeout_seconds=2.0)
    norm = PacketNormalizer()
    t0 = 1000.0

    pkt = norm.normalize({
        "epoch_timestamp": t0,
        "src_ip": "192.168.1.10",
        "dst_ip": "192.168.1.11",
        "src_port": 1234,
        "dst_port": 80,
        "protocol": "TCP",
        "packet_len": 500,
    })
    aggregator.add_packet(pkt)
    assert len(aggregator.get_active_flows()) == 1

    # Before timeout
    evicted = aggregator.prune_idle_flows(now=t0 + 1.5)
    assert len(evicted) == 0
    assert len(aggregator.get_active_flows()) == 1

    # After timeout
    evicted = aggregator.prune_idle_flows(now=t0 + 2.5)
    assert len(evicted) == 1
    assert len(aggregator.get_active_flows()) == 0


# ── 3. Model Runner Inference Tests ──────────────────────────────────────────

def test_model_runner_all_stages():
    runner = RealTimeModelRunner()
    flow = AggregatedFlow(
        flow_key=("192.168.1.10", "192.168.1.11", 50123, 443, "TCP"),
        flow_id="h1_192.168.1.10:50123->192.168.1.11:443_TCP",
        device_id="h1",
        src_ip="192.168.1.10",
        dst_ip="192.168.1.11",
        src_port=50123,
        dst_port=443,
        protocol="TCP",
        first_seen=time.time() - 2.0,
        last_seen=time.time(),
        start_time_iso="2026-10-14T18:00:00Z",
        last_time_iso="2026-10-14T18:00:02Z",
        packet_count=100,
        byte_count=150000,
        throughput_mbps=25.0,
        rtt_ms=12.5,
        packet_loss_percent=0.2,
        active_connections=4,
    )

    trace = runner.process_flow(flow)

    assert "trace_id" in trace
    assert trace["flow_id"] == flow.flow_id
    assert trace["traffic_classification"]["traffic_class"] == "WEB"
    assert trace["traffic_classification"]["confidence"] >= 0.5
    assert trace["user_profiling"]["cluster_id"] in (0, 1, 2)
    assert 0.0 <= trace["congestion_forecast"]["predicted_congestion_score"] <= 1.0
    assert trace["congestion_forecast"]["predicted_congestion_class"] in ("LOW", "MEDIUM", "HIGH")
    assert trace["qos_decision"]["final_priority"] in ("LOW", "NORMAL", "MEDIUM", "HIGH")
    assert "RECOMMENDED" in trace["qos_decision"]["os_enforcement_status"]


# ── 4. RealTimePipelineManager End-to-End Tests ──────────────────────────────

def test_pipeline_manager_end_to_end():
    mgr = RealTimePipelineManager(max_buffer=50)
    mgr.start()
    try:
        # Enqueue packets
        raw_packets = [
            {
                "src_ip": "192.168.1.10",
                "dst_ip": "192.168.1.11",
                "src_port": 50000 + i,
                "dst_port": 53,
                "protocol": "UDP",
                "packet_len": 120,
                "payload_len": 90,
            }
            for i in range(10)
        ]
        for p in raw_packets:
            mgr.enqueue_packet(p)

        # Allow worker thread to process
        time.sleep(0.5)

        status = mgr.get_status()
        assert status["is_running"] is True
        assert status["total_packets_received"] == 10

        flows, total_flows = mgr.get_live_flows(limit=10)
        assert total_flows >= 1

        preds, total_preds = mgr.get_live_predictions(limit=10)
        assert total_preds >= 1
        assert preds[0]["traffic_class"] == "DNS"

        traces, total_traces = mgr.get_live_traces(limit=10)
        assert total_traces >= 1
    finally:
        mgr.stop()


# ── 5. REST API Pipeline Endpoints ───────────────────────────────────────────

def test_api_live_pipeline_endpoints():
    app = create_app()
    client = app.test_client()

    # 1. Pipeline status
    res = client.get("/api/live/pipeline/status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] in ("STOPPED", "RUNNING", "success")
    assert "total_packets_received" in data

    # 2. Pipeline flows
    res = client.get("/api/live/pipeline/flows?limit=5")
    assert res.status_code == 200
    json_data = res.get_json()
    assert "data" in json_data
    assert "total" in json_data

    # 3. Pipeline predictions
    res = client.get("/api/live/pipeline/predictions?limit=5")
    assert res.status_code == 200

    # 4. Pipeline traces
    res = client.get("/api/live/pipeline/traces?limit=5")
    assert res.status_code == 200

    # 5. Clear pipeline
    res = client.post("/api/live/pipeline/clear")
    assert res.status_code == 200

    # 6. Monitoring flows with source=live
    res = client.get("/api/monitoring/flows?source=live&limit=5")
    assert res.status_code == 200
