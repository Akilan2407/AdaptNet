"""Adaptive traffic control endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response

control_bp = Blueprint("control", __name__, url_prefix="/control")


@control_bp.route("/actions", methods=["GET"])
def get_actions():
    """Retrieve audit log of traffic control shaping actions."""
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    status = request.args.get("status", default=None, type=str)
    device_id = request.args.get("device_id", default=None, type=str)

    records, total = DataService.get_control_actions(
        limit=limit,
        offset=offset,
        status=status,
        device_id=device_id,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@control_bp.route("/state", methods=["GET"])
def get_state():
    """Retrieve active traffic control rules applied across interfaces."""
    records, total = DataService.get_control_state()
    return collection_response(records, total=total)


@control_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve traffic control execution summary and status counts."""
    summary = DataService.get_control_summary()
    return success_response(summary)
