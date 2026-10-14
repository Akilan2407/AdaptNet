"""Global network data ingestion pipeline (converted from data_ingestion.h/.c)."""

import sys
from typing import Optional

from network.ingestion.data_store import (
    DataStore,
    DEFAULT_BUFFER_CAPACITY,
    IngestionStats,
)
from network.ingestion.data_validator import validate_network_record
from network.ingestion.record_parser import parse_network_record


_store: Optional[DataStore] = None


def data_ingestion_init(
    buffer_size: int = DEFAULT_BUFFER_CAPACITY,
    csv_path: Optional[str] = None,
    jsonl_path: Optional[str] = None,
    invalid_log_path: Optional[str] = None,
) -> int:
    """Initialize or re-initialize the global data ingestion pipeline."""
    global _store
    if _store is not None:
        data_ingestion_destroy()

    try:
        _store = DataStore(
            buffer_capacity=buffer_size,
            csv_path=csv_path,
            jsonl_path=jsonl_path,
            invalid_log_path=invalid_log_path,
        )
        return 0
    except Exception as exc:
        sys.stderr.write(f"[!] Failed to initialize DataStore: {exc}\n")
        return -1


def data_ingestion_process_raw_line(raw_line: str, client_addr: Optional[str] = None) -> int:
    """Ingest a single raw stream line received from a monitoring agent.

    Handles parsing, validation, duplicate checking, ring buffering, and persistence.

    Returns:
        0 on success, 1 on duplicate, -1 on parsing/validation error.
    """
    global _store
    if _store is None:
        data_ingestion_init()

    assert _store is not None
    _store.stats.total_received += 1

    # 1. Parse raw record
    record, parse_err = parse_network_record(raw_line)
    if record is None or parse_err is not None:
        addr = client_addr if client_addr else "local"
        err_msg = parse_err if parse_err else "Parsing failure"
        sys.stderr.write(f"[!] Ingestion parse error from {addr}: {err_msg} | Raw: '{raw_line}'\n")
        _store.log_invalid(raw_line, err_msg)
        return -1

    # 2. Validate record
    valid, val_err = validate_network_record(record)
    if not valid or val_err is not None:
        addr = client_addr if client_addr else "local"
        err_msg = val_err if val_err else "Validation failure"
        sys.stderr.write(f"[!] Ingestion validation error from {addr}: {err_msg} | Raw: '{raw_line}'\n")
        _store.log_invalid(raw_line, err_msg)
        return -1

    # 3. Insert into data store
    insert_res = _store.insert_record(record)
    if insert_res == 1:
        addr = client_addr if client_addr else "local"
        print(f"  [i] Duplicate record ignored from {addr} [{record.device_id}: {record.src_ip} -> {record.dst_ip}]")
        return 1

    return 0


def data_ingestion_print_stats() -> None:
    """Print current ingestion statistics to stdout."""
    global _store
    if _store is None:
        return

    stats = _store.get_stats()
    print("\n========================================")
    print("NETWORK DATA INGESTION")
    print("========================================")
    print(f"Records received : {stats.total_received}")
    print(f"Valid records    : {stats.valid_records}")
    print(f"Invalid records  : {stats.invalid_records}")
    print(f"Duplicates       : {stats.duplicate_records}")
    print(f"TCP records      : {stats.tcp_records}")
    print(f"UDP records      : {stats.udp_records}")
    print(f"Devices tracked  : {stats.devices_tracked}")
    print(f"Buffer size      : {stats.buffer_capacity} (Current: {stats.buffer_count})")
    print("========================================\n")


def data_ingestion_get_stats() -> IngestionStats:
    """Retrieve snapshot of current ingestion statistics."""
    global _store
    if _store is None:
        return IngestionStats()
    return _store.get_stats()


def data_ingestion_destroy() -> None:
    """Teardown ingestion pipeline and flush all storage."""
    global _store
    if _store is not None:
        _store.destroy()
        _store = None
