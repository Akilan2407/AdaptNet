"""Behavior Profile Definitions and Factual Characterization for Phase 8.

Calculates empirical cluster summary statistics and derives rule-based,
factual descriptive profile labels (e.g. 'Low-Activity', 'High-Throughput',
'Connection-Heavy') based strictly on measured relative characteristics.

IMPORTANT RULE:
Does NOT assign subjective priorities, quality-of-service (QoS) ratings,
or network policy decisions. Cluster IDs (0, 1, ...) remain the primary
mathematical identifiers.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("ml.profiling.profile_definitions")


def compute_cluster_summary(
    device_df: pd.DataFrame,
    cluster_labels: np.ndarray,
    feature_cols: List[str],
) -> pd.DataFrame:
    """Calculate mean observed metrics and device counts per cluster.

    Args:
        device_df: Device-level DataFrame
        cluster_labels: Cluster assignment array corresponding to device_df rows
        feature_cols: Numerical features to summarize

    Returns:
        DataFrame summarizing each cluster's size and mean feature values.
    """
    df = device_df.copy()
    df["cluster_id"] = cluster_labels

    summary_rows = []
    unique_clusters = sorted(df["cluster_id"].unique())

    # Key columns to summarize with friendly names
    metrics_to_summarize = [
        "mean_throughput_mbps",
        "mean_rtt_ms",
        "mean_packet_loss_percent",
        "mean_active_connections",
        "total_flow_count",
        "tcp_flow_ratio",
        "udp_flow_ratio",
        "active_hours_count",
    ]

    for cid in unique_clusters:
        cluster_members = df[df["cluster_id"] == cid]
        row: Dict[str, object] = {
            "cluster_id": int(cid),
            "device_count": len(cluster_members),
            "devices": ", ".join(cluster_members["device_id"].tolist()),
        }

        for metric in metrics_to_summarize:
            if metric in cluster_members.columns:
                val = cluster_members[metric].mean(skipna=True)
                summary_key = f"mean_{metric}" if not metric.startswith("mean_") else metric
                if metric == "total_flow_count":
                    summary_key = "mean_flow_count"
                row[summary_key] = round(float(val), 4) if pd.notna(val) else np.nan

        summary_rows.append(row)

    summary_df = pd.DataFrame(summary_rows)
    logger.info("Computed cluster summary across %d clusters", len(summary_df))
    return summary_df


def assign_descriptive_profile_labels(
    cluster_summary_df: pd.DataFrame,
) -> Dict[int, str]:
    """Generate factual, rule-based descriptive labels based on measured relative statistics.

    Classification Rules:
    1. If cluster count <= 1 or feature differences are negligible (variance near zero),
       use default mathematical identifier: 'Cluster {cid}'.
    2. Relative Comparisons:
       - High-Throughput: Cluster with peak mean throughput (if noticeably distinct).
       - Connection-Heavy: Cluster with highest active connections or high flow concurrency.
       - Low-Activity: Cluster with lowest flow counts and lowest throughput.
       - Moderate-Activity: Intermediary clusters exhibiting balanced network metrics.
    3. No QoS or priority inference is applied; labels represent purely factual behavior patterns.

    Args:
        cluster_summary_df: DataFrame output of compute_cluster_summary()

    Returns:
        Mapping of cluster_id -> profile_label string
    """
    n_clusters = len(cluster_summary_df)
    labels_map: Dict[int, str] = {}

    # If only 1 cluster, default to mathematical label
    if n_clusters <= 1:
        for cid in cluster_summary_df["cluster_id"]:
            labels_map[int(cid)] = f"Cluster {cid}"
        return labels_map

    # Check available metrics for differentiation
    has_throughput = "mean_throughput_mbps" in cluster_summary_df.columns
    has_flows = "mean_flow_count" in cluster_summary_df.columns

    throughput_vals = cluster_summary_df["mean_throughput_mbps"] if has_throughput else pd.Series([0] * n_clusters)
    flow_vals = cluster_summary_df["mean_flow_count"] if has_flows else pd.Series([0] * n_clusters)

    # Check if all clusters have identical measurements
    throughput_spread = throughput_vals.max() - throughput_vals.min()
    flow_spread = flow_vals.max() - flow_vals.min()

    if throughput_spread < 1e-4 and flow_spread < 1e-4:
        logger.info("Clusters have identical or near-identical metric means; using mathematical labels.")
        for cid in cluster_summary_df["cluster_id"]:
            labels_map[int(cid)] = f"Cluster {cid}"
        return labels_map

    # Relative ranking
    max_tp_idx = throughput_vals.idxmax()
    min_tp_idx = throughput_vals.idxmin()
    max_flow_idx = flow_vals.idxmax()
    min_flow_idx = flow_vals.idxmin()

    for idx, row in cluster_summary_df.iterrows():
        cid = int(row["cluster_id"])

        if has_throughput and throughput_spread > 1.0 and idx == max_tp_idx:
            labels_map[cid] = "High-Throughput"
        elif has_flows and flow_spread >= 5 and idx == max_flow_idx and idx != min_tp_idx:
            labels_map[cid] = "High-Flow-Activity"
        elif idx == min_flow_idx and (not has_throughput or idx == min_tp_idx):
            labels_map[cid] = "Low-Activity"
        elif (has_throughput and row["mean_throughput_mbps"] > throughput_vals.median()) or (has_flows and row["mean_flow_count"] > flow_vals.median()):
            labels_map[cid] = "Moderate-Activity"
        else:
            labels_map[cid] = "Baseline-Activity"

    # Ensure uniqueness of descriptive label or append cluster ID
    seen_labels: Dict[str, int] = {}
    for cid, lbl in labels_map.items():
        seen_labels[lbl] = seen_labels.get(lbl, 0) + 1

    for cid, lbl in list(labels_map.items()):
        if seen_labels[lbl] > 1:
            labels_map[cid] = f"{lbl} (C{cid})"

    logger.info("Assigned profile labels: %s", labels_map)
    return labels_map


def build_factual_descriptions(cluster_summary_df: pd.DataFrame) -> Dict[int, str]:
    """Build concise, factual summary sentences for each cluster without QoS bias.

    Args:
        cluster_summary_df: Cluster summary DataFrame

    Returns:
        Mapping of cluster_id -> factual description string
    """
    descriptions: Dict[int, str] = {}

    for _, row in cluster_summary_df.iterrows():
        cid = int(row["cluster_id"])
        count = int(row["device_count"])
        tp = row.get("mean_throughput_mbps", 0.0)
        flows = row.get("mean_flow_count", 0)
        tcp_ratio = row.get("tcp_flow_ratio", 1.0)
        rtt = row.get("mean_rtt_ms", np.nan)

        rtt_str = f"{rtt:.2f} ms" if pd.notna(rtt) else "N/A"
        desc = (
            f"Cluster {cid} ({count} device{'s' if count != 1 else ''}): "
            f"Mean Throughput: {tp:.2f} Mbps, Mean Flow Count: {flows:.1f}, "
            f"TCP Ratio: {tcp_ratio:.2f}, Mean RTT: {rtt_str}."
        )
        descriptions[cid] = desc

    return descriptions
