"""Common network protocol package."""

from network.common.protocol import (
    PROTOCOL_MAGIC,
    DEFAULT_AGENT_PORT,
    DEFAULT_CONTROLLER_PORT,
    MAX_HOST_ID_LEN,
    MessageType,
    TrafficProtocol,
    PacketHeader,
    TelemetryMetric,
    HEADER_SIZE,
    TELEMETRY_SIZE,
)

__all__ = [
    "PROTOCOL_MAGIC",
    "DEFAULT_AGENT_PORT",
    "DEFAULT_CONTROLLER_PORT",
    "MAX_HOST_ID_LEN",
    "MessageType",
    "TrafficProtocol",
    "PacketHeader",
    "TelemetryMetric",
    "HEADER_SIZE",
    "TELEMETRY_SIZE",
]
