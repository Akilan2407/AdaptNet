"""TCP socket client for streaming telemetry records to central controller."""

import socket
import sys
import time
from typing import Optional

from network.agent.flow_monitor import FlowRecord


DEFAULT_CONTROLLER_IP = "127.0.0.1"
DEFAULT_CONTROLLER_PORT = 5000
DEFAULT_RETRY_INTERVAL_SEC = 2.0


def serialize_flow_record(rec: FlowRecord) -> str:
    """
    Serialize FlowRecord into pipe-delimited line format ending in newline.

    Protocol Schema (11 fields standard wire protocol):
    timestamp|device_id|src_ip|dst_ip|src_port|dst_port|protocol|throughput|rtt|packet_loss|active_connections
    """
    rtt_str  = f"{rec.rtt_ms:.2f}"          if rec.has_rtt         else "N/A"
    loss_str = f"{rec.packet_loss_pct:.2f}" if rec.has_packet_loss  else "N/A"

    return (
        f"{rec.timestamp}|{rec.device_id}|{rec.src_ip}|{rec.dst_ip}|"
        f"{rec.src_port}|{rec.dst_port}|{rec.protocol}|{rec.throughput_mbps:.2f}|"
        f"{rtt_str}|{loss_str}|{rec.total_active_connections}\n"
    )


class SocketClient:
    """Manages resilient TCP streaming connection to controller."""

    def __init__(
        self,
        server_ip: str = DEFAULT_CONTROLLER_IP,
        server_port: int = DEFAULT_CONTROLLER_PORT,
        retry_interval_sec: float = DEFAULT_RETRY_INTERVAL_SEC,
    ):
        self.server_ip = server_ip if server_ip else DEFAULT_CONTROLLER_IP
        self.server_port = server_port if server_port > 0 else DEFAULT_CONTROLLER_PORT
        self.retry_interval_sec = retry_interval_sec if retry_interval_sec > 0.0 else DEFAULT_RETRY_INTERVAL_SEC
        self.sock: Optional[socket.socket] = None
        self.is_connected = False

    def connect(self) -> bool:
        """Attempt TCP connection to controller."""
        if self.is_connected and self.sock is not None:
            return True

        self.close()

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((self.server_ip, self.server_port))
            s.settimeout(None)
            self.sock = s
            self.is_connected = True
            print(f"[+] Connected to controller {self.server_ip}:{self.server_port}")
            return True
        except Exception:
            self.close()
            return False

    def send_record(self, rec: FlowRecord) -> bool:
        """Send flow record over active TCP socket (reconnects if needed)."""
        if not self.is_connected or self.sock is None:
            if not self.connect():
                return False

        line = serialize_flow_record(rec)
        data = line.encode("utf-8")

        try:
            assert self.sock is not None
            self.sock.sendall(data)
            return True
        except Exception as exc:
            sys.stderr.write(f"[!] Socket send failed: {exc}. Marking disconnected.\n")
            self.close()
            return False

    def close(self) -> None:
        """Close socket and reset connection state."""
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.is_connected = False
