# Phase 17 — Natural-Language Explanation Module

**Explainable, User-Aware ML System for Adaptive Network Traffic Management in Small LANs**

The **Natural-Language Explanation Module** converts raw network metrics, GRU time-series forecasts, SHAP feature attributions, QoS policy rules, and Linux traffic control actuation into clear, factual, and human-understandable explanations.

---

> [!IMPORTANT]
> **Core Explainability Principle**:
> * **SHAP values explain contributions to the GRU congestion prediction.** They do not establish real-world causation (e.g. packet loss contributed positively to the model's prediction score; it is not asserted as the universal real-world cause of network congestion).
> * **SHAP values do not independently determine the QoS policy.** The policy engine is deterministic and rule-based (`policy_rule_id` + `policy_reason`).
> * **The module strictly distinguishes between requested actions and actual actuation status** (`DRY_RUN`, `SUCCESS`, `FAILED`, `SKIPPED`).

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
 Stage 9: SHAP Explainability Module (Phase 16)
     │   data/explainability/local_shap_explanations.csv / .jsonl
     ▼
 PHASE 17: NATURAL-LANGUAGE EXPLANATION MODULE
     ├── data/explanations/natural_language_explanations.csv
     ├── data/explanations/natural_language_explanations.jsonl
     ├── data/explanations/explanation_report.txt
     ├── data/explanations/explanation_summary.json
     ├── data/explanations/explanation_status.png
     └── data/explanations/top_shap_features.png
```

---

## 2. Explanation Structure & Sections

Every complete natural-language explanation consists of six distinct, factual sections:

1. **Network Observation**: Summarizes factual measured telemetry (RTT, packet loss, throughput, active connections, concurrent flows).
2. **Congestion Prediction**: States the continuous score $\in [0, 1]$ and discrete categorical class (`LOW`, `MEDIUM`, `HIGH`) predicted by the GRU.
3. **Main Feature Contributions (SHAP)**: Lists top feature attributions, signed impacts, and directional semantics (`increased` / `decreased`) without asserting real-world causation.
4. **Traffic Classification**: Identifies the application category (`BULK_TRANSFER`, `WEB`, `REAL_TIME`, etc.) and metadata rule reason.
5. **QoS Policy Decision**: Details the deterministic policy rule ID and exact policy reason explaining why the priority was selected.
6. **Network Control Action**: Documents the resulting rate-shaping action (`APPLY`, `UPDATE`), target HTB class, interface, and status (`DRY_RUN`, `SUCCESS`, `FAILED`, `SKIPPED`).

---

## 3. Directory Layout

```text
ml/explanation/
├── __init__.py                     # Package exports
├── config.py                       # File paths, thresholds, and configuration
├── explanation_templates.py        # Deterministic sentence and template builder
├── explanation_builder.py          # ExplanationRecord dataclass and stage coordinator
├── explanation_validator.py        # Fidelity and cross-stage consistency validator
├── trace_loader.py                 # Phase 15 decision trace loader
├── shap_loader.py                  # Phase 16 SHAP outputs loader
├── policy_loader.py                # Phase 13 QoS policy loader
├── control_loader.py               # Phase 14 network control loader
├── report_generator.py             # Text report and diagnostic plot generator
├── explanation_generator.py        # Primary CLI and pipeline entrypoint
├── test_explanation_generator.py   # 15 comprehensive unit tests
└── README.md                       # This documentation
```

---

## 4. CLI Usage

### Run Full Explanation Pipeline
```bash
.venv/bin/python3 -m ml.explanation.explanation_generator
```

### Explain a Specific Decision Trace
```bash
.venv/bin/python3 -m ml.explanation.explanation_generator --trace-id TRC-000047
```
Example Output:
```text
================================================================================
DECISION EXPLANATION: TRC-000047
Status: SUCCESS | Timestamp: 2026-09-12 16:01:27 | Device: h1
Flow: h1_192.168.1.10:45672->192.168.1.11:5201_TCP
--------------------------------------------------------------------------------
For device h1, flow h1_192.168.1.10:45672->192.168.1.11:5201_TCP, observed network conditions included throughput of 0.00 Mbps, 0 active connection(s), and 1 concurrent flow(s).

The GRU congestion model predicted a congestion score of 0.3644, corresponding to MEDIUM congestion. The primary model contributions were: total_flow_count (1.0) decreased the predicted congestion score (SHAP: -0.0087); cluster_id (1.0) increased the predicted congestion score (SHAP: +0.0062); throughput_mbps (0.0) had a neutral effect on the predicted congestion score (SHAP: +0.0000). These contributions reflect mathematical attribution toward the GRU model's score, not real-world causation.

The flow was classified as BULK_TRANSFER based on configured traffic classification rules. The device was grouped into behavior profile cluster 1 ('High-Flow-Activity').

The QoS policy engine applied rule POLICY_BULK_MED_CONGESTION and assigned LOW priority. Policy rationale: BULK_TRANSFER traffic during MEDIUM predicted congestion received LOW priority.

The traffic control action APPLY (HTB class 1:40) on interface s1-eth1 was simulated in dry-run mode and was not applied to the live network.
================================================================================
```

---

## 5. Verification & Testing

Run unit tests directly:
```bash
.venv/bin/pytest -v ml/explanation/test_explanation_generator.py
```
Or across the full workspace suite:
```bash
.venv/bin/pytest -v tests/ml/
```
All **156 unit tests** across Phases 7–17 pass with zero regressions.
