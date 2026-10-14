"""Traffic classification endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response, error_response

classification_bp = Blueprint("classification", __name__, url_prefix="/classification")

_VALID_SORT_COLS = {
    "timestamp", "classification_confidence", "throughput_mbps",
    "device_id", "traffic_class",
}


@classification_bp.route("/flows", methods=["GET"])
def get_flows():
    """Retrieve classified traffic flows.

    Query params:
        limit (int): Max records (default 50).
        offset (int): Pagination offset (default 0).
        traffic_class (str): Filter by traffic class (e.g. BULK_TRANSFER).
        device_id (str): Filter by host identifier.
        sort_by (str): Column to sort by.
        sort_order (str): 'asc' or 'desc'.
    """
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    traffic_class = request.args.get("traffic_class", default=None, type=str)
    device_id = request.args.get("device_id", default=None, type=str)
    sort_by = request.args.get("sort_by", default=None, type=str)
    sort_order = request.args.get("sort_order", default="asc", type=str)

    if sort_order not in ("asc", "desc"):
        return error_response("sort_order must be 'asc' or 'desc'.", status_code=400)

    effective_sort = sort_by if sort_by in _VALID_SORT_COLS else None

    records, total = DataService.get_classification_flows(
        limit=limit,
        offset=offset,
        traffic_class=traffic_class,
        device_id=device_id,
        sort_by=effective_sort,
        sort_order=sort_order,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@classification_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve classification summary, active rules, and live class distribution."""
    summary = DataService.get_classification_summary()
    return success_response(summary)
