# Phase 14 — Python Control Bridge & Reporting

Part of the **“Explainable, User-Aware ML System for Adaptive Network Traffic Management in Small LANs”** project.

---

## 1. Overview

The Python Control Bridge (`ml/control/`) links the machine learning and policy engine layers (Phases 8–13) with the underlying C network controller and Linux traffic control layer.

It coordinates:
1. **Decision Loading**: Ingesting Phase 13 `data/policy/qos_decisions.csv`.
2. **Metadata Sanitization**: Validating IP addresses, port ranges, protocols, and interface names against strict allowlists (`control_validator.py`).
3. **Dry-Run Simulation**: Generating deterministic `tc` command previews and maintaining synthetic state (`dry_run.py`).
4. **C Controller Coordination**: Invoking the compiled native binary (`network/controller/adaptive_controller`) or Python driver (`control_bridge.py`).
5. **Diagnostic Visualizations**: Generating publication-quality charts for action outcomes and traffic control class distribution (`control_report.py`).

---

## 2. Key Modules

| Module | File | Purpose |
|---|---|---|
| **Configuration** | `config.py` | Priority mappings, rate definitions, interface allowlists, and file paths. |
| **Input Validator** | `control_validator.py` | Strict IPv4, port, protocol, interface, and device validation preventing command injection. |
| **Decision Loader** | `decision_loader.py` | Parses flow 5-tuple from `flow_id` and attaches interface metadata. |
| **Dry-Run Engine** | `dry_run.py` | Simulates `tc` HTB qdisc, class, and filter operations without touching the kernel. |
| **Control Bridge** | `control_bridge.py` | End-to-end execution coordinator exporting CSVs and summary JSON. |
| **Diagnostic Visualizer** | `control_report.py` | Generates `control_actions.png` and `priority_control_distribution.png`. |
| **Unit Tests** | `test_control.py` | 16 deterministic tests verifying priority mapping, validation, updates, rollback, and determinism. |

---

## 3. Execution Commands

### Run Control Bridge (Default Dry-Run)
```bash
python ml/control/control_bridge.py
```

### Generate Diagnostic Charts
```bash
python ml/control/control_report.py
```

### Run Unit Tests
```bash
pytest ml/control/
```

### Run Full ML Suite
```bash
pytest tests/ml/
```

---

## 4. Output Artifacts

* `data/control/control_actions.csv`: Complete audit trail of every control action attempt.
* `data/control/control_state.csv`: Current state of rules applied across managed interfaces.
* `data/control/control_summary.json`: High-level execution metrics and success rates.
* `data/control/control_actions.png`: Bar chart of action outcomes (`DRY_RUN`, `SUCCESS`, `SKIPPED`, `FAILED`).
* `data/control/priority_control_distribution.png`: Bar chart of traffic control class allocations (`1:10` HIGH to `1:40` LOW).
