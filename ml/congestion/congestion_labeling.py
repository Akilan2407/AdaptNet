"""Congestion Scoring and Labeling Module for Phase 9.

Implements a transparent, deterministic, multi-factor network congestion score
and categorical class assignment (LOW, MEDIUM, HIGH).

CRITICAL NOTE:
The congestion score defined here is a dataset-derived target for training
recurrent forecasting models (Phase 10), calculated from measurable physical
telemetry indicators (loss, RTT, throughput, connections). It is NOT an arbitrary
random value, nor is it claimed as an absolute universal standard.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

import numpy as np
import pandas as pd

from ml.congestion.config import (
    BASE_RTT_MS,
    DEFAULT_LABEL_CONFIG_PATH,
    HIGH_THRESHOLD,
    LOW_THRESHOLD,
    MAX_ACTIVE_CONNECTIONS,
    MAX_PACKET_LOSS_PCT,
    MAX_RTT_MS,
    NOMINAL_BANDWIDTH_MBPS,
    WEIGHT_CONNECTIONS,
    WEIGHT_PACKET_LOSS,
    WEIGHT_RTT,
    WEIGHT_THROUGHPUT,
)

logger = logging.getLogger("ml.congestion.congestion_labeling")


def calculate_congestion_score(
    df: pd.DataFrame,
    nominal_bandwidth: float = NOMINAL_BANDWIDTH_MBPS,
    base_rtt: float = BASE_RTT_MS,
    max_rtt: float = MAX_RTT_MS,
    max_loss: float = MAX_PACKET_LOSS_PCT,
    max_connections: float = MAX_ACTIVE_CONNECTIONS,
    weight_loss: float = WEIGHT_PACKET_LOSS,
    weight_rtt: float = WEIGHT_RTT,
    weight_tp: float = WEIGHT_THROUGHPUT,
    weight_conn: float = WEIGHT_CONNECTIONS,
) -> pd.Series:
    """Calculate normalized continuous congestion score in [0.0, 1.0].

    Formulation:
    1. Packet Loss Factor (L_loss):
       L_loss = min(1.0, max(0.0, packet_loss_percent) / max_loss)
       Reflects buffer overflow, link congestion drops, or transmission failures.

    2. RTT Inflation Factor (L_rtt):
       L_rtt = min(1.0, max(0.0, rtt_ms - base_rtt) / (max_rtt - base_rtt))
       Reflects queue buildup and bufferbloat above nominal baseline delay.

    3. Bandwidth Load Factor (L_tp):
       L_tp = min(1.0, max(0.0, throughput_mbps) / nominal_bandwidth)
       Reflects link saturation relative to nominal capacity.

    4. Active Connections Concurrency Factor (L_conn):
       L_conn = min(1.0, max(0.0, active_connections) / max_connections)
       Reflects socket concurrency pressure on network stack.

    Composite Score:
       Score = (w_loss * L_loss) + (w_rtt * L_rtt) + (w_tp * L_tp) + (w_conn * L_conn)

    Missing Value Handling:
       Missing (NaN) metrics default to 0.0 contribution rather than artificial spikes.

    Args:
        df: Input DataFrame containing network flow metrics
        nominal_bandwidth: Reference bandwidth in Mbps
        base_rtt: Baseline uncongested latency in ms
        max_rtt: Latency saturation threshold in ms
        max_loss: Severe packet loss threshold in percent
        max_connections: Concurrent connections saturation threshold
        weight_loss: Weight for packet loss factor
        weight_rtt: Weight for latency factor
        weight_tp: Weight for throughput load factor
        weight_conn: Weight for connection concurrency factor

    Returns:
        pd.Series of float scores bounded in [0.0, 1.0]
    """
    n_rows = len(df)
    if n_rows == 0:
        return pd.Series([], dtype=np.float64)

    # 1. Packet Loss Factor
    if "packet_loss_percent" in df.columns:
        loss = df["packet_loss_percent"].fillna(0.0).to_numpy(dtype=np.float64)
        l_loss = np.clip(loss / max_loss, 0.0, 1.0)
    elif "mean_packet_loss_percent" in df.columns:
        loss = df["mean_packet_loss_percent"].fillna(0.0).to_numpy(dtype=np.float64)
        l_loss = np.clip(loss / max_loss, 0.0, 1.0)
    else:
        l_loss = np.zeros(n_rows, dtype=np.float64)

    # 2. RTT Inflation Factor
    if "rtt_ms" in df.columns:
        rtt = df["rtt_ms"].fillna(0.0).to_numpy(dtype=np.float64)
        rtt_excess = np.maximum(0.0, rtt - base_rtt)
        l_rtt = np.clip(rtt_excess / (max_rtt - base_rtt), 0.0, 1.0)
    elif "mean_rtt_ms" in df.columns:
        rtt = df["mean_rtt_ms"].fillna(0.0).to_numpy(dtype=np.float64)
        rtt_excess = np.maximum(0.0, rtt - base_rtt)
        l_rtt = np.clip(rtt_excess / (max_rtt - base_rtt), 0.0, 1.0)
    else:
        l_rtt = np.zeros(n_rows, dtype=np.float64)

    # 3. Bandwidth Load Factor
    if "throughput_mbps" in df.columns:
        tp = df["throughput_mbps"].fillna(0.0).to_numpy(dtype=np.float64)
        l_tp = np.clip(tp / nominal_bandwidth, 0.0, 1.0)
    elif "mean_throughput_mbps" in df.columns:
        tp = df["mean_throughput_mbps"].fillna(0.0).to_numpy(dtype=np.float64)
        l_tp = np.clip(tp / nominal_bandwidth, 0.0, 1.0)
    else:
        l_tp = np.zeros(n_rows, dtype=np.float64)

    # 4. Active Connections Factor
    if "active_connections" in df.columns:
        conn = df["active_connections"].fillna(0.0).to_numpy(dtype=np.float64)
        l_conn = np.clip(conn / max_connections, 0.0, 1.0)
    elif "mean_active_connections" in df.columns:
        conn = df["mean_active_connections"].fillna(0.0).to_numpy(dtype=np.float64)
        l_conn = np.clip(conn / max_connections, 0.0, 1.0)
    else:
        l_conn = np.zeros(n_rows, dtype=np.float64)

    # Normalize weights to sum to 1.0
    total_weight = weight_loss + weight_rtt + weight_tp + weight_conn
    w_loss = weight_loss / total_weight
    w_rtt = weight_rtt / total_weight
    w_tp = weight_tp / total_weight
    w_conn = weight_conn / total_weight

    score = (w_loss * l_loss) + (w_rtt * l_rtt) + (w_tp * l_tp) + (w_conn * l_conn)
    score_series = pd.Series(np.clip(score, 0.0, 1.0), index=df.index, name="congestion_score")

    logger.debug(
        "Calculated congestion scores: min=%.4f, mean=%.4f, max=%.4f",
        score_series.min(),
        score_series.mean(),
        score_series.max(),
    )
    return score_series


def assign_congestion_class(
    scores: Union[pd.Series, np.ndarray],
    low_threshold: float = LOW_THRESHOLD,
    high_threshold: float = HIGH_THRESHOLD,
) -> pd.Series:
    """Map continuous congestion scores to categorical classes.

    Classes:
    - LOW    : score < low_threshold (default [0.00, 0.33))
    - MEDIUM : low_threshold <= score < high_threshold (default [0.33, 0.67))
    - HIGH   : score >= high_threshold (default [0.67, 1.00])

    Args:
        scores: Series or array of float congestion scores
        low_threshold: Threshold between LOW and MEDIUM
        high_threshold: Threshold between MEDIUM and HIGH

    Returns:
        pd.Series of string labels: 'LOW', 'MEDIUM', 'HIGH'
    """
    arr = np.asarray(scores, dtype=np.float64)
    classes = np.empty(len(arr), dtype=object)

    classes[arr < low_threshold] = "LOW"
    classes[(arr >= low_threshold) & (arr < high_threshold)] = "MEDIUM"
    classes[arr >= high_threshold] = "HIGH"

    # Handle any NaNs if present
    classes[np.isnan(arr)] = "UNKNOWN"

    return pd.Series(classes, name="congestion_class")


def export_label_config(
    output_path: Union[str, Path] = DEFAULT_LABEL_CONFIG_PATH,
    low_threshold: float = LOW_THRESHOLD,
    high_threshold: float = HIGH_THRESHOLD,
) -> Path:
    """Save the exact labeling configuration and formula parameters to JSON.

    Args:
        output_path: Target JSON file path
        low_threshold: Configured low threshold
        high_threshold: Configured high threshold

    Returns:
        Path to written JSON
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    config_data = {
        "description": "Dataset-derived multi-factor congestion scoring formula and class thresholds",
        "formula": "score = (w_loss * L_loss) + (w_rtt * L_rtt) + (w_tp * L_tp) + (w_conn * L_conn)",
        "score_range": [0.0, 1.0],
        "weights": {
            "packet_loss": WEIGHT_PACKET_LOSS,
            "rtt": WEIGHT_RTT,
            "throughput": WEIGHT_THROUGHPUT,
            "active_connections": WEIGHT_CONNECTIONS,
        },
        "baselines": {
            "nominal_bandwidth_mbps": NOMINAL_BANDWIDTH_MBPS,
            "base_rtt_ms": BASE_RTT_MS,
            "max_rtt_ms": MAX_RTT_MS,
            "max_packet_loss_pct": MAX_PACKET_LOSS_PCT,
            "max_active_connections": MAX_ACTIVE_CONNECTIONS,
        },
        "class_thresholds": {
            "LOW": [0.0, low_threshold],
            "MEDIUM": [low_threshold, high_threshold],
            "HIGH": [high_threshold, 1.0],
        },
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    logger.info("Saved congestion label configuration to %s", path)
    return path
