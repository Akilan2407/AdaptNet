# Phase 15 — Decision Trace Module

**Explainable, User-Aware ML System for Adaptive Network Traffic Management in Small LANs**

The **Decision Trace Module** provides an end-to-end, deterministic traceability layer linking all 7 pipeline stages for every network traffic management decision made across the system. It connects data points from physical monitoring agents up through machine learning inference, policy rules, and Linux traffic control actuation.

---

## 1. Architecture & Pipeline Stages

```text
 Stage 1: Network Monitoring (C Agent / Ingestion)
     │   data/monitoring/network_metrics.csv
     ▼
 Stage 2: Feature Extraction (Python)
     │   data/features/network_features.csv
     ▼
 Stage 3: User Behavior Profiling (K-Means)
     │   data/profiling/behavior_profiles.csv
     ▼
 Stage 4: Congestion Prediction (GRU Neural Network)
     │   data/congestion/test_predictions.csv
     ▼
 Stage 5: Traffic Classification (Rule-Based Classifier)
     │   data/classification/classified_flows.csv
     ▼
 Stage 6: QoS Policy Engine (Deterministic Policy Rules)
     │   data/policy/qos_decisions.csv
     ▼
 Stage 7: Adaptive Traffic Control (Linux tc HTB Actuator)
     │   data/control/control_actions.csv
     ▼
 PHASE 15: DECISION TRACE MODULE
     ├── data/trace/decision_traces.csv
     ├── data/trace/decision_traces.jsonl
     ├── data/trace/trace_summary.json
     └── data/trace/trace_completeness.png & trace_stage_availability.png
```

---

## 2. Key Capabilities & Design Principles

1. **Deterministic Trace Identifiers**: Stable, monotonic trace IDs formatted as `TRC-000001` through `TRC-000053`, sorted by `(timestamp, device_id, flow_id)`. Re-running the pipeline yields identical mappings and order.
2. **Domain-Aware Matching**: Never joins records by row index or arbitrary array positions. Instead, utilizes domain identifiers:
   - Primary: Exact `flow_id` 5-tuple match (`device_id_src_ip:src_port->dst_ip:dst_port_protocol`).
   - Secondary: Combined `(device_id, flow_id)` exact match.
   - Proximity: Temporal tolerance matching (`delta_t <= 5.0 seconds`) for time-series features or dynamic metrics.
   - Device Temporal: Device-level timestamp match within 5.0s for device-level models (e.g. GRU congestion).
3. **Trace Completeness Classification**:
   - `COMPLETE`: All 7 pipeline stages successfully linked with complete inputs.
   - `PARTIAL`: Core stages present (Policy + Classification/Features/Monitoring), but optional stages fallback gracefully (e.g., GRU test set sequence boundaries).
   - `INCOMPLETE`: Critical stages missing or unmatched.
4. **Integrity Validation Engine**: Enforces schema invariants, format requirements, valid priorities/classes, and detects cross-stage anomalies such as `PRIORITY_CONTROL_MISMATCH`.
5. **Multi-Format Export**:
   - Tabular CSV: Fast scanning, reporting, spreadsheet analysis.
   - Structured JSON Lines (JSONL): Full nested payload, including raw stage dictionaries, 5-tuple components, and reason chains.
   - Summary JSON: Aggregate metrics, match rates, completeness counts.

---

## 3. Directory Layout

```text
ml/trace/
├── __init__.py                # Package exports
├── config.py                  # Default file paths, tolerances, and schemas
├── trace_schema.py            # DecisionTrace dataclass and serializers
├── trace_matcher.py           # Domain-based multi-stage linking algorithms
├── trace_builder.py           # Ingestion, sorting, and trace construction
├── trace_validator.py         # Integrity and cross-stage consistency validation
├── trace_export.py            # CSV, JSONL, and summary statistics exporter
├── trace_report.py            # Matplotlib Agg visualization generator
├── decision_trace.py          # CLI trace viewer with advanced filtering
├── test_decision_trace.py     # 15 comprehensive unit tests
└── README.md                  # This documentation
```

---

## 4. CLI Trace Viewer Usage

The CLI trace viewer (`decision_trace.py`) provides an interactive or scriptable interface for querying decision traces.

### 4.1 Show All Traces (Summary Table)
```bash
.venv/bin/python3 -m ml.trace.decision_trace
```

### 4.2 Inspect a Specific Trace by ID
```bash
.venv/bin/python3 -m ml.trace.decision_trace --trace-id TRC-000001
```
Output:
```text
================================================================================
DECISION TRACE: TRC-000001
Timestamp: 2026-09-23 15:24:43 | Device: device_1 | Flow: device_1_192.168.1.10:54321->192.168.1.1:80_TCP
Completeness: PARTIAL | Match Method: EXACT_FLOW_ID (Δt = 0.0 ms)
--------------------------------------------------------------------------------
1. MONITORING:       Throughput=12.5 Mbps, RTT=15.0 ms, Loss=0.0%
2. FEATURES:         Throughput=12.5 Mbps, RTT=15.0 ms, Conn=5
3. USER PROFILE:     Cluster 0 ("High Bandwidth / Streaming")
4. CONGESTION PRED:  Score=None, Class=UNKNOWN (fallback)
5. CLASSIFICATION:   Class=WEB (Confidence=1.00)
6. POLICY DECISION:  Base=NORMAL -> Adjustment=0 -> Final=NORMAL (Rule: RULE-WEB-DEFAULT)
7. NETWORK CONTROL:  Action=CLASS_NORMAL -> Class=1:30 (Status=DRY_RUN, Rule: RULE-000001)
--------------------------------------------------------------------------------
REASONING CHAIN:
  * device_id=device_1 (profile='High Bandwidth / Streaming', cluster=0)
  * throughput_mbps=12.5
  * traffic_class=WEB
  * predicted_congestion=UNKNOWN (score=None)
  * qos_priority=NORMAL (base=NORMAL, rule=RULE-WEB-DEFAULT, cong_adj=0, user_adj=0)
  * control_action=CLASS_NORMAL (target_class=1:30, status=DRY_RUN)
================================================================================
```

### 4.3 Filter by Device, Status, or Priority
```bash
# Filter all decisions for device_2
.venv/bin/python3 -m ml.trace.decision_trace --device device_2

# Filter by final priority HIGH
.venv/bin/python3 -m ml.trace.decision_trace --priority HIGH

# Filter by completeness status COMPLETE
.venv/bin/python3 -m ml.trace.decision_trace --status COMPLETE
```

---

## 5. Diagnostic Visualizations

Generate the diagnostic charts at any time:
```bash
.venv/bin/python3 -m ml.trace.trace_report
```
Outputs:
- `data/trace/trace_completeness.png`: Breakdown of Complete vs Partial vs Incomplete traces.
- `data/trace/trace_stage_availability.png`: Match rate percentage for each of the 7 stages.

---

## 6. Verification and Unit Testing

Run unit tests directly:
```bash
.venv/bin/pytest -v ml/trace/test_decision_trace.py
```
Or run the full ML test suite:
```bash
.venv/bin/pytest -v tests/ml/
```

---

## 7. Preparation for Phase 16 (SHAP Explanation Layer)

The outputs generated by Phase 15 serve as the direct inputs for Phase 16:
- `data/trace/decision_traces.jsonl`: Provides the feature vector, model prediction, and baseline context needed to compute KernelSHAP or TreeSHAP values for congestion predictions and policy weights.
- `decision_trace.py`: Can be extended in Phase 16 to attach feature attribution scores directly to the `DecisionTrace` output schema.
