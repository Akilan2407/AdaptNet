"""Routes package for Phase 18 Flask API."""

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

ALL_BLUEPRINTS = [
    health_bp,
    monitoring_bp,
    profiling_bp,
    congestion_bp,
    classification_bp,
    policy_bp,
    control_bp,
    traces_bp,
    explainability_bp,
    explanations_bp,
    stats_bp,
]

__all__ = [
    "health_bp",
    "monitoring_bp",
    "profiling_bp",
    "congestion_bp",
    "classification_bp",
    "policy_bp",
    "control_bp",
    "traces_bp",
    "explainability_bp",
    "explanations_bp",
    "stats_bp",
    "ALL_BLUEPRINTS",
]
