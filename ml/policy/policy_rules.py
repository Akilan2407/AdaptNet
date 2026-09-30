"""Structured declarative policy rules and evaluation catalog for Phase 13 QoS Policy Engine.

Rules map combinations of (traffic_class, congestion_class) to assigned priority,
unique traceable rule ID, and human-readable explanation template.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from ml.policy.config import TRAFFIC_CLASS_PRIORITIES, DEFAULT_PRIORITY

# Match-all wildcard
ANY = "ANY"

# Structured Policy Rule Definitions (Evaluated in strict deterministic order)
POLICY_RULES: List[Dict[str, Any]] = [
    # ---------------------------------------------------------
    # 1. HIGH Congestion Rules (Strongest Differentiation)
    # ---------------------------------------------------------
    {
        "rule_id": "POLICY_RT_HIGH_CONGESTION",
        "traffic_class": "REAL_TIME",
        "congestion_class": "HIGH",
        "priority": "HIGH",
        "reason": "REAL_TIME traffic during HIGH predicted congestion received HIGH priority to preserve latency sensitivity.",
    },
    {
        "rule_id": "POLICY_INT_HIGH_CONGESTION",
        "traffic_class": "INTERACTIVE",
        "congestion_class": "HIGH",
        "priority": "HIGH",
        "reason": "INTERACTIVE traffic during HIGH predicted congestion received HIGH priority to prevent terminal/UI lag.",
    },
    {
        "rule_id": "POLICY_DNS_HIGH_CONGESTION",
        "traffic_class": "DNS",
        "congestion_class": "HIGH",
        "priority": "HIGH",
        "reason": "DNS resolution traffic during HIGH predicted congestion received HIGH priority to avoid lookup timeouts.",
    },
    {
        "rule_id": "POLICY_WEB_HIGH_CONGESTION",
        "traffic_class": "WEB",
        "congestion_class": "HIGH",
        "priority": "MEDIUM",
        "reason": "WEB traffic during HIGH predicted congestion received MEDIUM priority.",
    },
    {
        "rule_id": "POLICY_BULK_HIGH_CONGESTION",
        "traffic_class": "BULK_TRANSFER",
        "congestion_class": "HIGH",
        "priority": "LOW",
        "reason": "BULK_TRANSFER traffic during HIGH predicted congestion received LOW priority to relieve channel saturation.",
    },
    {
        "rule_id": "POLICY_OTHER_HIGH_CONGESTION",
        "traffic_class": "OTHER",
        "congestion_class": "HIGH",
        "priority": "LOW",
        "reason": "OTHER unclassified traffic during HIGH predicted congestion received LOW priority.",
    },

    # ---------------------------------------------------------
    # 2. MEDIUM Congestion Rules (Moderate Differentiation)
    # ---------------------------------------------------------
    {
        "rule_id": "POLICY_RT_MED_CONGESTION",
        "traffic_class": "REAL_TIME",
        "congestion_class": "MEDIUM",
        "priority": "HIGH",
        "reason": "REAL_TIME traffic during MEDIUM predicted congestion received HIGH priority.",
    },
    {
        "rule_id": "POLICY_INT_MED_CONGESTION",
        "traffic_class": "INTERACTIVE",
        "congestion_class": "MEDIUM",
        "priority": "HIGH",
        "reason": "INTERACTIVE traffic during MEDIUM predicted congestion received HIGH priority.",
    },
    {
        "rule_id": "POLICY_DNS_MED_CONGESTION",
        "traffic_class": "DNS",
        "congestion_class": "MEDIUM",
        "priority": "MEDIUM",
        "reason": "DNS traffic during MEDIUM predicted congestion received MEDIUM priority.",
    },
    {
        "rule_id": "POLICY_WEB_MED_CONGESTION",
        "traffic_class": "WEB",
        "congestion_class": "MEDIUM",
        "priority": "MEDIUM",
        "reason": "WEB traffic during MEDIUM predicted congestion received MEDIUM priority.",
    },
    {
        "rule_id": "POLICY_BULK_MED_CONGESTION",
        "traffic_class": "BULK_TRANSFER",
        "congestion_class": "MEDIUM",
        "priority": "LOW",
        "reason": "BULK_TRANSFER traffic during MEDIUM predicted congestion received LOW priority.",
    },
    {
        "rule_id": "POLICY_OTHER_MED_CONGESTION",
        "traffic_class": "OTHER",
        "congestion_class": "MEDIUM",
        "priority": "NORMAL",
        "reason": "OTHER traffic during MEDIUM predicted congestion received NORMAL priority.",
    },

    # ---------------------------------------------------------
    # 3. LOW Congestion Rules (Normal Traffic-Class Preference)
    # ---------------------------------------------------------
    {
        "rule_id": "POLICY_LOW_CONGESTION_BASE",
        "traffic_class": ANY,
        "congestion_class": "LOW",
        "priority": None,  # Dynamically looked up from TRAFFIC_CLASS_PRIORITIES
        "reason": "{traffic_class} traffic during LOW predicted congestion received default base priority {priority}.",
    },

    # ---------------------------------------------------------
    # 4. Fallback for UNKNOWN Congestion (Fallback to Base Priority)
    # ---------------------------------------------------------
    {
        "rule_id": "POLICY_UNKNOWN_CONGESTION_FALLBACK",
        "traffic_class": ANY,
        "congestion_class": "UNKNOWN",
        "priority": None,  # Dynamically looked up from TRAFFIC_CLASS_PRIORITIES
        "reason": "{traffic_class} traffic with UNKNOWN predicted congestion received default base priority {priority}.",
    },

    # ---------------------------------------------------------
    # 5. Default Traffic-Class Rule
    # ---------------------------------------------------------
    {
        "rule_id": "POLICY_DEFAULT_BASE",
        "traffic_class": ANY,
        "congestion_class": ANY,
        "priority": None,
        "reason": "Default traffic-class preference applied: {traffic_class} received {priority}.",
    },
]

# Catch-all generic fallback rule
FALLBACK_RULE: Dict[str, Any] = {
    "rule_id": "POLICY_DEFAULT",
    "traffic_class": ANY,
    "congestion_class": ANY,
    "priority": DEFAULT_PRIORITY,
    "reason": "No specific traffic rule matched; NORMAL priority applied.",
}


def find_matching_rule(
    traffic_class: str,
    congestion_class: str,
    custom_rules: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Find the first matching rule in deterministic order.

    Args:
        traffic_class: Normalized traffic category string.
        congestion_class: Normalized congestion level string.
        custom_rules: Optional custom rule catalog to evaluate instead of default.

    Returns:
        Matched rule dictionary with resolved priority and formatted reason template.
    """
    rule_catalog = custom_rules if custom_rules is not None else POLICY_RULES

    normalized_traffic = traffic_class.upper().strip() if traffic_class else "OTHER"
    normalized_congestion = congestion_class.upper().strip() if congestion_class else "UNKNOWN"

    for rule in rule_catalog:
        tc_match = (rule["traffic_class"] == ANY) or (rule["traffic_class"] == normalized_traffic)
        cc_match = (rule["congestion_class"] == ANY) or (rule["congestion_class"] == normalized_congestion)

        if tc_match and cc_match:
            resolved_rule = dict(rule)
            # Resolve dynamic priority if None
            if resolved_rule["priority"] is None:
                base_pri = TRAFFIC_CLASS_PRIORITIES.get(normalized_traffic, DEFAULT_PRIORITY)
                resolved_rule["priority"] = base_pri
            
            # Format reason template if needed
            reason = resolved_rule["reason"]
            if "{traffic_class}" in reason or "{priority}" in reason:
                resolved_rule["reason"] = reason.format(
                    traffic_class=normalized_traffic,
                    priority=resolved_rule["priority"],
                )
            return resolved_rule

    # If no rule matched, return fallback
    return dict(FALLBACK_RULE)
