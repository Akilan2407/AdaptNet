"""Decision trace endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, error_response, item_response, success_response

traces_bp = Blueprint("traces", __name__, url_prefix="/traces")


@traces_bp.route("", methods=["GET"])
def get_traces():
    """Retrieve decision traces across all 7 pipeline stages."""
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    status = request.args.get("status", default=None, type=str)
    device_id = request.args.get("device_id", default=None, type=str)

    records, total = DataService.get_traces(
        limit=limit,
        offset=offset,
        status=status,
        device_id=device_id,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@traces_bp.route("/<trace_id>", methods=["GET"])
def get_trace(trace_id: str):
    """Retrieve complete structured decision trace for a single decision."""
    trace = DataService.get_trace_by_id(trace_id)
    if not trace:
        return error_response(f"Trace '{trace_id}' not found.", status_code=404)
    return item_response(trace)


@traces_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve trace completeness counts and stage match rate statistics."""
    summary = DataService.get_trace_summary()
    return success_response(summary)
