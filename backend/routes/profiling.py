"""Device and user behavior profiling endpoints for Phase 18 Flask API."""

from flask import Blueprint
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response

profiling_bp = Blueprint("profiling", __name__, url_prefix="/profiling")


@profiling_bp.route("/behaviors", methods=["GET"])
def get_behaviors():
    """Retrieve device behavior profiles and assigned clusters."""
    records, total = DataService.get_profiling_behaviors()
    return collection_response(records, total=total)


@profiling_bp.route("/clusters", methods=["GET"])
def get_clusters():
    """Retrieve clustering evaluation metrics, centroids, and feature definitions."""
    clusters_info = DataService.get_profiling_clusters()
    return success_response(clusters_info)
