"""Priority conversion, arithmetic, and boundary clamping helpers for Phase 13 QoS Policy Engine.

Scale:
    0 = LOW
    1 = NORMAL
    2 = MEDIUM
    3 = HIGH
"""

from pathlib import Path
import sys
from typing import Tuple, Union

# Ensure project root is in sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from ml.policy.config import PRIORITY_LEVELS, PRIORITY_TO_NUMERIC, NUMERIC_TO_PRIORITY, DEFAULT_PRIORITY


def clamp_numeric(value: int, min_val: int = 0, max_val: int = 3) -> int:
    """Clamp an integer value within [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def priority_to_numeric(priority: str) -> int:
    """Convert a priority string label to its internal numeric value (0-3).

    Args:
        priority: Priority label string ('LOW', 'NORMAL', 'MEDIUM', 'HIGH').

    Returns:
        Integer priority between 0 and 3.

    Raises:
        ValueError: If priority is not in PRIORITY_LEVELS.
    """
    if not isinstance(priority, str):
        raise ValueError(f"Priority must be a string, got {type(priority).__name__}: {priority}")
    upper_p = priority.upper().strip()
    if upper_p not in PRIORITY_TO_NUMERIC:
        raise ValueError(
            f"Invalid priority label '{priority}'. Must be one of {PRIORITY_LEVELS}."
        )
    return PRIORITY_TO_NUMERIC[upper_p]


def numeric_to_priority(value: Union[int, float]) -> str:
    """Convert a numeric value to its corresponding priority label, clamped to [0, 3].

    Args:
        value: Numeric priority value. Floats will be rounded to nearest integer.

    Returns:
        Priority label string ('LOW', 'NORMAL', 'MEDIUM', or 'HIGH').
    """
    try:
        int_val = int(round(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Cannot convert {value} to integer priority: {exc}") from exc

    clamped = clamp_numeric(int_val, 0, 3)
    return NUMERIC_TO_PRIORITY[clamped]


def apply_priority_adjustment(base_priority: str, adjustment: int) -> Tuple[str, int]:
    """Apply an integer adjustment to a base priority and clamp within [0, 3].

    Args:
        base_priority: Base priority label ('LOW', 'NORMAL', 'MEDIUM', 'HIGH').
        adjustment: Integer increment/decrement (e.g. +1, -1, 0).

    Returns:
        Tuple of (clamped_priority_label, clamped_numeric_value).
    """
    base_num = priority_to_numeric(base_priority)
    new_num = clamp_numeric(base_num + int(adjustment), 0, 3)
    new_priority = numeric_to_priority(new_num)
    return new_priority, new_num
