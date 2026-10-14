"""Network Traffic Management Binary Protocol Definitions (converted from protocol.h)."""

from enum import IntEnum
import struct
from typing import Optional, Tuple


PROTOCOL_MAGIC: int = 0x4E544D31  # "NTM1" - Network Traffic Management v1
DEFAULT_AGENT_PORT: int = 9090
DEFAULT_CONTROLLER_PORT: int = 9091
MAX_HOST_ID_LEN: int = 64


class MessageType(IntEnum):
    """Message Types between Agent <-> Controller."""
    MSG_TYPE_HEARTBEAT = 0x01
    MSG_TYPE_METRICS_REPORT = 0x02
    MSG_TYPE_CONGESTION_ALERT = 0x03
    MSG_TYPE_POLICY_UPDATE = 0x04
    MSG_TYPE_ACK = 0x05
    MSG_TYPE_ERROR = 0xFF


class TrafficProtocol(IntEnum):
    """Monitored Protocol Classification."""
    TRAFFIC_PROTO_UNKNOWN = 0
    TRAFFIC_PROTO_TCP = 6
    TRAFFIC_PROTO_UDP = 17


# Packed binary struct format for packet header:
# uint32_t magic;           (4 bytes, '<I')
# uint16_t version;         (2 bytes, '<H')
# uint16_t msg_type;        (2 bytes, '<H')
# uint32_t payload_length;  (4 bytes, '<I')
# uint64_t timestamp_ms;    (8 bytes, '<Q')
# Total = 20 bytes
HEADER_STRUCT = struct.Struct("<IHHIQ")
HEADER_SIZE = HEADER_STRUCT.size  # 20 bytes


class PacketHeader:
    """Fixed-size Header for all TCP IPC Frames."""

    def __init__(
        self,
        magic: int = PROTOCOL_MAGIC,
        version: int = 1,
        msg_type: int = MessageType.MSG_TYPE_METRICS_REPORT,
        payload_length: int = 0,
        timestamp_ms: int = 0,
    ):
        self.magic = magic
        self.version = version
        self.msg_type = msg_type
        self.payload_length = payload_length
        self.timestamp_ms = timestamp_ms

    def pack(self) -> bytes:
        """Serialize header into packed binary bytes."""
        return HEADER_STRUCT.pack(
            self.magic,
            self.version,
            int(self.msg_type),
            self.payload_length,
            self.timestamp_ms,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "PacketHeader":
        """Deserialize packed binary bytes into PacketHeader."""
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Data length {len(data)} is less than header size {HEADER_SIZE}")
        magic, version, msg_type, payload_length, timestamp_ms = HEADER_STRUCT.unpack(data[:HEADER_SIZE])
        return cls(
            magic=magic,
            version=version,
            msg_type=msg_type,
            payload_length=payload_length,
            timestamp_ms=timestamp_ms,
        )


# Packed binary struct format for telemetry metric:
# char host_id[64];           (64s)
# uint32_t src_ip;            (I)
# uint32_t dst_ip;            (I)
# uint16_t src_port;          (H)
# uint16_t dst_port;          (H)
# uint8_t  protocol;          (B)
# uint64_t bytes_sent;        (Q)
# uint64_t bytes_received;    (Q)
# uint64_t packets_sent;      (Q)
# uint64_t packets_received;  (Q)
# float    rtt_ms;            (f)
# float    jitter_ms;         (f)
# float    packet_loss_rate;  (f)
# Total = 64 + 4 + 4 + 2 + 2 + 1 + 8 + 8 + 8 + 8 + 4 + 4 + 4 = 121 bytes
TELEMETRY_STRUCT = struct.Struct("<64sIIHHBQQQQfff")
TELEMETRY_SIZE = TELEMETRY_STRUCT.size  # 121 bytes


class TelemetryMetric:
    """Telemetry payload reported by monitoring agents."""

    def __init__(
        self,
        host_id: str = "",
        src_ip: int = 0,
        dst_ip: int = 0,
        src_port: int = 0,
        dst_port: int = 0,
        protocol: int = TrafficProtocol.TRAFFIC_PROTO_TCP,
        bytes_sent: int = 0,
        bytes_received: int = 0,
        packets_sent: int = 0,
        packets_received: int = 0,
        rtt_ms: float = 0.0,
        jitter_ms: float = 0.0,
        packet_loss_rate: float = 0.0,
    ):
        self.host_id = host_id
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.src_port = src_port
        self.dst_port = dst_port
        self.protocol = protocol
        self.bytes_sent = bytes_sent
        self.bytes_received = bytes_received
        self.packets_sent = packets_sent
        self.packets_received = packets_received
        self.rtt_ms = rtt_ms
        self.jitter_ms = jitter_ms
        self.packet_loss_rate = packet_loss_rate

    def pack(self) -> bytes:
        """Serialize telemetry metric into packed binary bytes."""
        host_id_bytes = self.host_id.encode("utf-8")[:MAX_HOST_ID_LEN].ljust(MAX_HOST_ID_LEN, b"\x00")
        return TELEMETRY_STRUCT.pack(
            host_id_bytes,
            self.src_ip,
            self.dst_ip,
            self.src_port,
            self.dst_port,
            int(self.protocol),
            self.bytes_sent,
            self.bytes_received,
            self.packets_sent,
            self.packets_received,
            self.rtt_ms,
            self.jitter_ms,
            self.packet_loss_rate,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "TelemetryMetric":
        """Deserialize packed binary bytes into TelemetryMetric."""
        if len(data) < TELEMETRY_SIZE:
            raise ValueError(f"Data length {len(data)} is less than telemetry size {TELEMETRY_SIZE}")
        (
            host_id_raw,
            src_ip,
            dst_ip,
            src_port,
            dst_port,
            protocol,
            bytes_sent,
            bytes_received,
            packets_sent,
            packets_received,
            rtt_ms,
            jitter_ms,
            packet_loss_rate,
        ) = TELEMETRY_STRUCT.unpack(data[:TELEMETRY_SIZE])

        host_id = host_id_raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
        return cls(
            host_id=host_id,
            src_ip=src_ip,
            dst_ip=dst_ip,
            src_port=src_port,
            dst_port=dst_port,
            protocol=protocol,
            bytes_sent=bytes_sent,
            bytes_received=bytes_received,
            packets_sent=packets_sent,
            packets_received=packets_received,
            rtt_ms=rtt_ms,
            jitter_ms=jitter_ms,
            packet_loss_rate=packet_loss_rate,
        )
