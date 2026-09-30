"""Explainable decision reason synthesis for Phase 13 QoS Policy Engine.

Constructs clear, deterministic, human-readable explanations detailing
the traffic category, predicted congestion state, matched rule, and any applied profile adjustments.
"""

from typing import Optional


def format_decision_reason(
    base_reason: str,
    base_priority: str,
    user_profile_adjustment: int,
    final_priority: str,
    cluster_id: Optional[int] = None,
) -> str:
    """Format an explainable, human-readable decision reason string.

    Args:
        base_reason: Reason generated from matched traffic/congestion rule.
        base_priority: Priority before user-profile adjustment.
        user_profile_adjustment: Integer adjustment (-1, 0, +1) from behavior profile.
        final_priority: Final clamped priority label.
        cluster_id: Device's behavior cluster ID if available.

    Returns:
        Structured, human-readable explanation string.
    """
    if user_profile_adjustment == 0:
        return base_reason

    # Format user-profile adjustment detail
    adj_str = f"+{user_profile_adjustment}" if user_profile_adjustment > 0 else str(user_profile_adjustment)
    cluster_desc = f"cluster {cluster_id}" if cluster_id is not None else "user profile"

    if base_priority == final_priority:
        profile_note = (
            f" Base priority {base_priority} was adjusted by {adj_str} ({cluster_desc}), "
            f"remaining at {final_priority} due to boundary limits."
        )
    else:
        direction = "increased" if user_profile_adjustment > 0 else "decreased"
        profile_note = (
            f" Base priority {base_priority} was {direction} to {final_priority} "
            f"because the configured user-profile adjustment was {adj_str} ({cluster_desc})."
        )

    return f"{base_reason}{profile_note}".strip()
