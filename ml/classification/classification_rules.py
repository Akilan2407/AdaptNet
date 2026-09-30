"""Protocol-Aware Port and Rule Evaluation Engine for Traffic Classification."""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from ml.classification.config import (
    CONFIDENCE_EXACT_PORT,
    CONFIDENCE_PORT_RANGE,
    MAX_VALID_PORT,
    MIN_VALID_PORT,
    PORT_RULES,
    RULE_PRIORITY,
)

logger = logging.getLogger("ml.classification.classification_rules")


def is_valid_port(port: Any) -> bool:
    """Check whether a given port value is a valid TCP/UDP port integer in [1, 65535]."""
    if port is None:
        return False
    try:
        val = int(port)
        return MIN_VALID_PORT <= val <= MAX_VALID_PORT
    except (ValueError, TypeError):
        return False


def is_port_in_range(port: int, start: int, end: int) -> bool:
    """Check whether port falls within the closed interval [start, end]."""
    return start <= port <= end


def normalize_protocol(protocol: Any) -> str:
    """Normalize transport protocol identifier to uppercase string (e.g., 'TCP', 'UDP')."""
    if protocol is None:
        return "UNKNOWN"
    proto_str = str(protocol).strip().upper()
    if proto_str in {"TCP", "6", "IPPROTO_TCP"}:
        return "TCP"
    if proto_str in {"UDP", "17", "IPPROTO_UDP"}:
        return "UDP"
    return proto_str


def matches_port_spec(
    port: int,
    ports: List[int],
    ranges: List[Tuple[int, int]],
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Determine whether port matches specific single ports or range intervals.

    Args:
        port: Integer port number.
        ports: List of exact port integers.
        ranges: List of (start, end) port tuples.

    Returns:
        Tuple of (is_match, match_type, detail_string)
        where match_type is 'exact' or 'range', or (False, None, None).
    """
    if port in ports:
        return True, "exact", str(port)

    for start, end in ranges:
        if is_port_in_range(port, start, end):
            return True, "range", f"{start}-{end}"

    return False, None, None


def evaluate_port_rules(
    protocol: Any,
    src_port: Any,
    dst_port: Any,
    rules: Optional[Dict[str, Dict[str, Any]]] = None,
    priority: Optional[List[str]] = None,
) -> Optional[Tuple[str, float, str]]:
    """Evaluate metadata against configured port and protocol rules in strict priority order.

    Checks destination port first (standard server service port), then source port.

    Args:
        protocol: Flow transport protocol.
        src_port: Flow source port.
        dst_port: Flow destination port.
        rules: Dictionary of port rules per category.
        priority: List of category evaluation order.

    Returns:
        Tuple of (traffic_class, confidence, reason) if a rule matches, else None.
    """
    if rules is None:
        rules = PORT_RULES
    if priority is None:
        priority = RULE_PRIORITY

    norm_proto = normalize_protocol(protocol)
    valid_dst = is_valid_port(dst_port)
    valid_src = is_valid_port(src_port)

    dst_p = int(dst_port) if valid_dst else None
    src_p = int(src_port) if valid_src else None

    # Evaluate categories strictly according to configured precedence
    for category in priority:
        if category == "OTHER" or category not in rules:
            continue

        cat_spec = rules[category]
        allowed_protos = [p.upper() for p in cat_spec.get("protocols", [])]

        # Protocol check
        if norm_proto not in allowed_protos:
            continue

        ports_list = cat_spec.get("ports", [])
        ranges_list = cat_spec.get("ranges", [])

        # Priority A: Check Destination Port (Primary Service Port)
        if dst_p is not None:
            matched, m_type, detail = matches_port_spec(dst_p, ports_list, ranges_list)
            if matched:
                if m_type == "exact":
                    conf = CONFIDENCE_EXACT_PORT
                    reason = f"{norm_proto} destination port {dst_p} matched {category} rule"
                else:
                    conf = CONFIDENCE_PORT_RANGE
                    reason = f"{norm_proto} destination port {dst_p} matched {category} port range [{detail}]"
                return category, conf, reason

        # Priority B: Check Source Port (Reverse Service Direction)
        if src_p is not None:
            matched, m_type, detail = matches_port_spec(src_p, ports_list, ranges_list)
            if matched:
                if m_type == "exact":
                    conf = CONFIDENCE_EXACT_PORT
                    reason = f"{norm_proto} source port {src_p} matched {category} rule"
                else:
                    conf = CONFIDENCE_PORT_RANGE
                    reason = f"{norm_proto} source port {src_p} matched {category} port range [{detail}]"
                return category, conf, reason

    return None
