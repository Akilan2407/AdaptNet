# Phase 12: Traffic Classification Module

## 1. Purpose

The Traffic Classification Module categorizes network flows into standardized, actionable traffic categories using transport layer and network telemetry metadata collected by the monitoring agent.

> **Core Principle**:
> The classifier estimates traffic categories from network metadata. A port-based rule does not prove the exact application generating a flow.

---

## 2. Why Traffic Classification Is Needed

In an explainable, user-aware network management architecture, QoS policy decisions cannot rely solely on device identity or overall congestion scores. A single workstation may run concurrent sessions:
- Interactive shell sessions (low-latency, low-bandwidth)
- Real-time video conferencing (low-jitter, bounded latency)
- Background bulk data transfers (throughput-hungry, delay-tolerant)

Assigning a traffic category to each flow allows the downstream **Phase 13 QoS Policy Engine** to enforce granular, differentiated traffic management:
$$\text{Device Profile (Phase 8)} + \text{Traffic Category (Phase 12)} + \text{Congestion Forecast (Phase 10)} \implies \text{QoS Action (Phase 13)}$$

---

## 3. Metadata Used

The classifier operates exclusively on telemetry fields extracted from flow headers:
- `protocol`: Transport protocol (`TCP`, `UDP`)
- `src_port`: Source port number ($1 \le \text{port} \le 65535$)
- `dst_port`: Destination port number ($1 \le \text{port} \le 65535$)
- `src_ip`, `dst_ip`: IPv4 endpoint addresses
- `throughput_mbps`: Flow throughput in megabits per second
- `rtt_ms`: Flow round-trip time in milliseconds
- `packet_loss_percent`: Observed packet loss percentage
- `active_connections`: Concurrent connection count
- `timestamp`: Observation timestamp

---

## 4. Traffic Categories

The module defines 6 configurable categories:

| Traffic Category | Description | Typical Network Requirements |
| :--- | :--- | :--- |
| **DNS** | Domain name queries and responses | Very low latency, immediate dispatch |
| **REAL_TIME** | Audio/video conferencing, VoIP, WebRTC | Low jitter, low bounded delay, packet drop tolerance |
| **WEB** | Standard web browsing (HTTP, HTTPS) | Moderate latency, bursty transmission |
| **INTERACTIVE** | Remote shells (SSH, Telnet), Remote Desktop (RDP, VNC) | Low round-trip delay, small packet sizes |
| **BULK_TRANSFER** | File downloads, SMB, FTP, benchmark tests (iPerf3) | High sustained throughput, delay-tolerant |
| **OTHER** | Unrecognized or non-standard port traffic | Best-effort default |

---

## 5. Port and Protocol Rules

Rules are defined declaratively in `config.py`:

```python
PORT_RULES = {
    "DNS": {
        "protocols": ["UDP", "TCP"],
        "ports": [53],
        "ranges": [],
    },
    "REAL_TIME": {
        "protocols": ["UDP"],
        "ports": [5004, 5005, 5060, 5061],
        "ranges": [(3478, 3481), (5000, 6000)],
    },
    "WEB": {
        "protocols": ["TCP"],
        "ports": [80, 443, 8080, 8443],
        "ranges": [],
    },
    "INTERACTIVE": {
        "protocols": ["TCP"],
        "ports": [22, 23, 3389, 5900],
        "ranges": [],
    },
    "BULK_TRANSFER": {
        "protocols": ["TCP"],
        "ports": [20, 21, 445, 5201, 873],
        "ranges": [],
    },
}
```

---

## 6. Rule Priority Ordering

Rules are evaluated deterministically in a strict precedence order to prevent race conditions or ambiguous classifications:
1. `DNS`
2. `REAL_TIME`
3. `WEB`
4. `INTERACTIVE`
5. `BULK_TRANSFER`
6. `OTHER` (Fallback)

---

## 7. Confidence Calculation

Every classification assigns a rule-based confidence score:
- **`1.0`**: Exact protocol and well-known single port match (e.g., TCP 443 $\rightarrow$ WEB).
- **`0.85`**: Protocol and port range match (e.g., UDP 3478 $\rightarrow$ REAL_TIME).
- **`0.70`**: Secondary metadata heuristic match (e.g., sustained TCP throughput $>20$ Mbps).
- **`0.0`**: Unmatched fallback to `OTHER`.

> This is a deterministic **rule confidence metric**, not an empirical machine-learning probability.

---

## 8. Classification Reason

For explainability, every flow includes a human-readable justification:
- `"TCP destination port 443 matched WEB rule"`
- `"UDP destination port 53 matched DNS rule"`
- `"TCP destination port 5201 matched BULK_TRANSFER rule"`
- `"No configured metadata rule matched"`

---

## 9. Privacy & No-Payload-Inspection Guarantee

The classifier adheres to strict privacy and operational constraints:
- **Zero Payload Inspection**: Packet data contents, HTTP request bodies, TLS handshakes, application messages, and DNS queries are never inspected.
- **Header Metadata Only**: Classification depends entirely on IP/port 5-tuples and statistical flow metrics.

---

## 10. Output Artifacts

All outputs are saved to `data/classification/`:

| Artifact | Type | Description |
| :--- | :--- | :--- |
| `classified_flows.csv` | CSV | Primary dataset with flow IDs, categories, confidence, and reasons |
| `classification_summary.json` | JSON | Summary counts, class distributions, and protocol metrics |
| `classification_rules.json` | JSON | Complete declarative rules and evaluation priority specification |
| `traffic_class_distribution.png` | PNG | Diagnostic bar chart of traffic category distribution |
| `protocol_distribution.png` | PNG | Breakdown of transport protocols across all flows |
| `class_by_protocol.png` | PNG | Stacked breakdown of traffic classes partitioned by transport protocol |

---

## 11. Limitations & Context

1. **Synthetic Testbed Uniformity**: In the current Mininet telemetry dataset, flows originate from benchmark traffic generators on TCP port 5201, correctly categorizing 100% of these flows as `BULK_TRANSFER`.
2. **Port Masquerading**: Applications operating on non-standard ports (e.g., HTTP over port 9000 or custom UDP tunnels) will be classified as `OTHER` unless custom rules are added to `config.py`.

---

## 12. Relationship with Other Phases

- **Phase 8 (Device Profiling)**: Clusters devices based on behavioral aggregates over time. Phase 12 classifies individual flows based on session metadata. They are orthogonal.
- **Phase 10 (Congestion Forecasting)**: Predicts future link congestion using a GRU model. It does not classify traffic types.
- **Phase 13 (QoS Policy Engine)**: Will consume device profile, traffic class, and congestion prediction simultaneously to prioritize critical flows and throttle delay-tolerant flows.

---

## 13. How to Run

### Execute Classification Pipeline
```bash
python ml/classification/traffic_classifier.py
```

### Validate and Generate Visualizations
```bash
python ml/classification/classification_report.py
```

### Run Unit Tests
```bash
pytest ml/classification/
```
