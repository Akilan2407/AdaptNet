"""SHAP explainability endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response

explainability_bp = Blueprint("explainability", __name__, url_prefix="/explainability")


@explainability_bp.route("/local", methods=["GET"])
def get_local():
    """Retrieve local SHAP feature attributions per decision."""
    trace_id = request.args.get("trace_id", default=None, type=str)
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)

    records, total = DataService.get_explainability_local(
        trace_id=trace_id, limit=limit, offset=offset
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@explainability_bp.route("/global", methods=["GET"])
def get_global():
    """Retrieve population-level global feature importance rankings."""
    records, total = DataService.get_explainability_global()
    return collection_response(records, total=total)


@explainability_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve SHAP explainability execution summary, explainer type, and metrics."""
    summary = DataService.get_explainability_summary()
    return success_response(summary)
