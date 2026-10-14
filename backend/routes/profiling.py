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
        source (str): 'historical' or 'live'.
    """
    source = request.args.get("source", default="historical", type=str).lower()
    limit = request.args.get("limit", default=None, type=int)
    offset = request.args.get("offset", default=0, type=int)
    device_id = request.args.get("device_id", default=None, type=str)

    if source == "live":
        from ml.realtime.pipeline_manager import pipeline_manager
        flows, _ = pipeline_manager.get_live_flows(limit=500)
        # Aggregate flows by device_id
        dev_map = {}
        cluster_labels = {
            0: "High-Throughput",
            1: "Baseline-Activity (C1)",
            2: "Baseline-Activity (C2)",
            3: "Low-Bandwidth (C3)",
        }
        for f in flows:
            did = f.get("device_id", "h_local")
            if device_id and did != device_id:
                continue
            if did not in dev_map:
                cid = f.get("cluster_id", 0)
                dev_map[did] = {
                    "device_id": did,
                    "cluster_id": cid,
                    "profile_label": cluster_labels.get(cid, f"Cluster {cid}"),
                    "mean_throughput_mbps": f.get("throughput_mbps", 0.0),
                    "max_throughput_mbps": f.get("throughput_mbps", 0.0),
                    "min_throughput_mbps": f.get("throughput_mbps", 0.0),
                    "throughput_std": 0.0,
                    "mean_rtt_ms": f.get("rtt_ms") or 15.0,
                    "max_rtt_ms": f.get("rtt_ms") or 15.0,
                    "rtt_std": 0.0,
                    "mean_packet_loss_percent": f.get("packet_loss_percent", 0.0),
                    "max_packet_loss_percent": f.get("packet_loss_percent", 0.0),
                    "packet_loss_std": 0.0,
                    "mean_active_connections": f.get("active_connections", 1),
                    "total_flow_count": 0,
                    "tcp_flow_count": 0,
                    "udp_flow_count": 0,
                    "tcp_flow_ratio": 1.0,
                    "udp_flow_ratio": 0.0,
                    "active_hours_count": 1,
                }
            entry = dev_map[did]
            entry["total_flow_count"] += 1
            if f.get("protocol") == "UDP":
                entry["udp_flow_count"] += 1
            else:
                entry["tcp_flow_count"] += 1
            t_rate = f.get("throughput_mbps", 0.0) or 0.0
            if t_rate > entry["max_throughput_mbps"]:
                entry["max_throughput_mbps"] = t_rate
            if t_rate < entry["min_throughput_mbps"]:
                entry["min_throughput_mbps"] = t_rate

        live_records = list(dev_map.values())
        for r in live_records:
            if r["total_flow_count"] > 0:
                r["tcp_flow_ratio"] = round(r["tcp_flow_count"] / r["total_flow_count"], 2)
                r["udp_flow_ratio"] = round(r["udp_flow_count"] / r["total_flow_count"], 2)
        total = len(live_records)
        if offset:
            live_records = live_records[offset:]
        if limit:
            live_records = live_records[:limit]
        return collection_response(live_records, total=total, limit=limit, offset=offset)

    records, total = DataService.get_profiling_behaviors(
        limit=limit, offset=offset, device_id=device_id
    )
    return collection_response(records, total=total, limit=limit, offset=offset)


@profiling_bp.route("/clusters", methods=["GET"])
def get_clusters():
    """Retrieve clustering evaluation metrics, centroids, and feature definitions."""
    clusters_info = DataService.get_profiling_clusters()
    return success_response(clusters_info)
