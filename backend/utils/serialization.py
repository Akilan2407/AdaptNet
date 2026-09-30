"""Serialization and JSON response formatting utilities for Phase 18 Flask API.

Ensures strict JSON compliance by safely converting:
- NumPy integers and floats -> Python int / float
- NaN and Infinity -> null (None)
- Pandas Timestamps and datetime -> ISO-8601 strings
- NumPy ndarrays -> Python lists
- Dictionaries and lists sanitized recursively
"""

from datetime import date, datetime
import math
from typing import Any, Dict, List, Optional, Tuple, Union
from flask import Response, jsonify
import numpy as np
import pandas as pd


def sanitize_value(val: Any) -> Any:
    """Recursively sanitize data into JSON-compliant Python primitives."""
    if val is None:
        return None

    # Handle dictionaries first
    if isinstance(val, dict):
        return {str(k): sanitize_value(v) for k, v in val.items()}

    # Handle lists / tuples / sets
    if isinstance(val, (list, tuple, set)):
        return [sanitize_value(v) for v in val]

    # Handle numpy ndarray
    if isinstance(val, np.ndarray):
        return [sanitize_value(v) for v in val.tolist()]

    # Handle strings directly
    if isinstance(val, str):
        return val

    # Handle Datetime / Timestamp / Date
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return val.isoformat()

    # Handle bool / numpy bool (must be checked before int as bool is a subclass of int)
    if isinstance(val, (bool, np.bool_)):
        return bool(val)

    # Handle integer / numpy integer
    if isinstance(val, (int, np.integer)):
        return int(val)

    # Handle float / numpy float
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)

    # Handle Pandas NA / NaT singleton
    if val is pd.NA:
        return None

    try:
        if pd.isna(val):
            return None
    except Exception:
        pass

    return val


def success_response(data: Any, status_code: int = 200) -> Tuple[Response, int]:
    """Return sanitized JSON response with HTTP status code."""
    sanitized = sanitize_value(data)
    if isinstance(sanitized, dict) and "status" not in sanitized:
        sanitized["status"] = "success"
    return jsonify(sanitized), status_code


def collection_response(
    items: List[Dict[str, Any]],
    total: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> Tuple[Response, int]:
    """Return standard collection response matching Phase 18 specification.

    Format:
    {
        "status": "success",
        "count": 10,
        "total": 100,
        "data": [...]
    }
    """
    sanitized_items = sanitize_value(items)
    res_payload: Dict[str, Any] = {
        "status": "success",
        "count": len(sanitized_items),
        "data": sanitized_items,
    }

    if total is not None:
        res_payload["total"] = int(total)
    if limit is not None:
        res_payload["limit"] = int(limit)
    if offset is not None:
        res_payload["offset"] = int(offset)

    if extra_fields:
        for k, v in extra_fields.items():
            res_payload[k] = sanitize_value(v)

    return jsonify(res_payload), status_code


def item_response(item: Dict[str, Any], status_code: int = 200) -> Tuple[Response, int]:
    """Return standard single item response."""
    sanitized = sanitize_value(item)
    payload: Dict[str, Any] = {
        "status": "success",
        "data": sanitized,
    }
    return jsonify(payload), status_code


def error_response(message: str, status_code: int = 400) -> Tuple[Response, int]:
    """Return standard error response matching Phase 18 specification.

    Format:
    {
        "status": "error",
        "error": "Description of the problem"
    }
    """
    return jsonify({"status": "error", "error": str(message)}), status_code
