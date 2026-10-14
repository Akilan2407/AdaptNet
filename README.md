# Explainable, User-Aware ML System for Adaptive Network Traffic Management in Small LANs

An intelligent, explainable network traffic management system combining low-level C telemetry collection, Python-powered machine learning (user profiling, GRU congestion prediction, and SHAP explainability), and a modern web dashboard.

---

## 🏗 System Architecture & Technology Stack

```
adaptive-network-traffic-management/
├── network/                    # Low-level networking & IPC in C
│   ├── agent/                  # C telemetry monitoring agent
│   ├── controller/             # C network controller & telemetry hub
│   └── common/                 # Common headers (protocol.h, packet definitions)
├── ml/                         # Machine Learning pipeline
│   ├── profiling/              # User/device clustering (K-Means, DBSCAN)
│   ├── congestion/             # Congestion prediction (TensorFlow / Keras GRU)
│   ├── baseline/               # Statistical baselines & rule engines
│   └── explainability/         # Model transparency & explanations (SHAP)
├── backend/                    # Flask REST API & service layer
├── frontend/                   # React + Vite admin dashboard
├── data/                       # Datasets & synthetic traffic captures
│   ├── raw/                    # Raw pcap & network flow logs
│   └── processed/              # Normalized feature tensors
├── tests/                      # Unit & integration test suites
│   ├── network/                # C agent/controller tests
│   ├── ml/                     # ML model validation & inference tests
│   └── backend/                # Flask endpoint tests
├── docs/                       # Architecture & design documents
├── Makefile                    # C build system
├── CMakeLists.txt              # CMake build configuration
├── requirements.txt            # Python ML & backend dependencies
└── README.md                   # Project overview & instructions
```

### Technology Matrix
- **Low-Level Networking & Agent**: `C` (C11, POSIX sockets, pthread)
- **Agent ↔ Controller IPC**: `TCP` (`protocol.h` fixed-format frames)
- **Monitored Application Traffic**: `TCP` & `UDP` (bandwidth, RTT, jitter, loss)
- **ML / Data Processing**: `Python 3`, `NumPy`, `Pandas`, `SciPy`
- **User / Traffic Profiling**: `scikit-learn` (`K-Means`, `DBSCAN`)
- **Congestion Forecasting**: `TensorFlow` / `Keras` (GRU recurrent neural networks)
- **ML Explainability (XAI)**: `SHAP` (Shapley Additive exPlanations)
- **Backend API**: `Flask`, `Flask-CORS`
- **Frontend Dashboard**: `React`, `Vite`
- **Testing & Emulation**: `Mininet`, `iperf3`, `pytest`

---

## 🚀 Getting Started & Environment Setup

### 1. Prerequisites
- **C Compiler**: `clang` or `gcc` (with `make`)
- **Python**: `Python 3.10+`
- **Node.js**: `Node v18+` and `npm`

### 2. Build the C Networking System
```bash
# Compile both agent and controller skeletons
make all

# Run smoke tests
make test

# Binaries generated:
# bin/agent
# bin/controller
```

### 3. Setup Python Virtual Environment
```bash
# Create virtual environment
python3 -m venv .venv

# Activate environment
source .venv/bin/activate

# Install all ML, backend, and testing dependencies
pip install -r requirements.txt
```

#### Windows PowerShell
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
once, then activate the environment again.

### 4. Setup & Start React Dashboard
```bash
cd frontend
npm install
npm run dev
# Dashboard will be available at http://localhost:3000
```

### 5. Quick Launch (Both Backend & Frontend)
```bash
# Start both Flask REST API (port 5001) and React Dashboard (port 3000)
./start_system.sh
```

On Windows PowerShell, use the native launcher instead:
```powershell
.\start_system.ps1
```

The Windows launcher starts the backend on port 5001 and the dashboard on port 3000.
Live packet capture requires Scapy and Npcap. Linux-only traffic shaping through `tc`
is simulated on Windows; use WSL2 or Linux for actual kernel traffic control.

---

## 📌 Development Roadmap & Implementation Status
- [x] **Phase 1: Project & Environment Setup** (Directory structure, C Makefile, Python venv, requirements, React Vite scaffold, architecture docs)
- [x] **Phase 2: Live Packet Sniffer & OSI Dissection** (Raw sockets, L2 Ethernet, L3 IPv4 checksums, L4 TCP 9 flags & window, UDP, ICMP)
- [x] **Phase 3: Real Timing & Metric Tracking** (TCP 3-way handshake RTT, RFC 6298 data/ACK deltas, TCP sequence gap packet loss, RFC 2581 Fast Retransmit dup ACKs)
- [x] **Phase 4: Traffic Generation & Emulation** (Mininet LAN topology, configurable TCP/UDP iperf3 traffic scenarios)
- [x] **Phase 5: ML Behavioral Profiling & Traffic Classification** (scikit-learn K-Means/DBSCAN user clustering, rule-based port & protocol classifier)
- [x] **Phase 6: Proactive Congestion Forecasting** (Deep Learning Keras GRU recurrent time-series models, sequence labeling)
- [x] **Phase 7: QoS Policy Decision Engine** (Dynamic policy matrix, priority clamping, reason chain generation)
- [x] **Phase 8: Kernel Traffic Control Actuation** (Linux `tc` HTB hierarchical token bucket queuing, rate shaping, priority filters)
- [x] **Phase 9: Explainability Engine (XAI)** (SHAP feature attribution, natural language explanations, decision trace logs)
- [x] **Phase 10: Flask REST API Backend** (Comprehensive read-only REST endpoints, CORS, multi-file data caching)
- [x] **Phase 11: React + Vite Admin Dashboard** (10 interactive pages: Monitoring, Profiling, Congestion, Policies, Control, Traces, Explanations)
- [x] **Phase 12: End-to-End System Integration & Evaluation** (181 / 181 automated tests passing across network, ML, and backend)
