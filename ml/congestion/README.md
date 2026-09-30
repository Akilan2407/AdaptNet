# Phase 9: Congestion Dataset Module

Explainable, User-Aware ML System for Adaptive Network Traffic Management in Small LANs

> **Important Scope Statement:**  
> This phase prepares a time-series dataset for congestion prediction. It does **not** implement or evaluate the prediction model (LSTM, GRU, 1D-CNN), nor does it perform real-time QoS traffic control or policy enforcement.

---

## 1. Purpose

The **Congestion Dataset Module (Phase 9)** transforms raw telemetry and flow features collected in earlier phases into a structured, forward-looking **time-series sequence dataset**.

This dataset is specifically engineered to train the recurrent neural network models in **Phase 10 (Congestion Prediction Engine)** to predict upcoming network congestion **10 to 30 seconds into the future**.

```
Phase 6: Ingestion (network_metrics.csv)
                ↓
Phase 7: Feature Extraction (network_features.csv)
                ↓
Phase 8: User Behavior Profiling (behavior_profiles.csv)
                ↓
=============================================================
         PHASE 9: CONGESTION DATASET MODULE
=============================================================
  1. Telemetry Ingestion & Timestamp Validation
  2. Sampling Interval & Time Gap Characterization
  3. Feature Imputation & NaN Tracking
  4. Multi-Factor Congestion Score Formulation
  5. Categorical Class Labeling (LOW, MEDIUM, HIGH)
  6. Forward Target Construction (t → t + H)
  7. Historical Sequence Windowing ([t - W, t])
  8. Chronological Split (Train: 70%, Val: 15%, Test: 15%)
  9. Dataset Integrity Validation & Visualization
=============================================================
                ↓
data/congestion/
  ├── congestion_dataset.csv
  ├── train_dataset.csv
  ├── validation_dataset.csv
  ├── test_dataset.csv
  ├── dataset_statistics.json
  ├── congestion_label_config.json
  └── dataset_visualization.png
                ↓
Phase 10: Congestion Prediction Engine (GRU / LSTM / 1D-CNN)
```

---

## 2. Input Dataset

The module primarily ingests the validated feature dataset produced by Phase 7:
```
data/features/network_features.csv
```

### Contextual Inputs:
Where available, Phase 8 behavioral profiles (`data/profiling/behavior_profiles.csv`) are ingested to enrich telemetry records with the device's behavioral `cluster_id`.

> **Separation of Concerns:**  
> The Phase 8 `cluster_id` represents **user/device behavioral grouping** (e.g. streaming, IoT, low-activity). The congestion target represents **underlying physical network condition**. The cluster ID is never used as a proxy or label for congestion.

---

## 3. Historical Time Window

To forecast future congestion, sequential models require a historical observation context. The observation window is configurable:
- **Default**: `history_window_seconds = 30`
- **Definition**: For an anchor observation at timestamp $t_{\text{anchor}}$, the historical sequence captures all records within $[t_{\text{anchor}} - 30s, t_{\text{anchor}}]$.
- **Minimum Steps**: Sequences must contain at least `min_history_steps = 1` observations. Sequences with insufficient history are safely discarded and logged.

---

## 4. Prediction Horizon

The target network condition is defined strictly in the future:
- **Default Horizon**: `prediction_horizon_seconds = 10`
- **Supported Horizons**: `10s`, `20s`, `30s` (configurable via `--prediction-horizon`)
- **Matching Window**: The target is located within a tolerance window $[t + H - \Delta, t + H + \Delta]$ ($\Delta = 5s$) to account for discrete sampling intervals.

---

## 5. Feature Definitions

The dataset incorporates measurable physical telemetry indicators originating from Phase 7:

| Feature Name | Type | Unit | Description |
| :--- | :---: | :---: | :--- |
| `throughput_mbps` | float | Mbps | Instantaneous flow throughput rate |
| `rtt_ms` | float | ms | Observed round-trip latency (NaN for connectionless UDP) |
| `packet_loss_percent` | float | % | Flow packet loss percentage |
| `active_connections` | int | count | Concurrent active transport sockets |
| `throughput_std` | float | Mbps | Rolling standard deviation of throughput |
| `rtt_std` | float | ms | Latency jitter |
| `packet_loss_std` | float | % | Packet loss variability |
| `total_flow_count` | int | count | Monitored flow records on host |
| `tcp_flow_ratio` | float | ratio | Proportion of TCP flows |
| `udp_flow_ratio` | float | ratio | Proportion of UDP flows |
| `cluster_id` | int | ID | Phase 8 user behavioral profile cluster |

---

## 6. Congestion Score Formula

The **congestion score** is a continuous target metric bounded within $[0.0, 1.0]$. It is computed from measurable physical network conditions rather than synthetic or random values.

### Mathematical Formulation

$$\text{Congestion Score} = w_{\text{loss}} \cdot L_{\text{loss}} + w_{\text{rtt}} \cdot L_{\text{rtt}} + w_{\text{tp}} \cdot L_{\text{tp}} + w_{\text{conn}} \cdot L_{\text{conn}}$$

Where:
1. **Packet Loss Factor ($L_{\text{loss}}$)**:
   $$L_{\text{loss}} = \min\left(1.0, \frac{\text{packet\_loss\_percent}}{10.0}\right)$$
   *Weight: $w_{\text{loss}} = 0.35$ (buffer overflow and drop severity).*

2. **RTT Inflation Factor ($L_{\text{rtt}}$)**:
   $$L_{\text{rtt}} = \min\left(1.0, \frac{\max(0, \text{rtt\_ms} - 2.0)}{98.0}\right)$$
   *Weight: $w_{\text{rtt}} = 0.30$ (queue buildup and bufferbloat above 2.0ms baseline).*

3. **Bandwidth Load Factor ($L_{\text{tp}}$)**:
   $$L_{\text{tp}} = \min\left(1.0, \frac{\text{throughput\_mbps}}{100.0}\right)$$
   *Weight: $w_{\text{tp}} = 0.25$ (link saturation relative to 100 Mbps nominal capacity).*

4. **Active Sockets Concurrency ($L_{\text{conn}}$)**:
   $$L_{\text{conn}} = \min\left(1.0, \frac{\text{active\_connections}}{20.0}\right)$$
   *Weight: $w_{\text{conn}} = 0.10$ (connection pressure).*

> **Note on Interpretation:**  
> This score is a **dataset-derived congestion target** designed for model training. It is not presented as an absolute universal standard.

---

## 7. Congestion Class Thresholds

In addition to the continuous score, a 3-tier discrete classification target is assigned:

- **LOW**: $\text{Score} < 0.33$ (uncongested or light traffic)
- **MEDIUM**: $0.33 \le \text{Score} < 0.67$ (moderate load, emerging queue delay)
- **HIGH**: $\text{Score} \ge 0.67$ (severe link saturation, elevated RTT, or packet loss)

Thresholds are defined in [config.py](file:///Users/shivabalan/Desktop/Networks_Project/ml/congestion/config.py) and exported to `congestion_label_config.json`.

---

## 8. Missing-Data Handling

- **Partial Missing Values**: Imputed using the empirical feature median.
- **100% Unmeasured Metrics**: If an entire measurement type is absent (e.g. UDP flows without RTT, or capture with 0 packet drops), a safe baseline of `0.0` is imputed and recorded.
- **Missing Timestamps**: Corrupt or unparseable timestamps are rejected.
- **Missing Target**: Records without a future observation within the prediction horizon are discarded.
- **Missing Value Tracking**: Full statistics are logged in `dataset_statistics.json`.

---

## 9. Sequence Generation

For recurrent architectures (LSTM/GRU), the module produces sequences structured as:
```
sequence_id | device_id | sequence_start | sequence_end | prediction_timestamp | future_congestion_score | future_congestion_class | [historical features...]
```
Each sequence encapsulates the historical trajectory leading up to $t_{\text{anchor}}$, paired with the future target at $t_{\text{future}}$.

---

## 10. Chronological Data Splitting

Time-series data is split strictly in temporal order without random shuffling:
- **Training Set (70%)**: Earliest observation window
- **Validation Set (15%)**: Middle observation window
- **Testing Set (15%)**: Latest observation window

---

## 11. Data Leakage Prevention

Strict temporal barriers are enforced and validated:
$$\max(T_{\text{hist}}) \le T_{\text{anchor}} < T_{\text{future}}$$
$$\max(T_{\text{train}}) \le \min(T_{\text{val}}) \le \min(T_{\text{test}})$$
No future information is ever allowed to contaminate historical sequence vectors or training partitions.

---

## 12. Output Files Reference

| File Path | Format | Description |
| :--- | :---: | :--- |
| `data/congestion/congestion_dataset.csv` | CSV | Complete time-series dataset with future targets |
| `data/congestion/train_dataset.csv` | CSV | Chronological training partition (70%) |
| `data/congestion/validation_dataset.csv` | CSV | Chronological validation partition (15%) |
| `data/congestion/test_dataset.csv` | CSV | Chronological test partition (15%) |
| `data/congestion/dataset_statistics.json` | JSON | Record counts, missingness stats, class balance, intervals |
| `data/congestion/congestion_label_config.json` | JSON | Exact congestion formula weights and class thresholds |
| `data/congestion/dataset_visualization.png` | PNG | 2-panel plot of congestion curve over time & class distribution |

---

## 13. Limitations

1. **Synthetic Burstiness**: Short bursts in synthetic LAN testbeds result in uneven gaps between testing phases. The pipeline handles irregular intervals without inventing artificial measurements.
2. **Horizon Feasibility**: The maximum feasible prediction horizon is bounded by the session duration of monitored hosts.
3. **Threshold Sensitivity**: Class boundaries (0.33, 0.67) are dataset labeling heuristics and may be adjusted based on specific network capacities.

---

## 14. How to Run

### Default Execution
```bash
python ml/congestion/congestion_dataset.py
```

### Custom Prediction Horizon & Window
```bash
python ml/congestion/congestion_dataset.py \
    --history-window 30 \
    --prediction-horizon 20 \
    --low-threshold 0.30 \
    --high-threshold 0.70
```

### Run Unit Tests
```bash
pytest ml/congestion/
```

---

## 15. How Phase 10 Consumes the Dataset

Phase 10 (Congestion Prediction Engine) directly consumes `train_dataset.csv`, `validation_dataset.csv`, and `test_dataset.csv`:
1. Reshapes historical telemetry columns into 3D tensors: `(samples, timesteps, features)`.
2. Fits `StandardScaler` strictly on `train_dataset.csv` (never on validation or test sets).
3. Trains a GRU recurrent neural network to predict continuous `future_congestion_score` in $[0.0, 1.0]$.
4. Categorizes continuous predictions into discrete classes (`LOW`, `MEDIUM`, `HIGH`) for operator situational awareness.
5. Evaluates forecasting skill against persistence and historical mean baselines on `test_dataset.csv`.

---

## 16. Phase 10: GRU Congestion Prediction Architecture

The Phase 10 model is a sequence-aware Gated Recurrent Unit (GRU) neural network built with TensorFlow/Keras:

```text
Sequence Input: (batch_size, timesteps=2, features=11)
      ↓
GRU Layer (units=64, return_sequences=False, L2=1e-4)
      ↓
Batch Normalization
      ↓
Dropout (rate=0.20)
      ↓
Dense Projection Layer (units=32, activation='relu', L2=1e-4)
      ↓
Dropout (rate=0.20)
      ↓
Output Layer: Dense(1, activation='sigmoid', name='future_congestion_score')
```

### Key Design Principles:
1. **Recurrent Representation**: Recurrent connections in the GRU allow the model to model dynamic trajectories from historical context (Timestep 0) to instantaneous anchor telemetry (Timestep 1).
2. **Sigmoid Output Activation**: Since the target `future_congestion_score` is mathematically bounded within $[0.0, 1.0]$, sigmoid activation guarantees that predictions never extrapolate outside valid physical limits.
3. **Dual-Task Utility**: Continuous regression is the primary optimization objective (MSE loss), while discrete classification (`LOW`, `MEDIUM`, `HIGH`) provides secondary operational categorization for QoS policy engines.

---

## 17. Sequence Tensor Dimensions & Preprocessing

- **Input Tensor Shape**: `(samples, 2, 11)`
  - **Timestep 0**: Historical lookback state vector (`[cluster_id, hist_mean_throughput_mbps, hist_mean_rtt_ms, hist_mean_packet_loss_percent, hist_mean_active_connections, hist_mean_throughput_std, hist_mean_rtt_std, hist_mean_packet_loss_std, hist_mean_total_flow_count, hist_mean_tcp_flow_ratio, hist_mean_udp_flow_ratio]`)
  - **Timestep 1**: Current instantaneous anchor telemetry vector (`[cluster_id, throughput_mbps, rtt_ms, packet_loss_percent, active_connections, throughput_std, rtt_std, packet_loss_std, total_flow_count, tcp_flow_ratio, udp_flow_ratio]`)
- **Strict Leakage Prevention**:
  - `StandardScaler` is fitted **exclusively on `train_dataset.csv`**.
  - All target identifiers (`future_congestion_score`, `future_congestion_class`), timestamps (`prediction_timestamp`, `sequence_start`), and IDs (`sequence_id`, `device_id`) are stripped before tensor formatting.

---

## 18. Phase 10 Evaluation & Benchmarking

The model is evaluated on unseen test data and benchmarked against two standard reference heuristics:
1. **Naive Persistence Baseline**: Predicts that future congestion score equals the current anchor telemetry congestion score ($y_{t+\tau} = y_t$).
2. **Historical Mean Baseline**: Predicts the training set's mean congestion score ($y_{t+\tau} = \mu_{\text{train}}$).

### Evaluated Metrics:
- **Regression**: MAE, MSE, RMSE, $R^2$, and Max Absolute Error.
- **Classification**: Accuracy, Macro Precision, Macro Recall, Macro F1, and $3 \times 3$ Confusion Matrix.

---

## 19. Phase 10 Output Artifacts

| File | Type | Description |
| :--- | :--- | :--- |
| `data/congestion/gru_congestion_model.keras` | Keras | Trained GRU model weights and computation graph |
| `data/congestion/congestion_scaler.pkl` | Pickle | Fitted `StandardScaler` parameters (mean, scale) |
| `data/congestion/model_metadata.json` | JSON | Architecture parameters, training hyperparameters, final losses |
| `data/congestion/model_evaluation.json` | JSON | Test set regression & classification metrics, baseline deltas |
| `data/congestion/baseline_evaluation.json` | JSON | Detailed persistence & mean baseline performance metrics |
| `data/congestion/test_predictions.csv` | CSV | Row-by-row actual vs predicted scores, classes, and residuals |
| `data/congestion/training_loss.png` | PNG | Training vs validation loss curve across epochs |
| `data/congestion/actual_vs_predicted.png` | PNG | Actual vs predicted score scatter plot with ideal $y=x$ line |
| `data/congestion/prediction_error.png` | PNG | Residual error distribution and residual vs actual scatter plot |
| `data/congestion/congestion_confusion_matrix.png` | PNG | Heatmap of predicted vs actual categorical classes |

---

## 20. How to Train, Evaluate, and Predict

### 1. Train Model
```bash
python ml/congestion/train.py --epochs 30 --batch-size 32 --lr 0.001
```

### 2. Evaluate Model
```bash
python ml/congestion/evaluate.py
```

### 3. Run Inference via CLI
```bash
# Predict on an existing test sample
python ml/congestion/predict.py --sample 0

# Predict using explicit telemetry values
python ml/congestion/predict.py \
    --throughput 85.0 \
    --rtt 45.0 \
    --packet-loss 5.5 \
    --connections 15 \
    --cluster-id 1

# Output raw JSON for programmatic integration
python ml/congestion/predict.py --sample 0 --json
```

### 4. Run Full Test Suite
```bash
pytest ml/congestion/
```

---

## 21. Limitations & Small LAN Telemetry Observations

1. **Small Sample Size**: In local development environments and synthetic Mininet/LAN topologies, the dataset currently yields 13 total temporal sequences (9 Train, 1 Val, 3 Test).
2. **Class Imbalance in Test Set**: The test split contains predominantly uncongested telemetry (`score = 0.0`, `class = LOW`). While the model accurately converges on training data, evaluation metrics reflect test set sample distribution constraints.
3. **Early Stopping & Small Batches**: Mini-batch sizing automatically adapts to dataset size (`min(BATCH_SIZE, len(X_train))`) to guarantee stability on small LAN deployments.
