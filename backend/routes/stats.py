"""Aggregate statistics endpoint — single-call dashboard metrics.

Returns a consolidated payload combining KPIs from all 9 modules.
This avoids the React frontend from making 6 parallel requests on
initial dashboard load.
"""

from flask import Blueprint
from backend.services.data_service import DataService
from backend.utils.serialization import success_response

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/stats", methods=["GET"])
def get_stats():
    """Return consolidated dashboard KPIs from all pipeline modules in a single response.

    Response shape:
    {
      "status": "success",
      "monitoring": { total_records, unique_devices, avg_throughput_mbps, ... },
      "congestion":  { mae, rmse, r2, test_samples },
      "policy":      { total_decisions, priority_distribution },
      "control":     { total_applied, dry_run_operations, control_success_rate },
      "traces":      { total_traces, complete_traces, trace_completeness_rate },
      "explainability": { explainer_type, feature_count, total_explained }
    }
    """
    stats = DataService.get_aggregate_stats()
    return success_response(stats)
