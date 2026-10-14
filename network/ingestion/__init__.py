"""Network data ingestion package."""

from network.ingestion.record_parser import (
    NetworkRecord,
    get_current_ingestion_timestamp,
    parse_network_record,
)
from network.ingestion.data_validator import (
    is_valid_ipv4,
    validate_network_record,
)
from network.ingestion.data_store import (
    DataStore,
    DeviceTracker,
    IngestionStats,
    DEFAULT_BUFFER_CAPACITY,
    DEFAULT_METRICS_CSV_PATH,
    DEFAULT_METRICS_JSONL_PATH,
    DEFAULT_INVALID_LOG_PATH,
)
from network.ingestion.data_ingestion import (
    data_ingestion_init,
    data_ingestion_process_raw_line,
    data_ingestion_print_stats,
    data_ingestion_get_stats,
    data_ingestion_destroy,
)

__all__ = [
    "NetworkRecord",
    "get_current_ingestion_timestamp",
    "parse_network_record",
    "is_valid_ipv4",
    "validate_network_record",
    "DataStore",
    "DeviceTracker",
    "IngestionStats",
    "DEFAULT_BUFFER_CAPACITY",
    "DEFAULT_METRICS_CSV_PATH",
    "DEFAULT_METRICS_JSONL_PATH",
    "DEFAULT_INVALID_LOG_PATH",
    "data_ingestion_init",
    "data_ingestion_process_raw_line",
    "data_ingestion_print_stats",
    "data_ingestion_get_stats",
    "data_ingestion_destroy",
]
