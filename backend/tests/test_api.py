"""
Comprehensive API test suite for Phase 18 Backend REST API Module.
Tests all 10 blueprints, 23 endpoints, pagination, filtering, 404/405 errors, and CORS.
"""

import pytest
from backend.app import create_app
from backend.config import Config


class TestConfig(Config):
    """Configuration for testing."""
    TESTING = True
    DEBUG = False


@pytest.fixture
def client():
    """Flask test client fixture."""
    app = create_app(TestConfig)
    with app.test_client() as client:
        yield client


# 1. Health & Root Endpoints
def test_health_check(client):
    """Test GET /api/health."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "network-management-api"
    assert data["version"] == "1.0.0"
    assert "modules" in data
    assert data["modules"]["monitoring"] == "ready"
    assert data["modules"]["explanations"] == "ready"


def test_root_index(client):
    """Test GET / and GET /api."""
    for path in ["/", "/api"]:
        response = client.get(path)
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        assert "endpoints" in data
        assert "/api/health" in data["endpoints"]


# 2. Monitoring Endpoints
def test_monitoring_flows(client):
    """Test GET /api/monitoring/flows with pagination and filtering."""
    response = client.get("/api/monitoring/flows")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "data" in data
    assert "count" in data
    assert "total" in data

    # Test pagination
    paginated_response = client.get("/api/monitoring/flows?limit=5&offset=2")
    assert paginated_response.status_code == 200
    p_data = paginated_response.get_json()
    assert p_data["count"] <= 5
    assert p_data["limit"] == 5
    assert p_data["offset"] == 2

    # Test device_id filter
    filtered_response = client.get("/api/monitoring/flows?device_id=h1")
    assert filtered_response.status_code == 200
    f_data = filtered_response.get_json()
    for item in f_data["data"]:
        assert item["device_id"] == "h1"


def test_monitoring_summary(client):
    """Test GET /api/monitoring/summary."""
    response = client.get("/api/monitoring/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "total_records" in data
    assert "unique_devices" in data


# 3. Profiling Endpoints
def test_profiling_behaviors(client):
    """Test GET /api/profiling/behaviors."""
    response = client.get("/api/profiling/behaviors")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "data" in data
    assert data["count"] > 0
    first_profile = data["data"][0]
    assert "device_id" in first_profile
    assert "cluster_id" in first_profile


def test_profiling_clusters(client):
    """Test GET /api/profiling/clusters."""
    response = client.get("/api/profiling/clusters")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "clusters" in data
    assert "features" in data


# 4. Congestion Endpoints
def test_congestion_predictions(client):
    """Test GET /api/congestion/predictions."""
    response = client.get("/api/congestion/predictions?limit=10")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) <= 10
    if len(data["data"]) > 0:
        pred = data["data"][0]
        assert "predicted_score" in pred or "actual_score" in pred


def test_congestion_summary(client):
    """Test GET /api/congestion/summary."""
    response = client.get("/api/congestion/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "model_evaluation" in data
    assert "baseline_summary" in data


# 5. Traffic Classification Endpoints
def test_classification_flows(client):
    """Test GET /api/classification/flows with traffic_class filter."""
    response = client.get("/api/classification/flows?limit=10")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) <= 10

    # Filter by traffic_class
    filtered = client.get("/api/classification/flows?traffic_class=BULK_TRANSFER")
    assert filtered.status_code == 200
    f_data = filtered.get_json()
    for flow in f_data["data"]:
        assert flow["traffic_class"] == "BULK_TRANSFER"


def test_classification_summary(client):
    """Test GET /api/classification/summary."""
    response = client.get("/api/classification/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "summary" in data
    assert "classification_rules" in data


# 6. QoS Policy Endpoints
def test_policy_decisions(client):
    """Test GET /api/policy/decisions with priority filter."""
    response = client.get("/api/policy/decisions?limit=10")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) <= 10

    # Filter by priority
    filtered = client.get("/api/policy/decisions?priority=LOW")
    assert filtered.status_code == 200
    f_data = filtered.get_json()
    for decision in f_data["data"]:
        assert decision["final_priority"] == "LOW"


def test_policy_summary(client):
    """Test GET /api/policy/summary."""
    response = client.get("/api/policy/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "total_decisions" in data
    assert "priority_distribution" in data


# 7. Adaptive Traffic Control Endpoints
def test_control_actions(client):
    """Test GET /api/control/actions."""
    response = client.get("/api/control/actions?limit=10")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) <= 10


def test_control_state(client):
    """Test GET /api/control/state."""
    response = client.get("/api/control/state")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "data" in data


def test_control_summary(client):
    """Test GET /api/control/summary."""
    response = client.get("/api/control/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "total_decisions" in data
    assert "control_success_rate" in data


# 8. Decision Traces Endpoints
def test_traces_list(client):
    """Test GET /api/traces."""
    response = client.get("/api/traces?limit=10")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) <= 10


def test_trace_by_id_found(client):
    """Test GET /api/traces/<trace_id> for existing trace."""
    response = client.get("/api/traces/TRC-000001")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["data"]["trace_id"] == "TRC-000001"
    assert "stages" in data["data"]


def test_trace_by_id_not_found(client):
    """Test GET /api/traces/<trace_id> for non-existent trace returns 404."""
    response = client.get("/api/traces/NON_EXISTENT_TRACE_ID")
    assert response.status_code == 404
    data = response.get_json()
    assert data["status"] == "error"
    assert "not found" in data["error"].lower()


def test_trace_summary(client):
    """Test GET /api/traces/summary."""
    response = client.get("/api/traces/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "total_traces" in data
    assert "complete_traces" in data


# 9. Explainability Endpoints
def test_explainability_local(client):
    """Test GET /api/explainability/local."""
    response = client.get("/api/explainability/local?limit=10")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) <= 10

    # Filter by trace_id
    filtered = client.get("/api/explainability/local?trace_id=TRC-000001")
    assert filtered.status_code == 200
    f_data = filtered.get_json()
    for item in f_data["data"]:
        assert item["trace_id"] == "TRC-000001"


def test_explainability_global(client):
    """Test GET /api/explainability/global."""
    response = client.get("/api/explainability/global")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) > 0
    assert "feature_name" in data["data"][0]
    assert "mean_absolute_shap" in data["data"][0]


def test_explainability_summary(client):
    """Test GET /api/explainability/summary."""
    response = client.get("/api/explainability/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "explainer_type" in data
    assert "feature_count" in data


# 10. Natural-Language Explanation Endpoints
def test_explanations_list(client):
    """Test GET /api/explanations."""
    response = client.get("/api/explanations?limit=10")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["data"]) <= 10


def test_explanation_by_id_found(client):
    """Test GET /api/explanations/<trace_id> for existing trace."""
    response = client.get("/api/explanations/TRC-000001")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["data"]["trace_id"] == "TRC-000001"
    assert "explanation_text" in data["data"]
    assert "classification" in data["data"]


def test_explanation_by_id_not_found(client):
    """Test GET /api/explanations/<trace_id> for non-existent trace returns 404."""
    response = client.get("/api/explanations/NON_EXISTENT_TRACE_ID")
    assert response.status_code == 404
    data = response.get_json()
    assert data["status"] == "error"
    assert "not found" in data["error"].lower()


def test_explanation_summary(client):
    """Test GET /api/explanations/summary."""
    response = client.get("/api/explanations/summary")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "total_traces" in data
    assert "partial_explanations" in data


# 11. Error Handling & Read-Only Tests
def test_404_not_found(client):
    """Test accessing an unknown API route returns clean JSON 404."""
    response = client.get("/api/nonexistent_route")
    assert response.status_code == 404
    data = response.get_json()
    assert data["status"] == "error"
    assert "not found" in data["error"].lower()


def test_read_only_method_not_allowed(client):
    """Test that POST/PUT/DELETE methods are rejected with 405 on read-only endpoints."""
    post_res = client.post("/api/health", json={"data": "test"})
    assert post_res.status_code == 405
    assert post_res.get_json()["status"] == "error"

    post_dec = client.post("/api/policy/decisions", json={"fake": "decision"})
    assert post_dec.status_code == 405
    assert post_dec.get_json()["status"] == "error"

    delete_trace = client.delete("/api/traces/TRC-000001")
    assert delete_trace.status_code == 405
    assert delete_trace.get_json()["status"] == "error"


# 12. CORS Headers Test
def test_cors_headers(client):
    """Test CORS header presence for cross-origin dashboard requests."""
    response = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") in ("*", "http://localhost:3000")
