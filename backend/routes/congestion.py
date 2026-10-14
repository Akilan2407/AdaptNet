"""Congestion prediction and evaluation endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response, error_response

congestion_bp = Blueprint("congestion", __name__, url_prefix="/congestion")

_VALID_CLASSES = {"LOW", "MEDIUM", "HIGH", "UNKNOWN"}
_VALID_SORT_COLS = {"sequence_id", "predicted_score", "actual_score", "absolute_error", "device_id"}


@congestion_bp.route("/predictions", methods=["GET"])
def get_predictions():
    """Retrieve GRU model congestion forecast predictions.

    Query params:
        limit (int): Max records (default 50).
        offset (int): Pagination offset (default 0).
        device_id (str): Filter by host identifier.
        congestion_class (str): Filter by predicted class (LOW/MEDIUM/HIGH/UNKNOWN).
        sort_by (str): Column to sort by.
        sort_order (str): 'asc' or 'desc'.
    """
    source = request.args.get("source", default="historical", type=str).lower()
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    device_id = request.args.get("device_id", default=None, type=str)
    congestion_class = request.args.get("congestion_class", default=None, type=str)
    sort_by = request.args.get("sort_by", default=None, type=str)
    sort_order = request.args.get("sort_order", default="asc", type=str)

    if sort_order not in ("asc", "desc"):
        return error_response("sort_order must be 'asc' or 'desc'.", status_code=400)

    if congestion_class and congestion_class.upper() not in _VALID_CLASSES:
        return error_response(
            f"congestion_class must be one of: {', '.join(sorted(_VALID_CLASSES))}.",
            status_code=400,
        )

    # Handle live packet pipeline source
    if source == "live":
        from ml.realtime.pipeline_manager import pipeline_manager
        records, total = pipeline_manager.get_live_predictions(
            limit=limit,
            offset=offset,
            device_id=device_id,
            congestion_class=congestion_class,
        )
        return collection_response(records, total=total, limit=limit, offset=offset)

    effective_sort = sort_by if sort_by in _VALID_SORT_COLS else None

    records, total = DataService.get_congestion_predictions(
        limit=limit,
        offset=offset,
        device_id=device_id,
        congestion_class=congestion_class,
        sort_by=effective_sort,
        sort_order=sort_order,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@congestion_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve model evaluation metrics, dataset statistics, baseline comparisons,
    and prediction class distribution."""
    source = request.args.get("source", default="historical", type=str).lower()
    if source == "live":
        from ml.realtime.pipeline_manager import pipeline_manager
        preds, total = pipeline_manager.get_live_predictions(limit=500)
        dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        scores = []
        for p in preds:
            c = p.get("predicted_congestion_class", "LOW")
            dist[c] = dist.get(c, 0) + 1
            s = p.get("predicted_congestion_score")
            if s is not None:
                scores.append(s)
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        max_score = round(max(scores), 4) if scores else 0.0
        summary = DataService.get_congestion_summary()
        summary = dict(summary)
        summary["source"] = "live_packet_capture"
        summary["live_metrics"] = {
            "total_live_predictions": total,
            "mean_congestion_score": avg_score,
            "max_congestion_score": max_score,
            "class_distribution": dist,
        }
        return success_response(summary)

    summary = DataService.get_congestion_summary()
    return success_response(summary)
