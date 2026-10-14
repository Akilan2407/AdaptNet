# AdaptNet: Explainable, User-Aware ML System for Adaptive Network Traffic Management

An end-to-end intelligent network traffic management system combining low-level packet capture, real-time streaming machine learning (device profiling, pure-NumPy GRU congestion forecasting, rule-based QoS policy engines, and SHAP explainability), a Flask REST API service, and a modern React Vite admin dashboard.

---

## 🏗 System Architecture & Technology Stack

```
adaptive-network-traffic-management/
├── network/                    # Low-level networking & IPC in C / Python
│   ├── agent/                  # Packet sniffer agent (Scapy / raw socket stream monitor)
│   ├── controller/             # C network controller & telemetry hub
│   ├── common/                 # Protocol headers (protocol.h, packet definitions)
│   └── traffic/                # Synthetic traffic generation & topology emulation
├── ml/                         # Machine Learning pipeline
│   ├── realtime/               # ⚡ Real-time wire capture & multi-model streaming pipeline
│   │   ├── packet_normalizer.py# Packet header normalization & protocol extraction
│   │   ├── flow_aggregator.py  # Stateful 5-tuple flow tracking & rate computation
│   │   ├── model_runner.py     # Multi-model inference (K-Means, Pure-NumPy GRU, Rules, QoS, SHAP)
│   │   └── pipeline_manager.py # Thread-safe singleton coordinator & ring buffers
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
│   ├── routes/                 # Blueprint endpoints (health, live capture, monitoring, profiling, etc.)
│   ├── services/               # Data loaders, LiveCaptureService, and pipeline managers
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
├── tests/                      # Integration & unit test suites (backend, ml, network, realtime)
├── docs/                       # Architecture diagrams & technical documentation
├── start_system.ps1            # Windows PowerShell one-click launcher
├── start_system.sh             # Linux/macOS Bash one-click launcher
├── COMMANDS.md                 # Full command and operational reference guide
├── Makefile                    # C build system for monitoring agent & controller
├── CMakeLists.txt              # CMake build configuration
├── requirements.txt            # Python dependencies (Flask, scikit-learn, Scapy, h5py, etc.)
└── README.md                   # Project overview & quick start
```

### Technology Matrix
- **Telemetry Collection & Sniffing**: `Python` (`scapy`, raw socket monitor, `psutil`) / `C` (C11, POSIX sockets, pthread, pcap)
- **Real-Time Streaming Engine**: Zero-copy packet normalization, stateful 5-tuple flow aggregation, EWMA rate estimator
- **User / Device Profiling**: `scikit-learn` (`K-Means`, `DBSCAN`) with standard feature scaling
- **Congestion Forecasting**: Recurrent neural networks (GRU) with a pure-NumPy zero-TensorFlow forward-pass runner (ensuring seamless Python 3.13 / Windows cross-platform support)
- **Explainability (XAI)**: `SHAP` (Shapley Additive exPlanations) & dynamic local feature attributions
- **Backend REST API**: `Flask` 3.x, `Flask-CORS` (listening on port `5001`)
- **Frontend Dashboard**: `React` 18, `Vite`, Lucide icons, glassmorphic dark theme (listening on port `3000`)
- **Testing & Emulation**: `pytest`, `Mininet`, `iperf3`

---

## ⚡ Quick Start

### 1. Prerequisites
- **Python**: `Python 3.10+` (fully tested with Python 3.13 on Windows & Linux)
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
| `/api/live/interfaces` | `GET` | List available OS network interfaces |
| `/api/live/start` | `POST` | Start real-time packet capture and ML pipeline |
| `/api/live/stop` | `POST` | Stop real-time packet capture |
| `/api/live/stats` | `GET` | Raw sniffer metrics, arrival rate (pps), and protocol breakdown |
| `/api/live/packets` | `GET` | Recent captured raw packet frames |
| `/api/live/pipeline/status` | `GET` | Status of real-time ML engine, queue size, and inference count |
| `/api/live/pipeline/flows` | `GET` | Stateful 5-tuple flows with live ML predictions |
| `/api/live/pipeline/predictions`| `GET` | Recent ML predictions (traffic class, cluster, congestion score, priority) |
| `/api/live/pipeline/traces` | `GET` | Live 7-stage decision traces with SHAP explainability |
| `/api/live/pipeline/clear` | `POST` | Reset in-memory flow and trace ring buffers |
| `/api/monitoring/flows` | `GET` | Network flows (`?source=live` supported) |
| `/api/monitoring/summary` | `GET` | Summary statistics of monitored network flows |
| `/api/profiling/behaviors` | `GET` | Device behavior profiles and cluster assignments |
| `/api/congestion/predictions` | `GET` | GRU congestion forecasts (`?source=live` supported) |
| `/api/classification/flows` | `GET` | Flow classification results (`?source=live` supported) |
| `/api/policy/decisions` | `GET` | QoS bandwidth limits and priority allocations (`?source=live` supported) |
| `/api/traces` | `GET` | End-to-end decision traces linking telemetry to QoS (`?source=live` supported) |
| `/api/explainability/local` | `GET` | Local SHAP attribution values for specific predictions |
| `/api/explainability/global`| `GET` | Global SHAP feature importances across all features |
| `/api/explanations` | `GET` | Natural language explanations for QoS decisions |

---

## ⚡ Real-Time ML Wire Capture Pipeline

AdaptNet features a **zero-delay, live wire machine learning pipeline** that hooks into genuine physical/virtual network interfaces:

1. **Packet Normalization:** Raw Ethernet/IP frames are converted into structured `NormalizedPacket` records extracting IP addresses, ports, transport protocol, header flags, payload sizes, and sequence numbers.
2. **Stateful Flow Aggregation:** Bounded in-memory flow aggregator tracks active 5-tuple sessions (`src:port -> dst:port [proto]`), computing exponentially weighted moving average (EWMA) throughput, RTT, and packet loss metrics with idle-timeout eviction.
3. **Multi-Model Inference:**
   - **K-Means Host Profiling:** Dynamically assigns device behavior clusters from live telemetry.
   - **Traffic Classification:** Categorizes live flows (Web, Video/VoIP, Bulk Transfer, Interactive, DNS) based on port and traffic heuristics.
   - **Zero-TensorFlow NumPy GRU Forecaster:** Executes recurrent neural network forward passes directly against trained `.keras` weights without needing TensorFlow installed (running in $<5$ ms on Windows and Python 3.13).
   - **QoS Policy Engine:** Synthesizes traffic class, device profile, and predicted congestion score to compute QoS priority (`CRITICAL`, `HIGH`, `NORMAL`, `LOW`) and bandwidth limits.
   - **Decision Trace & SHAP:** Emits a 7-stage auditable trace (`TRC-LIVE-xxxxxx`) with live feature attribution breakdown.

> [!NOTE]
> **Kernel QoS Enforcement Disclaimer:**
> In standard user-space mode, QoS policies are calculated, audited, and presented as **RECOMMENDED POLICIES**. Direct kernel-level traffic shaping requires root/administrative OS privileges and traffic control driver bindings (Linux `tc` / `netem` or Windows QoS Packet Scheduler).

---

## 🧪 Testing & Verification

Run the comprehensive automated test suite (51 tests):

```bash
# Run all backend API and real-time streaming pipeline tests
pytest -v backend/tests/test_api.py tests/test_realtime_pipeline.py
```

### Test Coverage Highlights:
- **`backend/tests/test_api.py` (44 tests):** Health checks, monitoring, profiling, congestion, classification, policies, control state, decision traces, and SHAP explainability.
- **`tests/test_realtime_pipeline.py` (7 tests):** Packet normalization, stateful flow aggregation, EWMA rate computation, idle flow eviction, multi-model inference runner, pipeline manager worker thread, and live API endpoints.

---

## 💻 React Admin Dashboard Modules

The React frontend includes an intuitive glassmorphic dashboard:
1. **Live Wire Sniffer & Real-Time ML**: Start/stop live wire packet capture, inspect active 5-tuple flows, view live ML predictions, and audit decision traces in real time.
2. **Network Monitoring**: Real-time traffic throughput, packet rates, RTT, jitter, and active connections with a toggle between **📁 Historical Dataset** and **⚡ Live Wire Stream**.
3. **User & Device Profiling**: Cluster visualization (K-Means/DBSCAN) distinguishing heavy streamers, bulk downloaders, and interactive users.
4. **Congestion Forecasting**: Recurrent neural network forecasts indicating upcoming queue saturation and bottleneck probabilities.
5. **Traffic Classification**: Port and flow classification identifying web browsing, DNS, gaming, VoIP, and bulk data transfers.
6. **QoS Policy Engine**: Dynamic bandwidth allocation, rate limits, and priority tier assignments.
7. **Adaptive Traffic Control**: Topology visualization, queue status, shaping rules, and actuation state.
8. **Decision Traces**: Comprehensive audit log mapping telemetry inputs, predictions, policies, and actions with interactive lineage inspection modals.
9. **Explainable AI (SHAP)**: Interactive SHAP feature importance charts and human-readable explanation reason chains.

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
