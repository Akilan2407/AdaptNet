"""QoS policy decision endpoints for Phase 18 Flask API."""

from flask import Blueprint, request
from backend.services.data_service import DataService
from backend.utils.serialization import collection_response, success_response, error_response

policy_bp = Blueprint("policy", __name__, url_prefix="/policy")

_VALID_PRIORITIES = {"LOW", "NORMAL", "MEDIUM", "HIGH"}
_VALID_SORT_COLS = {
    "timestamp", "final_priority", "device_id",
    "traffic_class", "policy_rule_id",
}


@policy_bp.route("/decisions", methods=["GET"])
def get_decisions():
    """Retrieve QoS policy decisions.

    Query params:
        limit (int): Max records (default 50).
        offset (int): Pagination offset (default 0).
        priority (str): Filter by final_priority (LOW/NORMAL/MEDIUM/HIGH).
        device_id (str): Filter by host identifier.
        rule_id (str): Filter by policy_rule_id.
        sort_by (str): Column to sort by.
        sort_order (str): 'asc' or 'desc'.
    """
    source = request.args.get("source", default="historical", type=str).lower()
    limit = request.args.get("limit", default=50, type=int)
    offset = request.args.get("offset", default=0, type=int)
    priority = request.args.get("priority", default=None, type=str)
    device_id = request.args.get("device_id", default=None, type=str)
    rule_id = request.args.get("rule_id", default=None, type=str)
    sort_by = request.args.get("sort_by", default=None, type=str)
    sort_order = request.args.get("sort_order", default="asc", type=str)

    if sort_order not in ("asc", "desc"):
        return error_response("sort_order must be 'asc' or 'desc'.", status_code=400)

    if priority and priority.upper() not in _VALID_PRIORITIES:
        return error_response(
            f"priority must be one of: {', '.join(sorted(_VALID_PRIORITIES))}.",
            status_code=400,
        )

    # Handle live packet pipeline source
    if source == "live":
        from ml.realtime.pipeline_manager import pipeline_manager
        preds, total = pipeline_manager.get_live_predictions(
            limit=limit,
            offset=offset,
            device_id=device_id,
        )
        if priority:
            preds = [p for p in preds if p.get("final_priority") == priority.upper()]
            total = len(preds)
        return collection_response(preds, total=total, limit=limit, offset=offset)

    effective_sort = sort_by if sort_by in _VALID_SORT_COLS else None

    records, total = DataService.get_policy_decisions(
        limit=limit,
        offset=offset,
        priority=priority,
        device_id=device_id,
        rule_id=rule_id,
        sort_by=effective_sort,
        sort_order=sort_order,
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@policy_bp.route("/summary", methods=["GET"])
def get_summary():
    """Retrieve QoS policy decision distribution, rule statistics, and live rule usage."""
    source = request.args.get("source", default="historical", type=str).lower()
    if source == "live":
        from ml.realtime.pipeline_manager import pipeline_manager
        preds, total = pipeline_manager.get_live_predictions(limit=500)
        dist = {"CRITICAL": 0, "HIGH": 0, "NORMAL": 0, "LOW": 0}
        rules_used = {}
        for p in preds:
            pri = p.get("final_priority", "NORMAL")
            dist[pri] = dist.get(pri, 0) + 1
            rid = p.get("rule_id", "POLICY_DEFAULT")
            rules_used[rid] = rules_used.get(rid, 0) + 1
        return success_response({
            "source": "live_packet_capture",
            "total_decisions": total,
            "priority_distribution": dist,
            "rule_usage": rules_used,
            "active_rules_count": len(rules_used),
        })

    summary = DataService.get_policy_summary()
    return success_response(summary)
