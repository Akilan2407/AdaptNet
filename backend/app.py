"""
Backend REST API Module for Adaptive Network Traffic Management.
Phase 18 Implementation - Read-Only REST APIs for React Dashboard.
"""

import os
from pathlib import Path
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, jsonify
from flask_cors import CORS

from backend.config import Config
from backend.utils.serialization import error_response, success_response
from backend.routes.health import health_bp
from backend.routes.monitoring import monitoring_bp
from backend.routes.profiling import profiling_bp
from backend.routes.congestion import congestion_bp
from backend.routes.classification import classification_bp
from backend.routes.policy import policy_bp
from backend.routes.control import control_bp
from backend.routes.traces import traces_bp
from backend.routes.explainability import explainability_bp
from backend.routes.explanations import explanations_bp
from backend.routes.stats import stats_bp


def create_app(config_class=Config) -> Flask:
    """Application factory for the Flask REST API."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Enable CORS for all API endpoints (ready for Phase 19 React frontend)
    CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

    # Register blueprints under API prefix
    prefix = app.config.get("API_PREFIX", "/api")

    app.register_blueprint(health_bp, url_prefix=prefix)
    app.register_blueprint(monitoring_bp, url_prefix=f"{prefix}/monitoring")
    app.register_blueprint(profiling_bp, url_prefix=f"{prefix}/profiling")
    app.register_blueprint(congestion_bp, url_prefix=f"{prefix}/congestion")
    app.register_blueprint(classification_bp, url_prefix=f"{prefix}/classification")
    app.register_blueprint(policy_bp, url_prefix=f"{prefix}/policy")
    app.register_blueprint(control_bp, url_prefix=f"{prefix}/control")
    app.register_blueprint(traces_bp, url_prefix=f"{prefix}/traces")
    app.register_blueprint(explainability_bp, url_prefix=f"{prefix}/explainability")
    app.register_blueprint(explanations_bp, url_prefix=f"{prefix}/explanations")
    app.register_blueprint(stats_bp, url_prefix=prefix)

    @app.route("/", methods=["GET"])
    @app.route(prefix, methods=["GET"])
    def index():
        """Root API metadata and endpoint directory."""
        return success_response({
            "service": "Adaptive Network Traffic Management REST API",
            "version": "1.1.0",
            "phase": "Phase 18 - Backend REST API Module (Improved)",
            "documentation": f"{prefix}/health",
            "endpoints": [
                f"{prefix}/health",
                f"{prefix}/stats",
                f"{prefix}/monitoring/flows",
                f"{prefix}/monitoring/summary",
                f"{prefix}/monitoring/search",
                f"{prefix}/profiling/behaviors",
                f"{prefix}/profiling/clusters",
                f"{prefix}/congestion/predictions",
                f"{prefix}/congestion/summary",
                f"{prefix}/classification/flows",
                f"{prefix}/classification/summary",
                f"{prefix}/policy/decisions",
                f"{prefix}/policy/summary",
                f"{prefix}/control/actions",
                f"{prefix}/control/state",
                f"{prefix}/control/summary",
                f"{prefix}/traces",
                f"{prefix}/traces/<trace_id>",
                f"{prefix}/traces/summary",
                f"{prefix}/explainability/local",
                f"{prefix}/explainability/global",
                f"{prefix}/explainability/summary",
                f"{prefix}/explanations",
                f"{prefix}/explanations/<trace_id>",
                f"{prefix}/explanations/summary",
            ],
        })

    # Global Error Handlers
    @app.errorhandler(400)
    def bad_request(error):
        return error_response(str(error.description or "Bad Request"), status_code=400)

    @app.errorhandler(404)
    def not_found(error):
        return error_response("Endpoint or resource not found.", status_code=404)

    @app.errorhandler(405)
    def method_not_allowed(error):
        return error_response("HTTP method not allowed on this endpoint.", status_code=405)

    @app.errorhandler(500)
    def internal_error(error):
        return error_response("An internal server error occurred.", status_code=500)

    return app


def is_port_available(host: str, port: int) -> bool:
    """Test if a port can be bound to."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
        except OSError:
            return False


if __name__ == "__main__":
    app = create_app()
    host = os.environ.get("HOST", app.config.get("API_HOST", "0.0.0.0"))
    desired_port = int(os.environ.get("PORT", app.config.get("API_PORT", 5000)))
    debug = app.config.get("DEBUG", False)

    # Check port availability (handles macOS AirPlay occupying port 5000)
    if is_port_available(host, desired_port):
        port = desired_port
    elif desired_port == 5000 and is_port_available(host, 5001):
        port = 5001
        print(f"Port 5000 occupied (macOS AirPlay). Automatically using port {port}")
    else:
        port = desired_port

    print(f"Starting Network Management REST API on http://{host}:{port}/api")
    app.run(host=host, port=port, debug=debug)
