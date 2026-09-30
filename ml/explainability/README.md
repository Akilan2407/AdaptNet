# Phase 16 — SHAP Explainability Module

**Explainable, User-Aware ML System for Adaptive Network Traffic Management in Small LANs**

The **SHAP Explainability Module** provides feature attribution and model transparency for the Phase 10 GRU Congestion Prediction Model. It answers:
> *"Which network telemetry features contributed to this congestion forecast, by how much, and in what direction?"*

---

> [!IMPORTANT]
> **Core Explainability Principle**:
> SHAP explains the continuous output of the machine learning model (the GRU predicted congestion score). It does **not** independently explain the deterministic QoS Policy Engine (which is rule-based: `policy_rule_id` + `policy_reason`) or Linux `tc` traffic control actuation (which is logged by Phase 14).
>
> Furthermore, SHAP feature attributions represent mathematical contributions to the model's prediction score, **not real-world causation** (e.g., packet loss contributed positively to the predicted congestion score; it is not asserted as the universal real-world cause of network congestion).

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
     │   data/congestion/gru_congestion_model.keras
     ▼
 Stage 5: Traffic Classification (Rule Classifier)
     │   data/classification/classified_flows.csv
     ▼
 Stage 6: QoS Policy Engine (Deterministic Rules)
     │   data/policy/qos_decisions.csv
     ▼
 Stage 7: Adaptive Traffic Control (Linux tc HTB)
     │   data/control/control_actions.csv
     ▼
 Stage 8: Decision Trace Module (Phase 15)
     │   data/trace/decision_traces.csv / .jsonl
     ▼
 PHASE 16: SHAP EXPLAINABILITY MODULE
     ├── data/explainability/local_shap_explanations.csv
     ├── data/explainability/local_shap_explanations.jsonl
     ├── data/explainability/global_shap_importance.csv
     ├── data/explainability/global_feature_importance.png
     ├── data/explainability/shap_summary.png
     ├── data/explainability/local/TRC-XXXXXX.png
     ├── data/explainability/explainability_summary.json
     ├── data/explainability/explanation_selection.json
     └── data/explainability/explanation_records.jsonl (Phase 17 Contract)
```

---

## 2. Model & Sequence Dimensions

* **Model**: Trained Phase 10 GRU (`gru_congestion_predictor`, 17,153 parameters).
* **Scaler**: Phase 10 fitted `StandardScaler` across 21 telemetry columns.
* **Input Tensor Shape**: `(samples, 2, 11)`:
  * Timestep 0: Historical lookback summary state (`hist_mean_*`).
  * Timestep 1: Current anchor observation (`base_features`).
* **Canonical Recurrent Features**:
  1. `cluster_id`
  2. `throughput_mbps`
  3. `rtt_ms`
  4. `packet_loss_percent`
  5. `active_connections`
  6. `throughput_std`
  7. `rtt_std`
  8. `packet_loss_std`
  9. `total_flow_count`
  10. `tcp_flow_ratio`
  11. `udp_flow_ratio`

---

## 3. Explainer Selection & Compatibility

* **Primary Explainer**: `shap.GradientExplainer`. Verified compatible with TensorFlow 2.18 / Keras 3.8 and natively handles 3D recurrent tensor gradients without loss of sequence dimensions.
* **Fallback Explainer**: `shap.KernelExplainer` via a model-agnostic flattened wrapper.
* **Temporal Aggregation**:
  * Default: `SHAP_TIME_AGGREGATION = "mean_absolute"`:
    $$\text{Importance}(f) = \frac{1}{T} \sum_{t=1}^T |\phi_{t, f}|$$
  * Signed Direction:
    $$\text{Signed}(f) = \frac{1}{T} \sum_{t=1}^T \phi_{t, f}$$
    * $\phi > 0 \implies \text{"increased"}$ (pushed predicted congestion score upward)
    * $\phi < 0 \implies \text{"decreased"}$ (pushed predicted congestion score downward)

---

## 4. CLI Usage

### Run Full Pipeline
```bash
.venv/bin/python3 -m ml.explainability.trace_explainer
```

### Explain a Specific Trace
```bash
.venv/bin/python3 -m ml.explainability.trace_explainer --trace-id TRC-000047
```
Output:
```text
================================================================================
SHAP EXPLANATION: TRC-000047
Status: SUCCESS | Score: 0.3644 | Base: 0.3541
--------------------------------------------------------------------------------
Top Contributing Features:
   1. cluster_id               SHAP: +0.0065 (+) (val=1.0)
   2. total_flow_count         SHAP: +0.0053 (+) (val=22.0)
   3. throughput_mbps          SHAP: +0.0000 ( ) (val=0.0)
================================================================================
```

### Filter by Device
```bash
.venv/bin/python3 -m ml.explainability.trace_explainer --device h1
```

---

## 5. Verification & Testing

Run unit tests directly:
```bash
.venv/bin/pytest -v ml/explainability/test_shap_explainability.py
```
Or across the workspace suite:
```bash
.venv/bin/pytest -v tests/ml/
```

---

## 6. Phase 17 Contract

Phase 16 produces `data/explainability/explanation_records.jsonl`. Each record clearly separates model predictions, SHAP top contributors, QoS policy rules, and network control results for consumption by the Natural-Language Explanation Module (Phase 17).
