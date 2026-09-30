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

### 4. Setup & Start React Dashboard
```bash
cd frontend
npm install
npm run dev
# Dashboard will be available at http://localhost:5173
```

---

## 📌 Development Roadmap
- [x] **Phase 1: Project & Environment Setup** (Directory structure, C Makefile/CMake, Python venv & requirements, React Vite scaffold, architecture docs)
- [ ] **Phase 2: Low-Level C Monitoring Agent & Protocol Implementation**
- [ ] **Phase 3: Traffic Generation & Data Pipeline (iperf3 / Mininet / PCAP)**
- [ ] **Phase 4: ML Models (K-Means/DBSCAN Profiling + GRU Congestion Forecasting)**
- [ ] **Phase 5: Explainability Engine (SHAP)**
- [ ] **Phase 6: Flask Backend API & Controller Integration**
- [ ] **Phase 7: React Dashboard & Visualization**
- [ ] **Phase 8: End-to-End System Integration & Evaluation**
