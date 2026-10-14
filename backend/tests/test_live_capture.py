"""
Unit and integration tests for Live Packet Capture backend service and REST endpoints.
"""

import time
import pytest
from flask.testing import FlaskClient

from backend.app import create_app
from backend.services.live_capture_service import LiveCaptureService
from network.agent.packet_sniffer import (
    CapturedPacket,
    IPv4Header,
    TCPHeader,
    UDPHeader,
    ICMPHeader,
)


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def capture_service():
    # Fresh isolated service instance with small buffer for testing
    return LiveCaptureService(max_buffer=5)


def create_mock_tcp_packet(seq_num: int = 100, flags_syn: bool = True, flags_ack: bool = False) -> CapturedPacket:
    tcp_hdr = TCPHeader(
        src_port=54321,
        dst_port=80,
        seq_num=seq_num,
        ack_num=0,
        data_offset=5,
        flags=2 if flags_syn else 16,
        window_size=65535,
        checksum=0,
        urgent_ptr=0,
        flag_syn=flags_syn,
        flag_ack=flags_ack,
    )
    ip_hdr = IPv4Header(
        version=4,
        ihl=5,
        dscp=0,
        ecn=0,
        total_length=60,
        identification=1234,
        flags=2,
        fragment_offset=0,
        ttl=64,
        protocol=6,
        checksum=0,
        src_ip="192.168.1.10",
        dst_ip="192.168.1.1",
        header_len_bytes=20,
    )
    return CapturedPacket(
        timestamp=time.monotonic(),
        capture_timestamp="2026-10-14 12:00:00",
        iface="test0",
        ip=ip_hdr,
        tcp=tcp_hdr,
        payload_len=0,
        protocol_name="TCP",
        src_ip="192.168.1.10",
        dst_ip="192.168.1.1",
        src_port=54321,
        dst_port=80,
        packet_len=60,
    )


def create_mock_udp_packet() -> CapturedPacket:
    udp_hdr = UDPHeader(src_port=5004, dst_port=5004, length=32, checksum=0)
    ip_hdr = IPv4Header(
        version=4, ihl=5, dscp=0, ecn=0, total_length=52,
        identification=2345, flags=0, fragment_offset=0, ttl=64,
        protocol=17, checksum=0, src_ip="192.168.1.12", dst_ip="192.168.1.14",
        header_len_bytes=20,
    )
    return CapturedPacket(
        timestamp=time.monotonic(),
        capture_timestamp="2026-10-14 12:00:01",
        iface="test0",
        ip=ip_hdr,
        udp=udp_hdr,
        payload_len=24,
        protocol_name="UDP",
        src_ip="192.168.1.12",
        dst_ip="192.168.1.14",
        src_port=5004,
        dst_port=5004,
        packet_len=52,
    )


def test_packet_event_formatting(capture_service):
    pkt = create_mock_tcp_packet(seq_num=101, flags_syn=True, flags_ack=True)
    capture_service._on_packet_arrived(pkt)

    stats = capture_service.get_stats()
    assert stats["total_captured"] == 1
    assert stats["tcp_count"] == 1
    assert stats["udp_count"] == 0

    packets, total = capture_service.get_packets()
    assert total == 1
    p = packets[0]
    assert p["protocol"] == "TCP"
    assert p["src_ip"] == "192.168.1.10"
    assert p["dst_ip"] == "192.168.1.1"
    assert p["src_port"] == 54321
    assert p["dst_port"] == 80
    assert "SYN" in p["tcp_flags"]
    assert "ACK" in p["tcp_flags"]
    assert p["packet_len"] == 60


def test_buffer_bounding_and_ordering(capture_service):
    # Max buffer is 5
    for i in range(8):
        pkt = create_mock_tcp_packet(seq_num=i)
        pkt.src_port = 5000 + i
        capture_service._on_packet_arrived(pkt)

    stats = capture_service.get_stats()
    assert stats["total_captured"] == 8
    assert stats["buffer_size"] == 5  # capped at max_buffer

    packets, total = capture_service.get_packets(limit=10)
    assert total == 5
    assert len(packets) == 5
    # Should be newest first: seq_num 7, 6, 5, 4, 3
    assert packets[0]["src_port"] == 5007
    assert packets[4]["src_port"] == 5003


def test_protocol_and_query_filtering(capture_service):
    capture_service._on_packet_arrived(create_mock_tcp_packet())
    capture_service._on_packet_arrived(create_mock_udp_packet())

    # Filter TCP
    tcp_pkts, tcp_total = capture_service.get_packets(protocol="TCP")
    assert tcp_total == 1
    assert tcp_pkts[0]["protocol"] == "TCP"

    # Filter UDP
    udp_pkts, udp_total = capture_service.get_packets(protocol="UDP")
    assert udp_total == 1
    assert udp_pkts[0]["protocol"] == "UDP"

    # Query IP
    ip_pkts, ip_total = capture_service.get_packets(ip_query="192.168.1.12")
    assert ip_total == 1
    assert ip_pkts[0]["src_ip"] == "192.168.1.12"


def test_api_live_stats_endpoint(client: FlaskClient):
    res = client.get("/api/live/stats")
    assert res.status_code == 200
    stats = res.get_json()
    assert "status" in stats
    assert "total_captured" in stats
    assert "tcp_count" in stats
    assert "udp_count" in stats
    assert stats["source"] == "live_wire_capture"


def test_api_live_packets_endpoint(client: FlaskClient):
    res = client.get("/api/live/packets?limit=10")
    assert res.status_code == 200
    data = res.get_json()
    assert "data" in data
    assert "total" in data
    assert data["source"] == "live_wire_capture"


def test_api_live_interfaces_endpoint(client: FlaskClient):
    res = client.get("/api/live/interfaces")
    assert res.status_code == 200
    data = res.get_json()
    assert "interfaces" in data
    assert len(data["interfaces"]) >= 1


def test_api_clear_buffer(client: FlaskClient):
    res = client.post("/api/live/clear")
    assert res.status_code == 200
    data = res.get_json()
    assert data["stats"]["buffer_size"] == 0
