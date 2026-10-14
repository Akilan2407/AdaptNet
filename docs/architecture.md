# System Architecture: Adaptive Network Traffic Management (AdaptNet)

## 1. Overview & Vision
The **Explainable, User-Aware ML System for Adaptive Network Traffic Management in Small LANs (AdaptNet)** provides real-time traffic monitoring, streaming machine learning-driven user/device profiling, proactive congestion prediction, dynamic QoS policy generation, and transparent explainability (XAI) for network administrators.

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
|                    Packet Sniffer & Flow Monitoring Layer                   |
|   - Real-Time Raw Socket / Scapy Packet Sniffer                             |
|   - C Telemetry Hub & Controller IPC (port 9091)                            |
|   - Packet Normalizer (packet_normalizer.py)                                |
|   - Stateful 5-Tuple Flow Aggregation & EWMA Rate Engine                    |
+---------------------------------------|-------------------------------------+
                                        v
+-----------------------------------------------------------------------------+
|                               ML Engine Layer                               |
|   1. Profiling & Clustering: scikit-learn (K-Means / DBSCAN)                |
|      - Device & Application Traffic Behavior Grouping                       |
|   2. Traffic Classification: Rule-based & ML Port / Protocol Classifier     |
|      - REAL_TIME (VoIP/Video), WEB, BULK_TRANSFER, INTERACTIVE, DNS         |
|   3. Congestion Prediction: Pure-NumPy GRU Recurrent Neural Network         |
|      - Proactive link saturation & queue buildup forecasting (<5ms latency) |
|   4. QoS Policy Engine: Multi-factor Priority & Rate-Limiting Engine        |
|      - Synthesizes Class + Congestion + Host Profile into QoS Priority      |
|   5. Explainability & Lineage: SHAP Feature Attributions & Decision Traces  |
|      - 7-stage lineage audit trail (TRC-LIVE-xxxxxx) with decision reasons  |
+---------------------------------------|-------------------------------------+
                                        v
+-----------------------------------------------------------------------------+
|                          Backend API Layer (Flask)                          |
|   - REST API on Port 5001 with CORS support                                 |
|   - Real-Time Live Capture & Streaming Pipeline endpoints (/api/live/*)     |
|   - Dual-Source support (?source=live vs. historical CSV datasets)          |
|   - Decision trace querying & local/global SHAP explanation serving         |
+---------------------------------------|-------------------------------------+
                                        v
+-----------------------------------------------------------------------------+
|                         Frontend Dashboard (React)                          |
|   - Live Wire Sniffer with active 5-tuple flow & ML prediction tables       |
|   - Interactive Decision Lineage Modal with SHAP attribution breakdown     |
|   - Telemetry Monitoring with Historical vs. Live Wire Stream toggle        |
|   - User & Device Cluster Map, GRU Congestion Risk Gauges, and SHAP charts  |
+-----------------------------------------------------------------------------+
```

## 2. Key Modules & Technology Stack

| Component | Technology | Primary Role |
| :--- | :--- | :--- |
| **Packet Sniffer** | Python (`scapy`, raw socket monitor) / C | Real-time live wire packet interception on physical/virtual network adapters |
| **Real-Time Streaming** | Python (`ml/realtime/`) | Header normalization, stateful 5-tuple flow aggregation, EWMA rate estimator, and timeout eviction |
| **Host Profiling** | `scikit-learn` (`K-Means`, `DBSCAN`) | Behavioral clustering (High-Throughput, Low-Bandwidth, Bursty) |
| **Traffic Classification** | Rule heuristics + Decision Trees | Dynamic application class tagging (VoIP, Web, Bulk Transfer, DNS) |
| **Congestion Forecasting** | Pure-NumPy GRU Recurrent Neural Network | Preemptive queue saturation forecasting using trained `.keras`/`h5` weights |
| **QoS Policy Engine** | Rule-Based Priority Matrix | Dynamic priority tier assignment (`CRITICAL`, `HIGH`, `NORMAL`, `LOW`) and recommended rate limits |
| **Explainable AI (XAI)** | `SHAP` & Decision Trace Engine | 7-stage lineage records and real-time local metric attribution |
| **Backend REST API** | Flask 3.x, Flask-CORS (Port 5001) | Serving live pipeline endpoints and historical benchmark data |
| **Frontend UI** | React 18, Vite, Lucide icons (Port 3000) | Real-time glassmorphic network operations dashboard |
| **Emulation & Testing** | `pytest`, `Mininet`, `iperf3` | Automated regression testing (51 tests) and virtualized topology emulation |

## 3. Communication Protocol Specification
All inter-process network telemetry adheres to the fixed-size binary frame defined in `network/common/protocol.h`:
- **Magic**: `0x4E544D31` (`NTM1`)
- **Header**: 20 bytes (Magic, Version, Message Type, Payload Length, Timestamp)
- **Telemetry Payload**: Host ID, 5-tuple flow identifiers (src/dst IP & port, protocol), byte/packet counters, RTT, jitter, loss rate.
