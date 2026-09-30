"""Congestion prediction and evaluation endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response

congestion_bp = Blueprint("congestion", __name__, url_prefix="/congestion")


@congestion_bp.route("/predictions", methods=["GET"])
def get_predictions():
    """Retrieve GRU model congestion forecast predictions."""
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    device_id = request.args.get("device_id", default=None, type=str)

    records, total = DataService.get_congestion_predictions(
        limit=limit, offset=offset, device_id=device_id
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@congestion_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve model evaluation metrics, dataset statistics, and baseline model comparisons."""
    summary = DataService.get_congestion_summary()
    return success_response(summary)
