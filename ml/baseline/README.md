# Phase 11: Congestion Baseline Module

## 1. Purpose

The Congestion Baseline Module implements and evaluates deterministic, non-machine-learning prediction baselines for forecasting future network congestion in small local area networks (LANs). It provides standard reference benchmarks against which the sequence-aware Phase 10 Gated Recurrent Unit (GRU) model is systematically evaluated on the exact same test dataset.

> **Important Assessment Principle**:
> Baseline methods provide reference predictions against which the GRU model can be evaluated. Their results do not by themselves establish that one method is universally superior.

---

## 2. Why Baselines are Required

In applied machine learning for network systems, evaluating a neural network solely in isolation provides an incomplete picture of its practical utility. Complex models introduce computational overhead, inference latency, and memory footprints. Simple baselines establish whether:
1. Recurrent sequence modeling captures non-trivial temporal dynamics beyond immediate persistence.
2. Simpler, lighter heuristics (constant or moving average) offer sufficient forecasting accuracy under stationary traffic.
3. Observed prediction errors stem from dataset limitations (such as class imbalance or small sample sizes) rather than architectural flaws.

---

## 3. Baseline Methods

### 1. Persistence / Naive Baseline
Assumes network congestion is stationary over short prediction horizons:
$$\hat{C}(t + H) = C(t)$$
- Takes the most recent valid observation prior to the prediction horizon.
- Requires no parameter fitting or historical memory beyond the latest telemetry report.

### 2. Moving Average Baseline
Smooths short-term fluctuations by averaging the $k$ most recent observations:
$$\hat{C}(t + H) = \frac{1}{k} \sum_{j=1}^{k} C(t - j + 1)$$
- Configurable window size (default: $k = 5$).
- Filters out high-frequency noise and transient bursts while tracking local baseline drift.
- Does not fabricate observations if fewer than $k$ points exist; utilizes available valid history down to minimum threshold.

### 3. Linear Trend Baseline
Fits an ordinary least squares (OLS) linear trend across recent historical observations and extrapolates into the future:
$$C(t) = a \cdot t + b \implies \hat{C}(t + H) = a \cdot (t + H) + b$$
- Captures monotonic trajectories (such as queue buildup or buffer drain).
- Employs numerical time representations relative to the first observation to avoid floating-point overflow.
- Handles constant series ($a = 0$) and single-observation fallbacks safely.
- Output predictions are strictly clipped to the physical score domain $[0.0, 1.0]$.

---

## 4. Input Data & Preprocessing

The module consumes artifacts from Phase 7, Phase 9, and Phase 10:

| Input File | Source | Description |
| :--- | :--- | :--- |
| `data/congestion/test_dataset.csv` | Phase 9 | Chronological test partition (3 sequences) with future targets and anchor timestamps |
| `data/congestion/test_predictions.csv` | Phase 10 | Sample-by-sample GRU predictions and actual targets |
| `data/congestion/congestion_label_config.json` | Phase 9 | Scoring formulation weights and class boundary thresholds |
| `data/congestion/model_evaluation.json` | Phase 10 | Benchmark evaluation metrics of the trained GRU model |
| `data/features/network_features.csv` | Phase 7 | Raw historical telemetry observations used to extract multi-step time series per device |

---

## 5. Strict Temporal Leakage Prevention

To guarantee scientific validity, all baseline predictions enforce strict temporal constraints:
1. **Temporal Precedence**: For every prediction target at timestamp $t_{\text{target}}$, all historical observations used by the baseline must satisfy:
   $$t_{\text{obs}} \le t_{\text{anchor}} < t_{\text{target}}$$
2. **Target Isolation**: Baseline algorithms never access `future_congestion_score` or `future_congestion_class` during inference.
3. **Explicit Validation**: A dedicated leakage check verifies that $t_{\text{obs}} < t_{\text{target}}$ for every test record, raising a `ValueError` if temporal ordering is violated.

---

## 6. Evaluation Metrics

Baselines are evaluated on the exact same test dataset population as Phase 10 using identical mathematical formulas:

### Continuous Regression Metrics:
- **MAE**: Mean Absolute Error ($\frac{1}{N} \sum |y_i - \hat{y}_i|$)
- **MSE**: Mean Squared Error ($\frac{1}{N} \sum (y_i - \hat{y}_i)^2$)
- **RMSE**: Root Mean Squared Error ($\sqrt{\text{MSE}}$)
- **$R^2$**: Coefficient of Determination

### Discrete Categorical Metrics:
Predictions are mapped to discrete classes using the documented Phase 9 thresholds:
- $C < 0.33 \implies \text{LOW}$
- $0.33 \le C \le 0.67 \implies \text{MEDIUM}$
- $C > 0.67 \implies \text{HIGH}$

Calculated classification metrics:
- Accuracy, Macro-averaged Precision, Macro-averaged Recall, Macro-averaged F1-score, and $3 \times 3$ Confusion Matrix.

---

## 7. Factual Model Comparison with GRU

The module compares the Phase 10 GRU model against all three baselines strictly using calculated numerical differences:
- **Error Delta**: $\Delta_{\text{MAE}} = \text{MAE}_{\text{GRU}} - \text{MAE}_{\text{baseline}}$
- **Percentage Improvement**:
  $$\text{Improvement} = \left( \frac{\text{Error}_{\text{baseline}} - \text{Error}_{\text{GRU}}}{\text{Error}_{\text{baseline}}} \right) \times 100$$
  *(Reported as negative if GRU has higher error, or omitted if baseline error is zero).*
- **Objective Reporting**: No model is labeled as "winner", "best", or "worst". Numerical values are reported as measured.

---

## 8. Output Artifacts

All outputs are saved to `data/baseline/`:

| Artifact | Type | Description |
| :--- | :--- | :--- |
| `persistence_predictions.csv` | CSV | Sample-by-sample Persistence predictions, actual values, and absolute errors |
| `moving_average_predictions.csv` | CSV | Sample-by-sample Moving Average predictions, actual values, and errors |
| `linear_trend_predictions.csv` | CSV | Sample-by-sample Linear Trend predictions, actual values, and errors |
| `baseline_evaluation.json` | JSON | Complete regression and classification metrics for each baseline |
| `model_comparison.csv` | CSV | Standardized comparative performance matrix (GRU vs. Baselines) |
| `baseline_summary.json` | JSON | Full execution summary, sample counts, metrics, and numerical deltas |
| `mae_comparison.png` | PNG | High-resolution bar chart comparing MAE across models |
| `rmse_comparison.png` | PNG | High-resolution bar chart comparing RMSE across models |
| `baseline_predictions.png` | PNG | Chronological trajectory showing actual congestion vs. all predictions |

---

## 9. Limitations & Test Set Context

1. **Small Test Sample Size**: The test partition in the current synthetic LAN dataset contains 3 samples.
2. **Homogeneous Uncongested Ground Truth**: All 3 test samples have actual future congestion scores of `0.0` (`LOW`). Consequently, baselines that predict historical steady-state values (0.0) achieve zero error ($0.0000$) trivially.
3. **GRU Bias on Small Data**: The GRU model (trained on 9 samples) outputs conservative predictions around `0.359` (lower edge of MEDIUM), resulting in an MAE of `0.3594`. As additional synthetic traffic scenarios with active congestion are generated in Mininet, baseline and GRU dynamics will differentiate across non-zero regimes.

---

## 10. How to Run

### Execute Baseline Pipeline
```bash
python ml/baseline/evaluate_baselines.py
```

### Run Unit Tests
```bash
pytest ml/baseline/
```
