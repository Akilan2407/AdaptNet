"""Natural-language explanation endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, error_response, item_response, success_response

explanations_bp = Blueprint("explanations", __name__, url_prefix="/explanations")


@explanations_bp.route("", methods=["GET"])
def get_explanations():
    """Retrieve natural-language decision explanations."""
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    status = request.args.get("status", default=None, type=str)
    device_id = request.args.get("device_id", default=None, type=str)

    records, total = DataService.get_explanations(
        limit=limit,
        offset=offset,
        status=status,
        device_id=device_id,
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
    """Retrieve natural-language explanation coverage, status distribution, and metrics."""
    summary = DataService.get_explanation_summary()
    return success_response(summary)
