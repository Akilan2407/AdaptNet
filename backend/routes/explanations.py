"""Natural-language explanation endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import (
    collection_response,
    error_response,
    item_response,
    success_response,
)

explanations_bp = Blueprint("explanations", __name__, url_prefix="/explanations")

_VALID_STATUSES = {"COMPLETE", "PARTIAL", "SKIPPED", "FAILED"}
_VALID_SORT_COLS = {
    "timestamp", "explanation_status", "device_id", "trace_id", "final_priority",
}


@explanations_bp.route("", methods=["GET"])
def get_explanations():
    """Retrieve natural-language decision explanations.

    Query params:
        limit (int): Max records (default 50).
        offset (int): Pagination offset (default 0).
        status (str): Filter by explanation_status (COMPLETE/PARTIAL/SKIPPED/FAILED).
        device_id (str): Filter by host identifier.
        sort_by (str): Column to sort by.
        sort_order (str): 'asc' or 'desc'.
    """
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    status = request.args.get("status", default=None, type=str)
    device_id = request.args.get("device_id", default=None, type=str)
    sort_by = request.args.get("sort_by", default=None, type=str)
    sort_order = request.args.get("sort_order", default="asc", type=str)

    if sort_order not in ("asc", "desc"):
        return error_response("sort_order must be 'asc' or 'desc'.", status_code=400)

    if status and status.upper() not in _VALID_STATUSES:
        return error_response(
            f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}.",
            status_code=400,
        )

    effective_sort = sort_by if sort_by in _VALID_SORT_COLS else None

    records, total = DataService.get_explanations(
        limit=limit,
        offset=offset,
        status=status,
        device_id=device_id,
        sort_by=effective_sort,
        sort_order=sort_order,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@explanations_bp.route("/<trace_id>", methods=["GET"])
def get_explanation(trace_id: str):
    """Retrieve single natural-language explanation record by trace_id."""
    record = DataService.get_explanation_by_id(trace_id)
    if not record:
        return error_response(f"Explanation for trace '{trace_id}' not found.", status_code=404)
    return item_response(record)


@explanations_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve natural-language explanation coverage, status distribution, and live metrics."""
    summary = DataService.get_explanation_summary()
    return success_response(summary)
