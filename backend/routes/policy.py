"""QoS policy engine endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response

policy_bp = Blueprint("policy", __name__, url_prefix="/policy")


@policy_bp.route("/decisions", methods=["GET"])
def get_decisions():
    """Retrieve deterministic QoS policy decisions."""
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    priority = request.args.get("priority", default=None, type=str)
    device_id = request.args.get("device_id", default=None, type=str)

    records, total = DataService.get_policy_decisions(
        limit=limit,
        offset=offset,
        priority=priority,
        device_id=device_id,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@policy_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve policy decision distribution and rule frequency metrics."""
    summary = DataService.get_policy_summary()
    return success_response(summary)
