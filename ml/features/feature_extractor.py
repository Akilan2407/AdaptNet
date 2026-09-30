"""Master Feature Extraction Module (Phase 7).

Processes raw telemetry records from Phase 6 into structured, explainable,
flow-level, time-based, device-aggregated, traffic-mix, and rolling-window features.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from ml.features.config import (
    DEFAULT_INPUT_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_ROLLING_WINDOW_SECONDS,
    DEFAULT_ROLLING_WINDOW_LABEL,
    PROTOCOL_ENCODING,
    TIME_OF_DAY_BINS,
)
from ml.features.preprocessing import clean_network_data, load_network_data

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("feature_extractor")


def _hour_to_time_of_day(hour: int) -> str:
    """Map hour of day (0-23) to a categorical time bin."""
    for category, (start_hr, end_hr) in TIME_OF_DAY_BINS.items():
        if start_hr <= hour <= end_hr:
            return category
    return "night"


def extract_flow_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract flow-level numerical and categorical features.

    - throughput_mbps
    - rtt_ms
    - packet_loss_percent
    - active_connections
    - protocol_numeric (TCP=1, UDP=0)
    - traffic_volume_mbps
    - flow_id (deterministic 5-tuple string)
    """
    res = df.copy()

    # Flow metrics
    res["throughput_mbps"] = res["throughput"].astype(float)
    res["traffic_volume_mbps"] = res["throughput_mbps"]
    res["rtt_ms"] = res["rtt"].astype(float)
    res["packet_loss_percent"] = res["packet_loss"].astype(float)
    res["active_connections"] = res["active_connections"].fillna(0).astype(int)

    # Protocol encoding
    res["protocol_numeric"] = (
        res["protocol"]
        .map(PROTOCOL_ENCODING)
        .fillna(0)
        .astype(int)
    )

    # Deterministic Flow ID: {device_id}_{src_ip}:{src_port}->{dst_ip}:{dst_port}_{protocol}
    res["flow_id"] = (
        res["device_id"].astype(str)
        + "_"
        + res["src_ip"].astype(str)
        + ":"
        + res["src_port"].astype(str)
        + "->"
        + res["dst_ip"].astype(str)
        + ":"
        + res["dst_port"].astype(str)
        + "_"
        + res["protocol"].astype(str)
    )

    return res


def extract_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract calendar and diurnal time features from timestamps.

    - hour (0-23)
    - minute (0-59)
    - day_of_week (0=Monday, 6=Sunday)
    - is_weekend (1=Sat/Sun, 0=Mon-Fri)
    - time_of_day ('night', 'morning', 'afternoon', 'evening')
    """
    res = df.copy()
    ts = pd.to_datetime(res["timestamp"])

    res["hour"] = ts.dt.hour
    res["minute"] = ts.dt.minute
    res["day_of_week"] = ts.dt.dayofweek
    res["is_weekend"] = res["day_of_week"].isin([5, 6]).astype(int)
    res["time_of_day"] = res["hour"].apply(_hour_to_time_of_day)

    return res


def extract_device_aggregations(df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-device aggregated statistics across flows.

    - mean_throughput_mbps, max_throughput_mbps, min_throughput_mbps, throughput_std
    - mean_rtt_ms, max_rtt_ms, rtt_std
    - mean_packet_loss_percent, max_packet_loss_percent, packet_loss_std
    - mean_active_connections
    - total_flow_count, tcp_flow_count, udp_flow_count
    """
    res = df.copy()

    if res.empty:
        agg_cols = [
            "mean_throughput_mbps",
            "max_throughput_mbps",
            "min_throughput_mbps",
            "throughput_std",
            "mean_rtt_ms",
            "max_rtt_ms",
            "rtt_std",
            "mean_packet_loss_percent",
            "max_packet_loss_percent",
            "packet_loss_std",
            "mean_active_connections",
            "total_flow_count",
            "tcp_flow_count",
            "udp_flow_count",
        ]
        for c in agg_cols:
            res[c] = pd.Series(dtype=float if "count" not in c else int)
        return res

    # Pre-calculate boolean indicators for protocols
    res["_is_tcp"] = (res["protocol"] == "TCP").astype(int)
    res["_is_udp"] = (res["protocol"] == "UDP").astype(int)

    # Compute group statistics
    grouped = res.groupby("device_id")

    stats = grouped.agg(
        mean_throughput_mbps=("throughput_mbps", "mean"),
        max_throughput_mbps=("throughput_mbps", "max"),
        min_throughput_mbps=("throughput_mbps", "min"),
        throughput_std=("throughput_mbps", lambda s: s.std(ddof=0)),
        mean_rtt_ms=("rtt_ms", "mean"),
        max_rtt_ms=("rtt_ms", "max"),
        rtt_std=("rtt_ms", lambda s: s.std(ddof=0) if s.notna().sum() > 1 else 0.0),
        mean_packet_loss_percent=("packet_loss_percent", "mean"),
        max_packet_loss_percent=("packet_loss_percent", "max"),
        packet_loss_std=(
            "packet_loss_percent",
            lambda s: s.std(ddof=0) if s.notna().sum() > 1 else 0.0,
        ),
        mean_active_connections=("active_connections", "mean"),
        total_flow_count=("throughput_mbps", "count"),
        tcp_flow_count=("_is_tcp", "sum"),
        udp_flow_count=("_is_udp", "sum"),
    ).reset_index()

    # Fill variability std with 0.0 where safe
    stats["throughput_std"] = stats["throughput_std"].fillna(0.0)

    # Merge aggregated columns back to base DataFrame
    res = res.drop(columns=["_is_tcp", "_is_udp"])
    res = res.merge(stats, on="device_id", how="left")

    return res


def extract_traffic_mix_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute device-level TCP and UDP flow ratios (0.0 to 1.0).

    - tcp_flow_ratio = tcp_flow_count / total_flow_count
    - udp_flow_ratio = udp_flow_count / total_flow_count
    """
    res = df.copy()

    total = res["total_flow_count"].replace(0, np.nan)
    res["tcp_flow_ratio"] = (res["tcp_flow_count"] / total).fillna(0.0).clip(0.0, 1.0)
    res["udp_flow_ratio"] = (res["udp_flow_count"] / total).fillna(0.0).clip(0.0, 1.0)

    return res


def extract_rolling_features(
    df: pd.DataFrame, window_seconds: int = DEFAULT_ROLLING_WINDOW_SECONDS
) -> pd.DataFrame:
    """Compute time-window rolling averages per device.

    Sorts by timestamp, applies rolling mean with window in seconds,
    and handles missing records cleanly.

    - rolling_mean_throughput_5m
    - rolling_mean_rtt_5m
    - rolling_mean_packet_loss_5m
    """
    label = DEFAULT_ROLLING_WINDOW_LABEL
    tp_col = f"rolling_mean_throughput_{label}"
    rtt_col = f"rolling_mean_rtt_{label}"
    loss_col = f"rolling_mean_packet_loss_{label}"

    if df.empty:
        res = df.copy()
        res[tp_col] = pd.Series(dtype=float)
        res[rtt_col] = pd.Series(dtype=float)
        res[loss_col] = pd.Series(dtype=float)
        return res

    res = df.copy()
    original_index = res.index

    # Ensure timestamp is datetime and preserve sorting index
    res["_orig_idx"] = original_index
    res["_dt"] = pd.to_datetime(res["timestamp"])
    res = res.sort_values(by=["device_id", "_dt"]).reset_index(drop=True)

    window_str = f"{window_seconds}s"

    # Compute rolling means per device
    rolling_results = []
    for device_id, group in res.groupby("device_id", sort=False):
        grp = group.set_index("_dt")

        roll_tp = (
            grp["throughput_mbps"]
            .rolling(window_str, min_periods=1)
            .mean()
            .values
        )
        roll_rtt = (
            grp["rtt_ms"]
            .rolling(window_str, min_periods=1)
            .mean()
            .values
        )
        roll_loss = (
            grp["packet_loss_percent"]
            .rolling(window_str, min_periods=1)
            .mean()
            .values
        )

        group_out = group.copy()
        group_out[tp_col] = roll_tp
        group_out[rtt_col] = roll_rtt
        group_out[loss_col] = roll_loss
        rolling_results.append(group_out)

    if rolling_results:
        res = pd.concat(rolling_results, ignore_index=True)
        res = res.sort_values(by="_orig_idx").drop(columns=["_orig_idx", "_dt"]).reset_index(drop=True)
    else:
        res = res.drop(columns=["_orig_idx", "_dt"], errors="ignore")

    return res


def validate_features(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Perform data quality checks on the extracted feature dataset.

    Returns:
        (is_valid, list_of_issue_messages)
    """
    issues = []

    # 1. Non-negative throughput
    if (df["throughput_mbps"] < 0).any():
        neg_tp = (df["throughput_mbps"] < 0).sum()
        issues.append(f"Found {neg_tp} records with negative throughput_mbps.")

    # 2. Non-negative RTT where not NaN
    valid_rtt = df["rtt_ms"].dropna()
    if (valid_rtt < 0).any():
        neg_rtt = (valid_rtt < 0).sum()
        issues.append(f"Found {neg_rtt} records with negative rtt_ms.")

    # 3. Packet loss in [0, 100] where not NaN
    valid_loss = df["packet_loss_percent"].dropna()
    if ((valid_loss < 0) | (valid_loss > 100)).any():
        bad_loss = ((valid_loss < 0) | (valid_loss > 100)).sum()
        issues.append(f"Found {bad_loss} records with packet_loss_percent outside [0, 100].")

    # 4. Active connections >= 0
    if (df["active_connections"] < 0).any():
        bad_conn = (df["active_connections"] < 0).sum()
        issues.append(f"Found {bad_conn} records with negative active_connections.")

    # 5. Traffic mix ratios in [0, 1]
    if ((df["tcp_flow_ratio"] < 0) | (df["tcp_flow_ratio"] > 1.0001)).any():
        bad_tcp = ((df["tcp_flow_ratio"] < 0) | (df["tcp_flow_ratio"] > 1.0001)).sum()
        issues.append(f"Found {bad_tcp} records with tcp_flow_ratio outside [0, 1].")

    if ((df["udp_flow_ratio"] < 0) | (df["udp_flow_ratio"] > 1.0001)).any():
        bad_udp = ((df["udp_flow_ratio"] < 0) | (df["udp_flow_ratio"] > 1.0001)).sum()
        issues.append(f"Found {bad_udp} records with udp_flow_ratio outside [0, 1].")

    # 6. Hour and Day of Week ranges
    if ((df["hour"] < 0) | (df["hour"] > 23)).any():
        issues.append("Found records with hour outside range [0, 23].")

    if ((df["day_of_week"] < 0) | (df["day_of_week"] > 6)).any():
        issues.append("Found records with day_of_week outside range [0, 6].")

    # 7. No accidental inf values
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if np.isinf(df[col]).any():
            inf_count = np.isinf(df[col]).sum()
            issues.append(f"Column '{col}' contains {inf_count} infinite values.")

    is_valid = len(issues) == 0
    return is_valid, issues


def extract_all_features(
    df: pd.DataFrame, window_seconds: int = DEFAULT_ROLLING_WINDOW_SECONDS
) -> pd.DataFrame:
    """Run the complete end-to-end feature extraction pipeline."""
    cleaned = clean_network_data(df)
    with_flows = extract_flow_features(cleaned)
    with_time = extract_time_features(with_flows)
    with_aggs = extract_device_aggregations(with_time)
    with_mix = extract_traffic_mix_features(with_aggs)
    final_features = extract_rolling_features(with_mix, window_seconds=window_seconds)

    # Drop raw alias columns if mapped
    final_features = final_features.drop(
        columns=[c for c in ["throughput", "rtt", "packet_loss"] if c in final_features.columns],
        errors="ignore",
    )

    # Order columns logically
    ordered_cols = [
        "timestamp",
        "device_id",
        "flow_id",
        "src_ip",
        "dst_ip",
        "src_port",
        "dst_port",
        "protocol",
        "protocol_numeric",
        "throughput_mbps",
        "traffic_volume_mbps",
        "rtt_ms",
        "packet_loss_percent",
        "active_connections",
        "hour",
        "minute",
        "day_of_week",
        "is_weekend",
        "time_of_day",
        "mean_throughput_mbps",
        "max_throughput_mbps",
        "min_throughput_mbps",
        "throughput_std",
        "mean_rtt_ms",
        "max_rtt_ms",
        "rtt_std",
        "mean_packet_loss_percent",
        "max_packet_loss_percent",
        "packet_loss_std",
        "mean_active_connections",
        "total_flow_count",
        "tcp_flow_count",
        "udp_flow_count",
        "tcp_flow_ratio",
        "udp_flow_ratio",
        f"rolling_mean_throughput_{DEFAULT_ROLLING_WINDOW_LABEL}",
        f"rolling_mean_rtt_{DEFAULT_ROLLING_WINDOW_LABEL}",
        f"rolling_mean_packet_loss_{DEFAULT_ROLLING_WINDOW_LABEL}",
    ]

    # Include any extra columns that exist
    all_cols = [c for c in ordered_cols if c in final_features.columns]
    for c in final_features.columns:
        if c not in all_cols and not c.startswith("_"):
            all_cols.append(c)

    final_features = final_features[all_cols]
    return final_features


def print_summary(
    input_count: int,
    output_count: int,
    device_count: int,
    tcp_count: int,
    udp_count: int,
    feature_count: int,
) -> None:
    """Print standard feature extraction summary block."""
    print("========================================")
    print("FEATURE EXTRACTION")
    print("========================================")
    print(f"Input records       : {input_count}")
    print(f"Output records      : {output_count}")
    print(f"Devices             : {device_count}")
    print(f"TCP records         : {tcp_count}")
    print(f"UDP records         : {udp_count}")
    print(f"Generated features  : {feature_count}")
    print("========================================")


def main():
    """Command-line interface for the feature extractor."""
    parser = argparse.ArgumentParser(
        description="Explainable Feature Extraction Module for LAN Network Telemetry (Phase 7)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(DEFAULT_INPUT_PATH),
        help="Path to input network metrics CSV (from Phase 6)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_PATH),
        help="Path to destination network features CSV",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=DEFAULT_ROLLING_WINDOW_SECONDS,
        help="Rolling time window size in seconds (e.g. 300 for 5 minutes)",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Print sample feature rows to stdout",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    try:
        raw_df = load_network_data(input_path)
    except Exception as e:
        logger.error("Failed to load input network data: %s", e)
        sys.exit(1)

    input_count = len(raw_df)
    features_df = extract_all_features(raw_df, window_seconds=args.window)

    # Validation
    is_valid, issues = validate_features(features_df)
    if not is_valid:
        logger.warning("Feature quality issues detected:")
        for issue in issues:
            logger.warning(" - %s", issue)

    # Create destination parent directory
    output_path.parent.mkdir(parents=True, exist_ok=True)
    features_df.to_csv(output_path, index=False)
    logger.info("Saved extracted features to '%s'", output_path.resolve())

    # Summary statistics
    output_count = len(features_df)
    device_count = features_df["device_id"].nunique()
    tcp_count = int((features_df["protocol"] == "TCP").sum())
    udp_count = int((features_df["protocol"] == "UDP").sum())
    feature_count = len(features_df.columns)

    print_summary(
        input_count=input_count,
        output_count=output_count,
        device_count=device_count,
        tcp_count=tcp_count,
        udp_count=udp_count,
        feature_count=feature_count,
    )

    if args.sample:
        print("\nSample Feature Rows (first 3 records):")
        display_cols = [
            "timestamp",
            "device_id",
            "protocol",
            "throughput_mbps",
            "rtt_ms",
            "mean_throughput_mbps",
            "tcp_flow_ratio",
            "rolling_mean_throughput_5m",
        ]
        sample_cols = [c for c in display_cols if c in features_df.columns]
        print(features_df[sample_cols].head(3).to_string(index=False))


if __name__ == "__main__":
    main()
