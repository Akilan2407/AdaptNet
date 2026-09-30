"""Feature Definitions and Catalog for Phase 7 Feature Extraction.

Provides formal documentation, data types, physical units, source fields,
and mathematical formulations for all generated network features.
"""

from typing import Dict, Any


FEATURE_CATALOG: Dict[str, Dict[str, Any]] = {
    # Identity and Flow Level
    "device_id": {
        "type": "string",
        "category": "identifier",
        "description": "Unique identifier of the LAN host / network device.",
        "source": "device_id",
        "valid_range": "Non-empty string (e.g. h1, h2)",
    },
    "flow_id": {
        "type": "string",
        "category": "identifier",
        "description": "Deterministic 5-tuple + device flow identifier.",
        "source": "device_id, src_ip, src_port, dst_ip, dst_port, protocol",
        "formula": "{device_id}_{src_ip}:{src_port}->{dst_ip}:{dst_port}_{protocol}",
    },
    "throughput_mbps": {
        "type": "float",
        "category": "flow",
        "unit": "Mbps",
        "description": "Instantaneous observed network throughput in Megabits per second.",
        "source": "throughput",
        "valid_range": ">= 0.0",
    },
    "rtt_ms": {
        "type": "float",
        "category": "flow",
        "unit": "milliseconds",
        "description": "Observed round-trip time in milliseconds. Missing (NaN) for connectionless UDP flows.",
        "source": "rtt",
        "valid_range": ">= 0.0 or NaN",
    },
    "packet_loss_percent": {
        "type": "float",
        "category": "flow",
        "unit": "percentage",
        "description": "Observed packet loss percentage (0.0 to 100.0).",
        "source": "packet_loss",
        "valid_range": "0.0 - 100.0 or NaN",
    },
    "active_connections": {
        "type": "integer",
        "category": "flow",
        "unit": "count",
        "description": "Current number of concurrent active connections on the host.",
        "source": "active_connections",
        "valid_range": ">= 0",
    },
    "protocol_numeric": {
        "type": "integer",
        "category": "flow",
        "unit": "binary flag",
        "description": "Numeric protocol encoding (TCP = 1, UDP = 0).",
        "source": "protocol",
        "valid_range": "{0, 1}",
    },
    "traffic_volume_mbps": {
        "type": "float",
        "category": "flow",
        "unit": "Mbps",
        "description": "Derived traffic bandwidth volume rate indicator.",
        "source": "throughput",
        "valid_range": ">= 0.0",
    },

    # Time-based Features
    "timestamp": {
        "type": "datetime",
        "category": "temporal",
        "description": "Normalized ISO datetime string of the telemetry record.",
        "source": "timestamp",
        "valid_range": "Valid datetime",
    },
    "hour": {
        "type": "integer",
        "category": "temporal",
        "unit": "hour of day (0-23)",
        "description": "Hour component of the measurement timestamp in 24-hour format.",
        "source": "timestamp",
        "valid_range": "0 - 23",
    },
    "minute": {
        "type": "integer",
        "category": "temporal",
        "unit": "minute of hour (0-59)",
        "description": "Minute component of the measurement timestamp.",
        "source": "timestamp",
        "valid_range": "0 - 59",
    },
    "day_of_week": {
        "type": "integer",
        "category": "temporal",
        "unit": "day (0=Monday, 6=Sunday)",
        "description": "Day of the week index.",
        "source": "timestamp",
        "valid_range": "0 - 6",
    },
    "is_weekend": {
        "type": "integer",
        "category": "temporal",
        "unit": "binary flag",
        "description": "1 if day_of_week is Saturday or Sunday, else 0.",
        "source": "timestamp",
        "valid_range": "{0, 1}",
    },
    "time_of_day": {
        "type": "string",
        "category": "temporal",
        "description": "Categorical time bin: night (0-5), morning (6-11), afternoon (12-17), evening (18-23).",
        "source": "timestamp",
        "valid_range": "{'night', 'morning', 'afternoon', 'evening'}",
    },

    # Device-Level Aggregations
    "mean_throughput_mbps": {
        "type": "float",
        "category": "device_aggregation",
        "unit": "Mbps",
        "description": "Mean throughput observed for the device across all its flows.",
        "source": "throughput grouped by device_id",
        "valid_range": ">= 0.0",
    },
    "max_throughput_mbps": {
        "type": "float",
        "category": "device_aggregation",
        "unit": "Mbps",
        "description": "Peak throughput observed for the device.",
        "source": "throughput grouped by device_id",
        "valid_range": ">= 0.0",
    },
    "min_throughput_mbps": {
        "type": "float",
        "category": "device_aggregation",
        "unit": "Mbps",
        "description": "Minimum throughput observed for the device.",
        "source": "throughput grouped by device_id",
        "valid_range": ">= 0.0",
    },
    "throughput_std": {
        "type": "float",
        "category": "device_variability",
        "unit": "Mbps",
        "description": "Standard deviation of throughput for the device (0.0 if <= 1 sample).",
        "source": "throughput grouped by device_id",
        "valid_range": ">= 0.0",
    },
    "mean_rtt_ms": {
        "type": "float",
        "category": "device_aggregation",
        "unit": "milliseconds",
        "description": "Mean round-trip time across all TCP flows for the device.",
        "source": "rtt grouped by device_id",
        "valid_range": ">= 0.0 or NaN",
    },
    "max_rtt_ms": {
        "type": "float",
        "category": "device_aggregation",
        "unit": "milliseconds",
        "description": "Maximum round-trip time observed for the device.",
        "source": "rtt grouped by device_id",
        "valid_range": ">= 0.0 or NaN",
    },
    "rtt_std": {
        "type": "float",
        "category": "device_variability",
        "unit": "milliseconds",
        "description": "Standard deviation of RTT for the device (0.0 if <= 1 sample).",
        "source": "rtt grouped by device_id",
        "valid_range": ">= 0.0 or NaN",
    },
    "mean_packet_loss_percent": {
        "type": "float",
        "category": "device_aggregation",
        "unit": "percentage",
        "description": "Mean packet loss percentage observed for the device.",
        "source": "packet_loss grouped by device_id",
        "valid_range": "0.0 - 100.0 or NaN",
    },
    "max_packet_loss_percent": {
        "type": "float",
        "category": "device_aggregation",
        "unit": "percentage",
        "description": "Maximum packet loss percentage observed for the device.",
        "source": "packet_loss grouped by device_id",
        "valid_range": "0.0 - 100.0 or NaN",
    },
    "packet_loss_std": {
        "type": "float",
        "category": "device_variability",
        "unit": "percentage",
        "description": "Standard deviation of packet loss for the device (0.0 if <= 1 sample).",
        "source": "packet_loss grouped by device_id",
        "valid_range": "0.0 - 100.0 or NaN",
    },
    "mean_active_connections": {
        "type": "float",
        "category": "device_aggregation",
        "unit": "count",
        "description": "Mean active connection count for the device.",
        "source": "active_connections grouped by device_id",
        "valid_range": ">= 0.0",
    },
    "total_flow_count": {
        "type": "integer",
        "category": "device_aggregation",
        "unit": "count",
        "description": "Total number of network flow records recorded for the device.",
        "source": "count grouped by device_id",
        "valid_range": ">= 1",
    },
    "tcp_flow_count": {
        "type": "integer",
        "category": "device_aggregation",
        "unit": "count",
        "description": "Total number of TCP flow records recorded for the device.",
        "source": "protocol == 'TCP' grouped by device_id",
        "valid_range": ">= 0",
    },
    "udp_flow_count": {
        "type": "integer",
        "category": "device_aggregation",
        "unit": "count",
        "description": "Total number of UDP flow records recorded for the device.",
        "source": "protocol == 'UDP' grouped by device_id",
        "valid_range": ">= 0",
    },
    "tcp_flow_ratio": {
        "type": "float",
        "category": "traffic_mix",
        "unit": "ratio",
        "description": "Proportion of TCP flows out of total flows for the device (0.0 to 1.0).",
        "formula": "tcp_flow_count / total_flow_count",
        "valid_range": "0.0 - 1.0",
    },
    "udp_flow_ratio": {
        "type": "float",
        "category": "traffic_mix",
        "unit": "ratio",
        "description": "Proportion of UDP flows out of total flows for the device (0.0 to 1.0).",
        "formula": "udp_flow_count / total_flow_count",
        "valid_range": "0.0 - 1.0",
    },

    # Rolling Window Features (Configurable window, default 5m)
    "rolling_mean_throughput_5m": {
        "type": "float",
        "category": "rolling",
        "unit": "Mbps",
        "description": "Rolling mean throughput over a 5-minute (300s) time window per device.",
        "source": "throughput rolling window by timestamp per device",
        "valid_range": ">= 0.0",
    },
    "rolling_mean_rtt_5m": {
        "type": "float",
        "category": "rolling",
        "unit": "milliseconds",
        "description": "Rolling mean RTT over a 5-minute (300s) time window per device.",
        "source": "rtt rolling window by timestamp per device",
        "valid_range": ">= 0.0 or NaN",
    },
    "rolling_mean_packet_loss_5m": {
        "type": "float",
        "category": "rolling",
        "unit": "percentage",
        "description": "Rolling mean packet loss over a 5-minute (300s) time window per device.",
        "source": "packet_loss rolling window by timestamp per device",
        "valid_range": "0.0 - 100.0 or NaN",
    },
}


def get_feature_info(feature_name: str) -> Dict[str, Any]:
    """Retrieve metadata description for a given feature."""
    return FEATURE_CATALOG.get(
        feature_name,
        {"type": "unknown", "description": "Custom or uncataloged feature"},
    )


def list_features() -> list:
    """Return a list of all defined feature names."""
    return list(FEATURE_CATALOG.keys())
