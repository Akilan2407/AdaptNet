"""Adaptive traffic control endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response, error_response

control_bp = Blueprint("control", __name__, url_prefix="/control")

_VALID_STATUSES = {"APPLIED", "SKIPPED", "FAILED", "DRY_RUN"}
_VALID_SORT_COLS = {
    "timestamp", "status", "device_id", "interface",
    "final_priority", "action",
}


@control_bp.route("/actions", methods=["GET"])
def get_actions():
    """Retrieve audit log of traffic control shaping actions.

    Query params:
        limit (int): Max records (default 50).
        offset (int): Pagination offset (default 0).
        status (str): Filter by status (APPLIED/SKIPPED/FAILED/DRY_RUN).
        device_id (str): Filter by host identifier.
        sort_by (str): Column to sort by (default: timestamp desc).
        sort_order (str): 'asc' or 'desc'.
    """
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    status = request.args.get("status", default=None, type=str)
    device_id = request.args.get("device_id", default=None, type=str)
    sort_by = request.args.get("sort_by", default="timestamp", type=str)
    sort_order = request.args.get("sort_order", default="desc", type=str)

    if sort_order not in ("asc", "desc"):
        return error_response("sort_order must be 'asc' or 'desc'.", status_code=400)

    if status and status.upper() not in _VALID_STATUSES:
        return error_response(
            f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}.",
            status_code=400,
        )

    effective_sort = sort_by if sort_by in _VALID_SORT_COLS else "timestamp"

    records, total = DataService.get_control_actions(
        limit=limit,
        offset=offset,
        status=status,
        device_id=device_id,
        sort_by=effective_sort,
        sort_order=sort_order,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@control_bp.route("/state", methods=["GET"])
def get_state():
    """Retrieve active traffic control rules applied across interfaces.

    Query params:
        limit (int): Max records (default: all).
        offset (int): Pagination offset (default 0).
    """
    limit = request.args.get("limit", default=None, type=int)
    offset = request.args.get("offset", default=0, type=int)

    records, total = DataService.get_control_state(limit=limit, offset=offset)
    return collection_response(records, total=total, limit=limit, offset=offset)


@control_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve traffic control execution summary, status counts, and live status breakdown."""
    summary = DataService.get_control_summary()
    return success_response(summary)
