"""In-memory ring buffer, device tracking, and persistent storage for network records (converted from data_store.h/.c)."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
from typing import Dict, List, Optional

from network.ingestion.record_parser import NetworkRecord, get_current_ingestion_timestamp


DEFAULT_BUFFER_CAPACITY = 1000
MAX_TRACKED_DEVICES = 64
DEFAULT_METRICS_CSV_PATH = "data/monitoring/network_metrics.csv"
DEFAULT_METRICS_JSONL_PATH = "data/monitoring/network_metrics.jsonl"
DEFAULT_INVALID_LOG_PATH = "data/monitoring/invalid_records.log"


@dataclass
class DeviceTracker:
    device_id: str
    total_records: int = 0
    tcp_records: int = 0
    udp_records: int = 0
    last_timestamp: str = ""
    last_protocol: str = ""
    last_throughput: float = 0.0


@dataclass
class IngestionStats:
    total_received: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    duplicate_records: int = 0
    tcp_records: int = 0
    udp_records: int = 0
    devices_tracked: int = 0
    buffer_count: int = 0
    buffer_capacity: int = DEFAULT_BUFFER_CAPACITY


class DataStore:
    """Thread-safe circular ring buffer and multi-destination persistent store."""

    def __init__(
        self,
        buffer_capacity: int = DEFAULT_BUFFER_CAPACITY,
        csv_path: Optional[str] = None,
        jsonl_path: Optional[str] = None,
        invalid_log_path: Optional[str] = None,
    ):
        self.buffer_capacity = buffer_capacity if buffer_capacity > 0 else DEFAULT_BUFFER_CAPACITY
        self.csv_path = csv_path if csv_path else DEFAULT_METRICS_CSV_PATH
        self.jsonl_path = jsonl_path if jsonl_path else DEFAULT_METRICS_JSONL_PATH
        self.invalid_log_path = invalid_log_path if invalid_log_path else DEFAULT_INVALID_LOG_PATH

        self.ring_buffer: List[Optional[NetworkRecord]] = [None] * self.buffer_capacity
        self.buffer_head: int = 0
        self.buffer_count: int = 0

        self.devices: Dict[str, DeviceTracker] = {}
        self.stats = IngestionStats(buffer_capacity=self.buffer_capacity)
        self.lock = threading.Lock()

        self._ensure_parent_dirs()
        self._init_files()

    def _ensure_parent_dirs(self) -> None:
        for path_str in (self.csv_path, self.jsonl_path, self.invalid_log_path):
            p = Path(path_str)
            p.parent.mkdir(parents=True, exist_ok=True)

    def _init_files(self) -> None:
        # Create CSV header if not exists or empty
        csv_p = Path(self.csv_path)
        if not csv_p.exists() or csv_p.stat().st_size == 0:
            with open(csv_p, "w", encoding="utf-8") as f:
                f.write("timestamp,device_id,src_ip,dst_ip,src_port,dst_port,protocol,throughput,rtt,packet_loss,active_connections\n")

    def is_duplicate(self, record: NetworkRecord) -> bool:
        """Check if record matches an existing entry in the recent buffer."""
        if self.buffer_count == 0:
            return False

        scan_limit = min(self.buffer_count, 200)
        idx = (self.buffer_head - 1) % self.buffer_capacity

        for _ in range(scan_limit):
            existing = self.ring_buffer[idx]
            if existing is not None:
                if (
                    existing.measurement_timestamp == record.measurement_timestamp
                    and existing.device_id == record.device_id
                    and existing.src_ip == record.src_ip
                    and existing.dst_ip == record.dst_ip
                    and existing.src_port == record.src_port
                    and existing.dst_port == record.dst_port
                    and existing.protocol == record.protocol
                ):
                    return True
            idx = (idx - 1) % self.buffer_capacity

        return False

    def insert_record(self, record: NetworkRecord) -> int:
        """Store a validated record (duplicate check, ring buffer, CSV, JSONL, device tracker).

        Returns:
            0 on success, 1 on duplicate detected, -1 on error.
        """
        with self.lock:
            # 1. Duplicate check
            if self.is_duplicate(record):
                self.stats.duplicate_records += 1
                self._log_invalid_locked("DUPLICATE", "Duplicate record detected (already in recent buffer)")
                return 1

            # 2. Ring buffer insertion
            self.ring_buffer[self.buffer_head] = record
            self.buffer_head = (self.buffer_head + 1) % self.buffer_capacity
            if self.buffer_count < self.buffer_capacity:
                self.buffer_count += 1
            self.stats.buffer_count = self.buffer_count

            # 3. Update device tracker
            if record.device_id not in self.devices:
                self.devices[record.device_id] = DeviceTracker(device_id=record.device_id)

            dev = self.devices[record.device_id]
            dev.total_records += 1
            if record.protocol == "TCP":
                dev.tcp_records += 1
            elif record.protocol == "UDP":
                dev.udp_records += 1
            dev.last_timestamp = record.measurement_timestamp
            dev.last_protocol = record.protocol
            dev.last_throughput = record.throughput_mbps

            # 4. Update stats
            self.stats.valid_records += 1
            if record.protocol == "TCP":
                self.stats.tcp_records += 1
            elif record.protocol == "UDP":
                self.stats.udp_records += 1
            self.stats.devices_tracked = len(self.devices)

            # 5. Write to CSV
            rtt_str = f"{record.rtt_ms:.2f}" if (record.has_rtt and record.rtt_ms is not None) else "N/A"
            loss_str = f"{record.packet_loss_pct:.2f}" if (record.has_packet_loss and record.packet_loss_pct is not None) else "N/A"

            csv_line = (
                f"{record.measurement_timestamp},{record.device_id},{record.src_ip},{record.dst_ip},"
                f"{record.src_port},{record.dst_port},{record.protocol},{record.throughput_mbps:.2f},"
                f"{rtt_str},{loss_str},{record.active_connections}\n"
            )
            with open(self.csv_path, "a", encoding="utf-8") as f:
                f.write(csv_line)
                f.flush()

            # 6. Write to JSONL
            rtt_val = round(record.rtt_ms, 2) if (record.has_rtt and record.rtt_ms is not None) else None
            loss_val = round(record.packet_loss_pct, 2) if (record.has_packet_loss and record.packet_loss_pct is not None) else None

            jsonl_obj = {
                "timestamp": record.measurement_timestamp,
                "ingestion_timestamp": record.ingestion_timestamp,
                "device_id": record.device_id,
                "src_ip": record.src_ip,
                "dst_ip": record.dst_ip,
                "src_port": record.src_port,
                "dst_port": record.dst_port,
                "protocol": record.protocol,
                "throughput": round(record.throughput_mbps, 2),
                "rtt": rtt_val,
                "packet_loss": loss_val,
                "active_connections": record.active_connections,
            }
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(jsonl_obj) + "\n")
                f.flush()

            return 0

    def _log_invalid_locked(self, raw_line: str, reason: str) -> None:
        self.stats.invalid_records += 1
        ts = get_current_ingestion_timestamp()
        log_line = f"[{ts}] REJECTED ({reason}): {raw_line}\n"
        with open(self.invalid_log_path, "a", encoding="utf-8") as f:
            f.write(log_line)
            f.flush()

    def log_invalid(self, raw_line: str, reason: str) -> None:
        """Log an invalid or rejected raw line with rejection reason."""
        with self.lock:
            self._log_invalid_locked(raw_line, reason)

    def get_stats(self) -> IngestionStats:
        """Retrieve copy of ingestion statistics."""
        with self.lock:
            return IngestionStats(
                total_received=self.stats.total_received,
                valid_records=self.stats.valid_records,
                invalid_records=self.stats.invalid_records,
                duplicate_records=self.stats.duplicate_records,
                tcp_records=self.stats.tcp_records,
                udp_records=self.stats.udp_records,
                devices_tracked=len(self.devices),
                buffer_count=self.buffer_count,
                buffer_capacity=self.buffer_capacity,
            )

    def get_recent_records(self, max_records: int) -> List[NetworkRecord]:
        """Retrieve records from recent ring buffer (newest first)."""
        with self.lock:
            count = min(self.buffer_count, max_records)
            records: List[NetworkRecord] = []
            idx = (self.buffer_head - 1) % self.buffer_capacity
            for _ in range(count):
                rec = self.ring_buffer[idx]
                if rec is not None:
                    records.append(rec)
                idx = (idx - 1) % self.buffer_capacity
            return records

    def destroy(self) -> None:
        """Clear memory and reset state."""
        with self.lock:
            self.ring_buffer = [None] * self.buffer_capacity
            self.buffer_head = 0
            self.buffer_count = 0
            self.devices.clear()
