"""Device and user behavior profiling endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response

profiling_bp = Blueprint("profiling", __name__, url_prefix="/profiling")


@profiling_bp.route("/behaviors", methods=["GET"])
def get_behaviors():
    """Retrieve device behavior profiles and assigned clusters.

    Query params:
        limit (int): Max records (default: all).
        offset (int): Pagination offset (default 0).
        device_id (str): Filter by host identifier.
    """
    limit = request.args.get("limit", default=None, type=int)
    offset = request.args.get("offset", default=0, type=int)
    device_id = request.args.get("device_id", default=None, type=str)

    records, total = DataService.get_profiling_behaviors(
        limit=limit, offset=offset, device_id=device_id
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@profiling_bp.route("/clusters", methods=["GET"])
def get_clusters():
    """Retrieve clustering evaluation metrics, centroids, and feature definitions."""
    clusters_info = DataService.get_profiling_clusters()
    return success_response(clusters_info)
