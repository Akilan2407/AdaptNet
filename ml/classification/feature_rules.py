"""Conservative Secondary Metadata Rules for Flow Classification.

Used as secondary heuristics when port and protocol rules alone are ambiguous.
Strictly avoids unwarranted assumptions (e.g. high throughput != automatically video).
"""

import logging
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from ml.classification.classification_rules import normalize_protocol
from ml.classification.config import CONFIDENCE_SECONDARY_FEATURE

logger = logging.getLogger("ml.classification.feature_rules")


def evaluate_secondary_feature_rules(
    row: pd.Series,
    high_throughput_threshold_mbps: float = 20.0,
    interactive_max_throughput_mbps: float = 0.05,
) -> Optional[Tuple[str, float, str]]:
    """Evaluate conservative secondary heuristics based on transport and flow dynamics.

    Args:
        row: Series containing flow metadata (protocol, throughput_mbps, rtt_ms, active_connections).
        high_throughput_threshold_mbps: Threshold for heavy TCP bulk data transfer.
        interactive_max_throughput_mbps: Threshold for low-throughput interactive sessions.

    Returns:
        Tuple of (traffic_class, confidence, reason) if heuristic triggers, else None.
    """
    proto = normalize_protocol(row.get("protocol"))
    tp = float(row.get("throughput_mbps", row.get("throughput", 0.0)) or 0.0)
    conns = int(row.get("active_connections", 0) or 0)

    # Heuristic 1: Sustained high-throughput TCP transfer with active connection
    if proto == "TCP" and tp >= high_throughput_threshold_mbps and conns >= 1:
        confidence = CONFIDENCE_SECONDARY_FEATURE
        reason = (
            f"TCP sustained high throughput ({tp:.1f} Mbps >= {high_throughput_threshold_mbps} Mbps) "
            f"matched secondary bulk transfer heuristic"
        )
        return "BULK_TRANSFER", confidence, reason

    # Heuristic 2: Low-throughput interactive persistent TCP connection
    if proto == "TCP" and 0.0 < tp <= interactive_max_throughput_mbps and conns >= 1:
        confidence = 0.60
        reason = (
            f"TCP low throughput ({tp:.4f} Mbps) with active connection "
            f"matched secondary interactive heuristic"
        )
        return "INTERACTIVE", confidence, reason

    # All other cases: metadata is inconclusive; return None to trigger safe fallback to OTHER
    return None
