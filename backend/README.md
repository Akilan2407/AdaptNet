# Phase 18: Backend REST API Module

## Overview

The **Phase 18: Backend REST API Module** provides a comprehensive, read-only RESTful API service built on Flask for the *“Explainable, User-Aware ML System for Adaptive Network Traffic Management in Small LANs”* project.

It unifies and exposes all analytical, predictive, control, traceability, and explainability artifacts produced across Phases 1 through 17 to serve as the data backbone for the Phase 19 React Dashboard.

---

## Architectural Principles

1. **Strictly Read-Only**: The API provides pure query and inspection capabilities. It does not modify traffic control states, alter system policies, or retrain ML models.
2. **Modular Route Structure**: 10 decoupled Flask blueprints organized under the `/api` prefix, utilizing the Flask application factory pattern (`create_app()`).
3. **Resilient Data Service (`DataService`)**: Thread-safe ingestion layer handling CSV, JSON, and JSONL data files generated across Phases 1–17. Missing files or empty datasets return structured empty/error responses without crashing the server.
4. **Strict JSON Sanitization**: Automatic recursive transformation of NumPy datatypes, `NaN`/`inf` to `null`, and timestamps to ISO-8601 strings.
5. **CORS Enabled**: Configured via `flask-cors` with credentials support to seamlessly serve cross-origin requests from the React frontend running on port 3000 or Vite dev servers.
6. **Consistent JSON Schemas**:
   - Collections: `{"status": "success", "count": N, "total": M, "data": [...]}`
   - Items: `{"status": "success", "data": {...}}`
   - Summaries: `{"status": "success", ...summary_metrics}`
   - Errors: `{"status": "error", "error": "Detailed description"}`

---

## Complete API Endpoint Directory

All endpoints are hosted under the `/api` prefix:

| Endpoint | Method | Query Parameters | Description |
|:---|:---:|:---|:---|
| `/api/health` | `GET` | — | System health status, version, and module readiness |
| `/api` / `/` | `GET` | — | API service metadata and complete endpoint directory |
| `/api/monitoring/flows` | `GET` | `limit`, `offset`, `device_id` | Telemetry flow records from C monitoring agents |
| `/api/monitoring/summary` | `GET` | — | Aggregate network metrics (bandwidth, packet loss, active flows) |
| `/api/profiling/behaviors` | `GET` | `limit`, `offset` | Host behavior profiles and assigned K-Means cluster IDs |
| `/api/profiling/clusters` | `GET` | — | Clustering evaluation metrics, silhouette score, feature weights |
| `/api/congestion/predictions` | `GET` | `limit`, `offset`, `device_id` | GRU congestion model forecast predictions and actuals |
| `/api/congestion/summary` | `GET` | — | GRU model evaluation metrics, dataset stats, and baseline comparisons |
| `/api/classification/flows` | `GET` | `limit`, `offset`, `traffic_class`, `device_id` | Classified flows with application category and confidence |
| `/api/classification/summary` | `GET` | — | Classification distributions and active classification rules |
| `/api/policy/decisions` | `GET` | `limit`, `offset`, `priority`, `device_id` | Deterministic QoS policy decisions and rule justifications |
| `/api/policy/summary` | `GET` | — | QoS policy decision frequencies and rule invocation stats |
| `/api/control/actions` | `GET` | `limit`, `offset`, `status`, `device_id` | Audit log of applied Linux `tc` traffic control actions |
| `/api/control/state` | `GET` | `limit`, `offset` | Current active traffic shaping state across network interfaces |
| `/api/control/summary` | `GET` | — | Control execution summary, success rates, dry-run counts |
| `/api/traces` | `GET` | `limit`, `offset`, `status`, `device_id` | End-to-end decision traces across all 7 pipeline stages |
| `/api/traces/<trace_id>` | `GET` | — | Deep-dive structured trace for a specific decision ID |
| `/api/traces/summary` | `GET` | — | Trace completeness counts, match rates, and validation stats |
| `/api/explainability/local` | `GET` | `limit`, `offset`, `trace_id` | Local SHAP attributions per prediction and decision |
| `/api/explainability/global` | `GET` | — | Global mean absolute SHAP importance rankings across features |
| `/api/explainability/summary` | `GET` | — | SHAP explainer configuration, sample counts, and validation checks |
| `/api/explanations` | `GET` | `limit`, `offset`, `status`, `device_id` | Natural-language decision explanations for network flows |
| `/api/explanations/<trace_id>` | `GET` | — | Complete natural-language explanation record for a trace ID |
| `/api/explanations/summary` | `GET` | — | Natural-language explanation coverage and status distribution |

---

## Directory Layout

```text
backend/
├── __init__.py
├── app.py                     # Application factory (create_app), CORS, error handlers
├── config.py                  # Server configuration and concrete data filepaths
├── requirements.txt           # Python backend dependencies
├── README.md                  # This documentation
├── routes/                    # Modular route blueprints
│   ├── __init__.py
│   ├── health.py              # Health check endpoint
│   ├── monitoring.py          # Network telemetry & flows
│   ├── profiling.py           # Device behavior & clustering
│   ├── congestion.py          # Congestion forecast & baselines
│   ├── classification.py      # Traffic classification
│   ├── policy.py              # QoS policy decisions
│   ├── control.py             # Adaptive traffic control actions
│   ├── traces.py              # End-to-end decision traces
│   ├── explainability.py      # SHAP feature attributions
│   └── explanations.py        # Natural-language explanations
├── services/
│   ├── __init__.py
│   └── data_service.py        # Data ingestion, caching, filtering, and pagination
├── tests/
│   ├── __init__.py
│   └── test_api.py            # Comprehensive pytest test suite (29 tests)
└── utils/
    ├── __init__.py
    └── serialization.py       # JSON serialization sanitizer & standard responses
```

---

## Quick Start & Running Locally

### 1. Environment & Dependencies

Activate the project virtual environment and verify dependencies:

```bash
source .venv/bin/activate
pip install -r backend/requirements.txt
```

On Windows PowerShell, activate the environment with:
```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

### 2. Run the Development Server

Start the REST API server:

```bash
python -m backend.app
```

The server binds to `0.0.0.0:5000` by default:
- **API Root**: `http://localhost:5000/api`
- **Health Check**: `http://localhost:5000/api/health`

### 3. Example `curl` Commands

```bash
# Check service health and module status
curl -s http://localhost:5000/api/health | jq .

# Inspect telemetry flows with pagination
curl -s "http://localhost:5000/api/monitoring/flows?limit=3" | jq .

# Query high-priority QoS decisions
curl -s "http://localhost:5000/api/policy/decisions?priority=LOW&limit=5" | jq .

# Retrieve a single decision trace by ID
curl -s http://localhost:5000/api/traces/TRC-000001 | jq .

# Retrieve global SHAP feature importance
curl -s http://localhost:5000/api/explainability/global | jq .

# Retrieve natural-language explanation
curl -s http://localhost:5000/api/explanations/TRC-000001 | jq .
```

---

## Running Automated Tests

Run the backend test suite:

```bash
pytest -v backend/tests/test_api.py
```

Run both backend and regression test suites:

```bash
pytest -v tests/ backend/tests/
```

---

## Phase 19 React Dashboard Integration Guide

The frontend application in Phase 19 will connect to these endpoints:
1. **Network Topology & Flow Monitor**: Calls `GET /api/monitoring/flows` and `GET /api/monitoring/summary`.
2. **Behavior Profiling View**: Calls `GET /api/profiling/behaviors` and `GET /api/profiling/clusters`.
3. **Congestion Prediction View**: Calls `GET /api/congestion/predictions` and `GET /api/congestion/summary`.
4. **Traffic Classification View**: Calls `GET /api/classification/flows` and `GET /api/classification/summary`.
5. **QoS Policy & Control Monitor**: Calls `GET /api/policy/decisions` and `GET /api/control/actions`.
6. **Decision Trace Inspector**: Calls `GET /api/traces` and `GET /api/traces/<trace_id>`.
7. **XAI & Natural Language Panel**: Calls `GET /api/explainability/global`, `GET /api/explainability/local`, and `GET /api/explanations/<trace_id>`.
