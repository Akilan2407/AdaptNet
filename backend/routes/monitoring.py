"""Network monitoring and telemetry endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response, error_response

monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/monitoring")

_VALID_SORT_COLS = {
    "timestamp", "throughput_mbps", "rtt_ms", "packet_loss_percent",
    "active_connections", "device_id", "total_flow_count",
}


@monitoring_bp.route("/flows", methods=["GET"])
def get_flows():
    """Retrieve network telemetry and flow records.

    Query params:
        limit (int): Max records (default 50).
        offset (int): Pagination offset (default 0).
        device_id (str): Filter by host identifier.
        sort_by (str): Column to sort by (default: timestamp).
        sort_order (str): 'asc' or 'desc' (default: desc).
    """
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    device_id = request.args.get("device_id", default=None, type=str)
    sort_by = request.args.get("sort_by", default="timestamp", type=str)
    sort_order = request.args.get("sort_order", default="desc", type=str)

    # Validate sort_order
    if sort_order not in ("asc", "desc"):
        return error_response("sort_order must be 'asc' or 'desc'.", status_code=400)

    # Validate sort_by column
    effective_sort = sort_by if sort_by in _VALID_SORT_COLS else "timestamp"

    records, total = DataService.get_monitoring_flows(
        limit=limit,
        offset=offset,
        device_id=device_id,
        sort_by=effective_sort,
        sort_order=sort_order,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@monitoring_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve enhanced aggregate telemetry metrics and per-device breakdown."""
    summary = DataService.get_monitoring_summary()
    return success_response(summary)


@monitoring_bp.route("/search", methods=["GET"])
def search_flows():
    """Full-text search across flow records.

    Query params:
        q (str): Search query (min 2 chars). Matches device_id, src_ip, dst_ip, flow_id.
        limit (int): Max results (default 20, max 100).
    """
    q = request.args.get("q", default="", type=str).strip()
    limit = min(request.args.get("limit", default=20, type=int), 100)

    if len(q) < 2:
        return error_response("Query 'q' must be at least 2 characters.", status_code=400)

    results = DataService.search_flows(q, limit=limit)
    return collection_response(results, total=len(results), limit=limit, offset=0)
