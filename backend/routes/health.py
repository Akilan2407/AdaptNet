"""Health check endpoint for Phase 18 Flask API.

Improved: Reports real data-file readiness per module, server uptime,
and timestamp rather than hardcoded 'ready' for every module.
"""

import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint
from backend.utils.serialization import success_response
import backend.config as cfg

health_bp = Blueprint("health", __name__)

# Record startup time
_START_TIME = time.monotonic()
_START_DT = datetime.now(timezone.utc)

# Map module name → list of data files that must exist to be "ready"
_MODULE_FILES: dict = {
    "monitoring": [cfg.MONITORING_METRICS_CSV],
    "profiling": [cfg.BEHAVIOR_PROFILES_CSV, cfg.CLUSTER_SUMMARY_CSV],
    "congestion": [cfg.CONGESTION_PREDICTIONS_CSV, cfg.CONGESTION_MODEL_EVAL_JSON],
    "classification": [cfg.CLASSIFIED_FLOWS_CSV, cfg.CLASSIFICATION_SUMMARY_JSON],
    "policy": [cfg.POLICY_DECISIONS_CSV, cfg.POLICY_SUMMARY_JSON],
    "control": [cfg.CONTROL_ACTIONS_CSV, cfg.CONTROL_SUMMARY_JSON],
    "traces": [cfg.DECISION_TRACES_CSV, cfg.TRACE_SUMMARY_JSON],
    "explainability": [cfg.EXPLAINABILITY_GLOBAL_CSV, cfg.EXPLAINABILITY_SUMMARY_JSON],
    "explanations": [cfg.NATURAL_LANGUAGE_CSV, cfg.EXPLANATION_SUMMARY_JSON],
}


def _check_module(files: list) -> dict:
    """Return module status dict with ready/degraded/unavailable and missing files."""
    missing = [str(Path(f).name) for f in files if not Path(f).exists()]
    if not missing:
        return {"status": "ready", "missing_files": []}
    if len(missing) < len(files):
        return {"status": "degraded", "missing_files": missing}
    return {"status": "unavailable", "missing_files": missing}


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Service health with per-module data-file readiness, uptime, and timestamp."""
    uptime_seconds = round(time.monotonic() - _START_TIME, 1)

    modules = {name: _check_module(files) for name, files in _MODULE_FILES.items()}
    all_statuses = [m["status"] for m in modules.values()]

    if all(s == "ready" for s in all_statuses):
        overall = "healthy"
    elif all(s == "unavailable" for s in all_statuses):
        overall = "unhealthy"
    else:
        overall = "degraded"

    return success_response({
        "status": overall,
        "service": "network-management-api",
        "version": "1.0.0",
        "uptime_seconds": uptime_seconds,
        "started_at": _START_DT.isoformat(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modules": modules,
    })
