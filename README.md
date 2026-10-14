# AdaptNet: Explainable, User-Aware ML System for Adaptive Network Traffic Management

An end-to-end intelligent network traffic management system combining low-level C telemetry collection, Python-powered machine learning (behavior profiling, GRU congestion forecasting, rule-based QoS policy engines, and SHAP explainability), a Flask REST API service, and a modern React Vite admin dashboard.

---

## 🏗 System Architecture & Technology Stack

```
adaptive-network-traffic-management/
├── network/                    # Low-level networking & IPC in C / Python
│   ├── agent/                  # C telemetry monitoring agent (packet dissection, timing)
│   ├── controller/             # C network controller & telemetry hub
│   ├── common/                 # Protocol headers (protocol.h, packet definitions)
│   └── traffic/                # Synthetic traffic generation & topology emulation
├── ml/                         # Machine Learning pipeline
│   ├── features/               # Feature extraction from raw network flows
│   ├── profiling/              # User/device clustering (K-Means, DBSCAN)
│   ├── classification/         # Rule-based & ML traffic classification
│   ├── congestion/             # Congestion forecasting (GRU recurrent neural networks)
│   ├── baseline/               # Statistical baselines & comparative models
│   ├── policy/                 # QoS policy engine & priority matrix
│   ├── trace/                  # End-to-end decision trace pipeline
│   ├── explainability/         # Model transparency & feature attributions (SHAP)
│   └── explanation/            # Natural language explanation generator
├── backend/                    # Flask REST API service layer
│   ├── routes/                 # Blueprint endpoints (health, monitoring, profiling, etc.)
│   ├── services/               # Data loaders, CSV parsers, and cache managers
│   ├── tests/                  # REST API test suite (44 automated tests)
│   └── app.py                  # API entry point & CORS configuration
├── frontend/                   # Modern React + Vite web dashboard
│   ├── src/                    # Components, pages, hooks, charts, API client
│   └── vite.config.js          # Vite configuration with `/api` proxy to port 5001
├── data/                       # Datasets, pipeline outputs, and telemetry logs
│   ├── monitoring/             # Network flow records & metrics
│   ├── features/               # Normalized feature matrices
│   ├── profiling/              # Clustering outputs & behavior profiles
│   ├── congestion/             # Congestion predictions & model artifacts
│   ├── policies/               # Policy allocations & decision matrices
│   ├── traces/                 # Structured decision trace logs
│   └── explainability/         # SHAP local/global attributions & summary JSONs
├── tests/                      # Integration & unit test suites (backend, ml, network)
├── docs/                       # Architecture diagrams & technical documentation
├── start_system.ps1            # Windows PowerShell one-click launcher
├── start_system.sh             # Linux/macOS Bash one-click launcher
├── COMMANDS.md                 # Full command and operational reference guide
├── Makefile                    # C build system for monitoring agent & controller
├── CMakeLists.txt              # CMake build configuration
├── requirements.txt            # Python dependencies (Flask, scikit-learn, Scapy, etc.)
└── README.md                   # Project overview & quick start
```

### Technology Matrix
- **Telemetry Collection & Sniffing**: `C` (C11, POSIX sockets, pthread, pcap) / `Python` (`scapy`, `psutil`)
- **Agent ↔ Controller IPC**: `TCP` (`protocol.h` fixed-format binary frames)
- **Data Processing**: `NumPy`, `Pandas`, `SciPy`
- **User / Device Profiling**: `scikit-learn` (`K-Means`, `DBSCAN`)
- **Congestion Forecasting**: `TensorFlow` / `Keras` (GRU recurrent neural networks)
- **Explainability (XAI)**: `SHAP` (Shapley Additive exPlanations) & Natural Language Reason Chains
- **Backend REST API**: `Flask` 3.x, `Flask-CORS` (listening on port `5001`)
- **Frontend Dashboard**: `React` 18, `Vite`, Tailwind CSS / Lucide icons (listening on port `3000`)
- **Testing & Emulation**: `pytest`, `Mininet`, `iperf3`

---

## ⚡ Quick Start

### 1. Prerequisites
- **Python**: `Python 3.10+` (tested with Python 3.13 / 3.14)
- **Node.js**: `Node v18+` and `npm`
- **C Compiler** *(Optional for C binaries on Linux/macOS)*: `gcc` or `clang` with `make`

### 2. One-Command Launch (Backend + Frontend)

#### Windows (PowerShell)
```powershell
.\start_system.ps1
```
*Note: If script execution is restricted on Windows, allow execution by running once:*
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

#### Linux / macOS (Bash)
```bash
chmod +x start_system.sh
./start_system.sh
```

The unified launcher checks port availability, starts the Flask REST API on port `5001`, starts the React Vite dashboard on port `3000`, and continuously monitors both processes.

---

## 🌐 Active Service Endpoints

| Service | URL | Purpose |
| :--- | :--- | :--- |
| **Frontend Dashboard** | [http://localhost:3000](http://localhost:3000) | Interactive React administrative dashboard |
| **Backend REST API Root** | [http://localhost:5001/api](http://localhost:5001/api) | API endpoint catalog & service metadata |
| **System Health Check** | [http://localhost:5001/api/health](http://localhost:5001/api/health) | Subsystem health, uptime, and module readiness |

### Key REST API Catalog

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/api/health` | `GET` | Health status and module availability |
| `/api/stats` | `GET` | Aggregated system metrics (flow counts, alert levels) |
| `/api/monitoring/flows` | `GET` | Live and recorded network flow records |
| `/api/monitoring/summary` | `GET` | Summary statistics of monitored network flows |
| `/api/monitoring/search` | `GET` | Filtered flow queries by IP, port, or protocol |
| `/api/profiling/behaviors` | `GET` | Device behavior profiles and cluster assignments |
| `/api/profiling/clusters` | `GET` | Summary of identified behavioral clusters |
| `/api/congestion/predictions` | `GET` | GRU congestion forecasts and risk probabilities |
| `/api/congestion/summary` | `GET` | Aggregate congestion risk indices across devices |
| `/api/classification/flows` | `GET` | Flow classification (Web, Streaming, Interactive, etc.) |
| `/api/policy/decisions` | `GET` | QoS bandwidth limits and priority allocations |
| `/api/policy/summary` | `GET` | QoS policy overview and rule breakdown |
| `/api/control/actions` | `GET` | Traffic shaping and queue configuration actions |
| `/api/control/state` | `GET` | Current operational state of traffic controller |
| `/api/traces` | `GET` | End-to-end decision traces linking telemetry to QoS |
| `/api/traces/<trace_id>` | `GET` | Detailed audit record for an individual decision trace |
| `/api/explainability/local` | `GET` | Local SHAP attribution values for specific predictions |
| `/api/explainability/global`| `GET` | Global SHAP feature importances across all features |
| `/api/explanations` | `GET` | Natural language explanations for QoS decisions |

---

## 🛠 Manual Installation & Individual Startup

If you prefer to run services in separate terminals for independent debugging:

### A. Python Environment Setup
```powershell
# Windows
python -m pip install --upgrade pip
pip install -r requirements.txt

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### B. Frontend Setup
```bash
cd frontend
npm install
cd ..
```

### C. Running Services Individually

**Terminal 1 — Flask REST API (Port 5001):**
```powershell
# Windows PowerShell
$env:PORT = "5001"
python backend/app.py

# Linux / macOS
PORT=5001 python backend/app.py
```

**Terminal 2 — React Dashboard (Port 3000):**
```bash
cd frontend
npm run dev
```

---

## 🧪 Testing & Verification

Ensure dependencies are installed and run the automated test suite:

```bash
# Run backend REST API test suite (44 tests)
pytest -v backend/tests/test_api.py

# Run network module unit tests
pytest -v tests/network/

# Run ML pipeline unit tests
pytest -v tests/ml/
```

### C Networking System (Linux / macOS only)
```bash
# Compile monitoring agent and controller binaries
make all

# Run smoke tests
make test
```

---

## 💻 React Admin Dashboard Modules

The React frontend includes an intuitive dark-themed user interface:
1. **Network Monitoring**: Real-time traffic throughput, packet rates, RTT, jitter, and active connections.
2. **User & Device Profiling**: Cluster visualization (K-Means/DBSCAN) distinguishing heavy streamers, bulk downloaders, and interactive users.
3. **Congestion Forecasting**: Recurrent neural network forecasts indicating upcoming queue saturation and bottleneck probabilities.
4. **Traffic Classification**: Port and flow classification identifying web browsing, DNS, gaming, VoIP, and bulk data transfers.
5. **QoS Policy Engine**: Dynamic bandwidth allocation, rate limits, and priority tier assignments.
6. **Traffic Control**: Kernel traffic control (`tc` HTB) queue status, shaping rules, and actuation state.
7. **Decision Traces**: Comprehensive audit log mapping inputs, predictions, policies, and actions.
8. **Explainable AI (XAI)**: Interactive SHAP feature importance charts and clear human-readable explanations explaining *why* traffic was throttled or prioritized.
9. **Diagnostics & Health**: Live backend subsystem latency, data file freshness, and endpoint telemetry.

---

## 🧹 Port Cleanup & Troubleshooting

If port `5001` or `3000` is already in use from a prior session:

### Windows (PowerShell)
```powershell
# Free port 5001 (Backend)
Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# Free port 3000 (Frontend)
Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

### Linux / macOS (Bash)
```bash
lsof -ti :5001 | xargs kill -9 2>/dev/null || true
lsof -ti :3000 | xargs kill -9 2>/dev/null || true
```

For complete command references across all pipeline components, refer to [`COMMANDS.md`](COMMANDS.md).
