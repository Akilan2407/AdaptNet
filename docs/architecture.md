# System Architecture: Adaptive Network Traffic Management

## 1. Overview & Vision
The **Explainable, User-Aware ML System for Adaptive Network Traffic Management in Small LANs** provides real-time traffic monitoring, machine learning-driven user/device profiling, proactive congestion prediction, and policy enforcement with transparent explainability (XAI) for network administrators.

```
+-----------------------------------------------------------------------------+
|                               Small LAN Layer                               |
|   +---------------------+   +---------------------+   +-----------------+   |
|   |  Host A (Work/VoIP) |   |  Host B (Streaming) |   |  Host C (Bulk)  |   |
|   |  [C Monitor Agent]  |   |  [C Monitor Agent]  |   | [C Monitor Agent|   |
+-------------|-------------------------|------------------------|------------+
              | (TCP Telemetry)         | (TCP Telemetry)        | (TCP Telemetry)
              +-------------------------+------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------+
|                          C / Python Controller Layer                        |
|   - TCP Telemetry Collector (port 9091)                                      |
|   - Packet / Flow Telemetry Aggregation (TCP & UDP Traffic)                 |
|   - IPC / Data Pipeline to ML Engine                                        |
+---------------------------------------|-------------------------------------+
                                        v
+-----------------------------------------------------------------------------+
|                               ML Engine Layer                               |
|   1. Profiling & Clustering: scikit-learn (K-Means / DBSCAN)                |
|      - Device & Application Traffic Behavior Grouping                       |
|   2. Congestion Prediction: TensorFlow / Keras (GRU Time-Series)            |
|      - Multi-step ahead link saturation & queue buildup forecasting         |
|   3. Explainability: SHAP (Kernel/Tree/Deep Explainer)                      |
|      - Real-time attribution: Why was a flow deprioritized or throttled?    |
+---------------------------------------|-------------------------------------+
                                        v
+-----------------------------------------------------------------------------+
|                          Backend API Layer (Flask)                          |
|   - REST & WebSocket endpoints for Real-Time Metrics                        |
|   - Model Inference & SHAP explanation serving                              |
|   - Network Policy & QoS rule dispatch                                      |
+---------------------------------------|-------------------------------------+
                                        v
+-----------------------------------------------------------------------------+
|                         Frontend Dashboard (React)                          |
|   - Live Traffic & Bandwidth Visualizer                                     |
|   - User & Device Cluster Map                                               |
|   - GRU Congestion Risk Gauges                                              |
|   - Interactive SHAP Feature Importance Explanations                        |
+-----------------------------------------------------------------------------+
```

## 2. Key Modules & Technology Stack

| Component | Technology | Primary Role |
| :--- | :--- | :--- |
| **Monitoring Agent** | C (Sockets, pcap/raw) | Lightweight, low-overhead endpoint telemetry capture (TCP/UDP flows, bytes, RTT, jitter, loss) |
| **Controller IPC** | TCP Sockets (`protocol.h`) | Structured binary frame communication between distributed agents and central manager |
| **ML Engine** | Python 3, scikit-learn, TensorFlow, SHAP | Profiling (K-means/DBSCAN), congestion forecasting (GRU), and XAI (SHAP values) |
| **Backend API** | Flask, Flask-CORS | REST APIs serving live metrics, predictions, and explanation payloads |
| **Frontend UI** | React, Vite | Real-time adaptive traffic visualization and admin dashboard |
| **Emulation & Testing** | Mininet, iperf3 | Virtualized LAN topologies and controlled synthetic traffic generation |

## 3. Communication Protocol Specification
All inter-process network telemetry adheres to the fixed-size binary frame defined in `network/common/protocol.h`:
- **Magic**: `0x4E544D31` (`NTM1`)
- **Header**: 20 bytes (Magic, Version, Message Type, Payload Length, Timestamp)
- **Telemetry Payload**: Host ID, 5-tuple flow identifiers (src/dst IP & port, protocol), byte/packet counters, RTT, jitter, loss rate.
