"""
Live Packet Capture REST API Endpoints.

Provides real-time packet event streaming, buffer inspection, and capture controls.
"""

from flask import Blueprint, jsonify, request
from backend.services.live_capture_service import live_capture_service
from backend.utils.serialization import collection_response, error_response, success_response

live_capture_bp = Blueprint("live_capture", __name__, url_prefix="/live")


@live_capture_bp.route("/stats", methods=["GET"])
def get_live_stats():
    """
    Retrieve current real-time packet capture status, counters, rates, and health.
    """
    stats = live_capture_service.get_stats()
    return success_response(stats)


@live_capture_bp.route("/packets", methods=["GET"])
def get_live_packets():
    """
    Retrieve buffered live packet events.

    Query params:
        limit (int): Number of packets (default 50, max 200).
        offset (int): Pagination offset (default 0).
        protocol (str): Optional filter ("TCP", "UDP", "ICMP", "ALL").
        q (str): Optional IP or port filter query.
    """
    try:
        limit = min(max(request.args.get("limit", default=50, type=int), 1), 200)
    except (ValueError, TypeError):
        limit = 50

    try:
        offset = max(request.args.get("offset", default=0, type=int), 0)
    except (ValueError, TypeError):
        offset = 0

    protocol = request.args.get("protocol", default=None, type=str)
    ip_query = request.args.get("q", default=None, type=str)

    packets, total = live_capture_service.get_packets(
        limit=limit,
        offset=offset,
        protocol=protocol,
        ip_query=ip_query,
    )

    response = collection_response(packets, total=total, limit=limit, offset=offset)
    # Add source tag indicating these are genuine live captured events
    if isinstance(response, tuple):
        json_resp, code = response
        data = json_resp.get_json()
        data["source"] = "live_wire_capture"
        data["live_active"] = live_capture_service.get_stats()["is_live"]
        return jsonify(data), code

    data = response.get_json()
    data["source"] = "live_wire_capture"
    data["live_active"] = live_capture_service.get_stats()["is_live"]
    return jsonify(data), 200


@live_capture_bp.route("/start", methods=["POST"])
def start_capture():
    """
    Start the live packet sniffer.

    JSON payload (optional):
        interface (str): Network interface name (default: auto-detect)
        filter (str): BPF capture filter (e.g., 'tcp', 'port 80')
    """
    body = request.get_json(silent=True) or {}
    interface = body.get("interface")
    bpf_filter = body.get("filter", "")

    ok, message = live_capture_service.start(interface=interface, bpf_filter=bpf_filter)
    if not ok:
        return error_response(message, status_code=400)

    return success_response({"message": message, "stats": live_capture_service.get_stats()})


@live_capture_bp.route("/stop", methods=["POST"])
def stop_capture():
    """Stop the live packet sniffer."""
    ok, message = live_capture_service.stop()
    if not ok:
        return error_response(message, status_code=500)

    return success_response({"message": message, "stats": live_capture_service.get_stats()})


@live_capture_bp.route("/clear", methods=["POST"])
def clear_buffer():
    """Clear the live packet circular buffer."""
    live_capture_service.clear()
    return success_response({"message": "Buffer cleared", "stats": live_capture_service.get_stats()})


@live_capture_bp.route("/interfaces", methods=["GET"])
def get_interfaces():
    """List available network interfaces for live packet sniffing."""
    ifaces = live_capture_service.get_available_interfaces()
    return success_response({"interfaces": ifaces, "count": len(ifaces)})


# ── Real-Time ML Pipeline Endpoints ──────────────────────────────────────────

@live_capture_bp.route("/pipeline/status", methods=["GET"])
def get_pipeline_status():
    """Retrieve real-time ML processing pipeline operational status."""
    from ml.realtime.pipeline_manager import pipeline_manager
    status = pipeline_manager.get_status()
    capture_stats = live_capture_service.get_stats()
    status["capture_active"] = capture_stats.get("is_live", False) or capture_stats.get("status") == "LIVE"
    status["capture_interface"] = capture_stats.get("interface")
    return success_response(status)


@live_capture_bp.route("/pipeline/flows", methods=["GET"])
def get_pipeline_flows():
    """Retrieve recent live aggregated network flows with ML predictions."""
    from ml.realtime.pipeline_manager import pipeline_manager
    limit = min(max(request.args.get("limit", default=50, type=int), 1), 200)
    offset = max(request.args.get("offset", default=0, type=int), 0)
    device_id = request.args.get("device_id", default=None, type=str)

    flows, total = pipeline_manager.get_live_flows(limit=limit, offset=offset, device_id=device_id)
    return collection_response(flows, total=total, limit=limit, offset=offset)


@live_capture_bp.route("/pipeline/predictions", methods=["GET"])
def get_pipeline_predictions():
    """Retrieve latest real-time ML inference predictions across all models."""
    from ml.realtime.pipeline_manager import pipeline_manager
    limit = min(max(request.args.get("limit", default=50, type=int), 1), 200)
    offset = max(request.args.get("offset", default=0, type=int), 0)
    device_id = request.args.get("device_id", default=None, type=str)
    c_class = request.args.get("congestion_class", default=None, type=str)

    preds, total = pipeline_manager.get_live_predictions(
        limit=limit, offset=offset, device_id=device_id, congestion_class=c_class
    )
    return collection_response(preds, total=total, limit=limit, offset=offset)


@live_capture_bp.route("/pipeline/traces", methods=["GET"])
def get_pipeline_traces():
    """Retrieve recent live 7-stage decision traces."""
    from ml.realtime.pipeline_manager import pipeline_manager
    limit = min(max(request.args.get("limit", default=50, type=int), 1), 200)
    offset = max(request.args.get("offset", default=0, type=int), 0)
    trace_id = request.args.get("trace_id", default=None, type=str)

    traces, total = pipeline_manager.get_live_traces(limit=limit, offset=offset, trace_id=trace_id)
    return collection_response(traces, total=total, limit=limit, offset=offset)


@live_capture_bp.route("/pipeline/clear", methods=["POST"])
def clear_pipeline():
    """Clear in-memory real-time ML pipeline buffers."""
    from ml.realtime.pipeline_manager import pipeline_manager
    pipeline_manager.clear()
    return success_response({"message": "Real-time ML pipeline buffers cleared."})

