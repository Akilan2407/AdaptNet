"""Traffic classification endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response

classification_bp = Blueprint("classification", __name__, url_prefix="/classification")


@classification_bp.route("/flows", methods=["GET"])
def get_flows():
    """Retrieve classified network flows."""
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    traffic_class = request.args.get("traffic_class", default=None, type=str)
    device_id = request.args.get("device_id", default=None, type=str)

    records, total = DataService.get_classification_flows(
        limit=limit,
        offset=offset,
        traffic_class=traffic_class,
        device_id=device_id,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@classification_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve classification distributions and active classification rules."""
    summary = DataService.get_classification_summary()
    return success_response(summary)
