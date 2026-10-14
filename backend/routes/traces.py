"""Decision trace endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import (
    collection_response,
    error_response,
    item_response,
    success_response,
)

traces_bp = Blueprint("traces", __name__, url_prefix="/traces")

_VALID_STATUSES = {"COMPLETE", "PARTIAL"}
_VALID_SORT_COLS = {
    "timestamp", "trace_completeness", "device_id", "trace_id",
    "congestion_match_rate", "final_priority",
}


@traces_bp.route("", methods=["GET"])
def get_traces():
    """Retrieve decision traces across all 7 pipeline stages.

    Query params:
        limit (int): Max records (default 50).
        offset (int): Pagination offset (default 0).
        status (str): Filter by trace_completeness (COMPLETE/PARTIAL).
        device_id (str): Filter by host identifier.
        sort_by (str): Column to sort by.
        sort_order (str): 'asc' or 'desc'.
    """
    source = request.args.get("source", default="historical", type=str).lower()
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

    # Handle live packet pipeline source
    if source == "live":
        from ml.realtime.pipeline_manager import pipeline_manager
        traces, total = pipeline_manager.get_live_traces(limit=limit, offset=offset)
        return collection_response(traces, total=total, limit=limit, offset=offset)

    effective_sort = sort_by if sort_by in _VALID_SORT_COLS else None

    records, total = DataService.get_traces(
        limit=limit,
        offset=offset,
        status=status,
        device_id=device_id,
        sort_by=effective_sort,
        sort_order=sort_order,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@traces_bp.route("/<trace_id>", methods=["GET"])
def get_trace(trace_id: str):
    """Retrieve complete structured decision trace for a single decision."""
    if trace_id.startswith("TRC-LIVE-"):
        from ml.realtime.pipeline_manager import pipeline_manager
        traces, _ = pipeline_manager.get_live_traces(limit=1, offset=0, trace_id=trace_id)
        if traces:
            return item_response(traces[0])
        return error_response(f"Live trace '{trace_id}' not found.", status_code=404)

    trace = DataService.get_trace_by_id(trace_id)
    if not trace:
        return error_response(f"Trace '{trace_id}' not found.", status_code=404)
    return item_response(trace)


@traces_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve trace completeness counts, stage match rates, and live completeness distribution."""
    summary = DataService.get_trace_summary()
    return success_response(summary)
