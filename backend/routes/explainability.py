"""SHAP explainability endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response, error_response

explainability_bp = Blueprint("explainability", __name__, url_prefix="/explainability")

_VALID_SHAP_STATUSES = {"SUCCESS", "SKIPPED", "FAILED"}


@explainability_bp.route("/local", methods=["GET"])
def get_local():
    """Retrieve local SHAP feature attributions per decision.

    Query params:
        limit (int): Max records (default 50).
        offset (int): Pagination offset (default 0).
        trace_id (str): Filter to a specific decision trace.
        status (str): Filter by explanation_status (SUCCESS/SKIPPED/FAILED).
    """
    trace_id = request.args.get("trace_id", default=None, type=str)
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    status = request.args.get("status", default=None, type=str)

    if status and status.upper() not in _VALID_SHAP_STATUSES:
        return error_response(
            f"status must be one of: {', '.join(sorted(_VALID_SHAP_STATUSES))}.",
            status_code=400,
        )

    records, total = DataService.get_explainability_local(
        trace_id=trace_id,
        limit=limit,
        offset=offset,
        status=status,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@explainability_bp.route("/global", methods=["GET"])
def get_global():
    """Retrieve population-level global feature importance rankings (sorted by rank ascending)."""
    records, total = DataService.get_explainability_global()
    return collection_response(records, total=total)


@explainability_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve SHAP explainability execution summary with live status counts."""
    summary = DataService.get_explainability_summary()
    return success_response(summary)
