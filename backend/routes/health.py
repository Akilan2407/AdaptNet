"""Health check endpoint for Phase 18 Flask API."""

from flask import Blueprint, jsonify
from backend.utils.serialization import success_response

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Service health and module readiness check."""
    return success_response({
        "status": "healthy",
        "service": "network-management-api",
        "version": "1.0.0",
        "modules": {
            "monitoring": "ready",
            "profiling": "ready",
            "congestion": "ready",
            "classification": "ready",
            "policy": "ready",
            "control": "ready",
            "traces": "ready",
            "explainability": "ready",
            "explanations": "ready",
        },
    })
