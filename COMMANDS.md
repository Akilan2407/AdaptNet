
# AdaptNet — System Run & Command Reference Guide

This document lists all the commands needed to set up, run, test, and maintain the **AdaptNet** system on both **Windows (PowerShell)** and **Linux / macOS (Bash)**.

---

## ⚡ 1. Quick Start (One Command)

The easiest way to start both the Flask backend and the React frontend simultaneously:

### Windows (PowerShell)
```powershell
.\start_system.ps1
```

> **Note**: If script execution is restricted on Windows, allow execution for current user:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

### Linux / macOS (Bash)
```bash
chmod +x start_system.sh
./start_system.sh
```

---

## 🛠️ 2. Environment Setup & Installation

Run these commands once during initial setup:

### A. Python Virtual Environment (`.venv`)

#### Windows (PowerShell)
```powershell
# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### Linux / macOS (Bash)
```bash
# 1. Create virtual environment
python3 -m venv .venv

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

### B. Frontend Dependencies

```bash
# Navigate to frontend folder and install npm packages
cd frontend
npm install
cd ..
```

---

### C. C Networking System (Linux / macOS only)

```bash
# Compile monitoring agent and controller binaries
make all

# Run binary smoke tests
make test
```

---

## 🖥️ 3. Running Services Individually (Manual Start)

If you prefer running services in separate terminals for independent debugging:

### Terminal 1: Flask REST API Backend (Port 5001)

#### Windows (PowerShell)
```powershell
.\.venv\Scripts\Activate.ps1
$env:PORT = "5001"
python backend\app.py
```

#### Linux / macOS (Bash)
```bash
source .venv/bin/activate
PORT=5001 python backend/app.py
```

---

### Terminal 2: React Vite Frontend (Port 3000)

#### Any OS
```bash
cd frontend
npm run dev
```

---

## 🌐 4. Service URLs & Endpoints

Once running, access the services using these URLs:

| Service | URL | Notes |
| :--- | :--- | :--- |
| **Frontend Dashboard** | [http://localhost:3000](http://localhost:3000) | Interactive React UI |
| **Backend REST API** | [http://localhost:5001/api](http://localhost:5001/api) | API Root & endpoint catalog |
| **Health Check** | [http://localhost:5001/api/health](http://localhost:5001/api/health) | System status & component readiness |
| **Telemetry Flows** | [http://localhost:5001/api/monitoring/flows](http://localhost:5001/api/monitoring/flows) | Live/recorded packet flows |
| **User Profiling** | [http://localhost:5001/api/profiling/behaviors](http://localhost:5001/api/profiling/behaviors) | Clustering & host profiles |
| **Congestion Predictions** | [http://localhost:5001/api/congestion/predictions](http://localhost:5001/api/congestion/predictions) | GRU model predictions |
| **Decision Traces** | [http://localhost:5001/api/traces](http://localhost:5001/api/traces) | Full pipeline trace inspection |
| **SHAP Explainability** | [http://localhost:5001/api/explainability/global](http://localhost:5001/api/explainability/global) | Global feature importances |

---

## 🧪 5. Running Automated Tests

Make sure your virtual environment is active before running tests:

### Run All Tests
```bash
pytest
```

### Run With Verbose Output
```bash
pytest -v
```

### Run Specific Test Modules

```bash
# Run backend REST API tests only (29 tests)
pytest -v backend/tests/test_api.py

# Run ML module tests
pytest -v tests/ml/

# Run feature extraction test
pytest -v tests/ml/test_feature_extraction.py

# Run network module tests
pytest -v tests/network/
```

---

## 🤖 6. Running ML & Telemetry Pipeline Modules

You can execute individual pipeline stages directly via Python modules:

```bash
# 1. Generate Synthetic Telemetry Flow Data
python network/traffic/generate_synthetic_telemetry.py

# 2. Extract Features from Flow Data
python -m ml.features.feature_extractor

# 3. User & Device Behavioral Profiling (K-Means / DBSCAN)
python -m ml.profiling.behavior_profiler

# 4. Traffic Classification (Rule-based & ML)
python -m ml.classification.traffic_classifier

# 5. Congestion Dataset Preparation & Model Training (GRU)
python -m ml.congestion.congestion_dataset
python -m ml.congestion.train
python -m ml.congestion.evaluate

# 6. QoS Policy Decision Engine
python -m ml.policy.qos_policy_engine

# 7. End-to-End Decision Traces
python -m ml.trace.decision_trace

# 8. Explainability Engine (SHAP Attributions)
python -m ml.explainability.trace_explainer

# 9. Natural Language Explanations
python -m ml.explanation.explanation_generator
```

---

## 🧹 7. Port Cleanup & Troubleshooting

If port `5001` or `3000` is already in use from a previous run:

### Windows (PowerShell)
```powershell
# Find and stop process on port 5001 (Backend)
Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# Find and stop process on port 3000 (Frontend)
Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### Linux / macOS (Bash)
```bash
# Free port 5001
lsof -ti :5001 | xargs kill -9 2>/dev/null || true

# Free port 3000
lsof -ti :3000 | xargs kill -9 2>/dev/null || true
```
