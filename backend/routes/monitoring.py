"""Network monitoring and telemetry endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response

monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/monitoring")


@monitoring_bp.route("/flows", methods=["GET"])
def get_flows():
    """Retrieve network telemetry and flow records."""
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    device_id = request.args.get("device_id", default=None, type=str)

    records, total = DataService.get_monitoring_flows(
        limit=limit, offset=offset, device_id=device_id
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@monitoring_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve aggregate telemetry metrics and averages."""
    summary = DataService.get_monitoring_summary()
    return success_response(summary)
