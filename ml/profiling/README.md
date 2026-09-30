# Phase 8: User Behavior Profiling Module

Explainable, User-Aware ML System for Adaptive Network Traffic Management in Small LANs

---

## 1. Purpose

The **User Behavior Profiling Module (Phase 8)** analyzes network traffic behaviors of connected devices and users within a Local Area Network (LAN) and categorizes them into distinct behavioral profiles using unsupervised machine learning. 

```
Phase 7: Feature Extraction
(data/features/network_features.csv)
            │
            ▼
==================================================
PHASE 8: USER BEHAVIOR PROFILING PIPELINE
==================================================
  1. Telemetry Ingestion & Feature Validation
  2. Device-Level Aggregation (1 vector per device)
  3. Missing-Value Handling (Median Imputation)
  4. StandardScaler Normalization
  5. K-Means Evaluation (Inertia & Silhouette Score)
  6. Optimal K Selection & Model Training
  7. Factual Cluster Summary & Profile Labeling
  8. 2D PCA Visualization
==================================================
            │
            ├─► data/profiling/behavior_profiles.csv
            ├─► data/profiling/cluster_summary.csv
            ├─► data/profiling/clustering_evaluation.csv
            ├─► data/profiling/clustering_model.pkl
            ├─► data/profiling/scaler.pkl
            ├─► data/profiling/clustering_features.json
            └─► data/profiling/cluster_visualization.png
            │
            ▼
Future Modules:
- Phase 9: Congestion Prediction Engine (GRU)
- Phase 10: Explainability Engine (SHAP)
- Phase 13: QoS Policy Enforcement
```

---

## 2. Why User Behavior Profiling is Needed

Modern LAN traffic is highly heterogeneous:
- Video streaming and large file transfers generate sustained high throughput.
- Web browsing and DNS generate intermittent, low-bandwidth bursts with high connection churn.
- IoT sensors transmit periodic telemetry packets with low concurrency.

Traditional static Quality-of-Service (QoS) rules rely on rigid port-based classifications or static IP mappings. However, DHCP reassignment breaks static IP bindings, and modern applications tunnel diverse traffic over standard ports (e.g. 443). By profiling the **observed statistical behavior** of devices dynamically:
1. The network management system understands what types of behavior patterns currently exist.
2. Downstream predictive modules (Phase 9 Congestion Prediction) can ingest user profile context to foresee link bottlenecks.
3. Policy decisions can be made based on transparent, data-driven behavior classes rather than arbitrary assumptions.

---

## 3. Input Data Specifications

The module reads the validated feature dataset produced by Phase 7:
```
data/features/network_features.csv
```

### Key Principles:
- **Device Identity**: Devices are identified strictly by `device_id` (e.g. `h1`, `h2`), representing permanent host endpoints. IP addresses (`src_ip`, `dst_ip`) are treated as ephemeral network-layer addresses, not permanent user identities.
- **No Packet Clustering**: Clustering is performed exclusively on aggregated device-level behavioral profiles, not individual network packets or raw flow rows.

---

## 4. Behavior Features Catalog

The profiling module extracts behavior-related network features originating from Phase 7:

| Feature Name | Category | Unit | Description |
| :--- | :--- | :---: | :--- |
| `mean_throughput_mbps` | Volume / Rate | Mbps | Average observed throughput across the device's flows |
| `throughput_std` | Variability | Mbps | Standard deviation of throughput (traffic burstiness) |
| `mean_rtt_ms` | Latency | ms | Mean Round-Trip Time across active TCP connections |
| `rtt_std` | Latency Jitter | ms | Standard deviation of RTT |
| `mean_packet_loss_percent` | Reliability | % | Mean observed packet loss percentage |
| `mean_active_connections` | Concurrency | Count | Mean simultaneous active transport sockets |
| `total_flow_count` | Activity | Count | Total volume of monitored flow records |
| `tcp_flow_ratio` | Traffic Mix | Ratio [0, 1] | Proportion of flows utilizing TCP |
| `udp_flow_ratio` | Traffic Mix | Ratio [0, 1] | Proportion of flows utilizing UDP |
| `active_hours_count` | Temporal | Hours | Number of distinct active hours recorded for device |

---

## 5. Device-Level Aggregation

Phase 7 outputs multiple flow records over time for each host. To model user and device behavior patterns, these flow-level records are aggregated by `device_id`:

$$\mathbf{x}_{\text{device}} = \left[ \bar{T}, \sigma_T, \bar{L}, \sigma_L, \bar{P}, \bar{C}, N_{\text{flows}}, R_{\text{tcp}}, R_{\text{udp}}, H_{\text{active}} \right]$$

- For metrics already calculated as device aggregates in Phase 7 (`mean_throughput_mbps`, `tcp_flow_ratio`, etc.), the module retrieves the device summary.
- Temporal span (`active_hours_count`) is computed via unique hour count.
- Each device is represented as a single vector in the clustering feature space.

---

## 6. Missing-Value Handling Strategy

Network telemetry inherently contains missing values:
- UDP flows are connectionless and do not record TCP RTT handshakes (`mean_rtt_ms` is NaN).
- In short LAN sessions, zero packet drops may occur (`mean_packet_loss_percent` is unmeasured or NaN).

### Documented Imputation Strategy:
1. **No Arbitrary Guessing**: We never fabricate arbitrary values.
2. **Median Imputation**: If a feature is partially observed across the network, missing values are imputed using the **empirical median** of that feature across observed devices.
3. **Safe Fallback**: If a feature is completely unobserved across all devices (100% NaN, e.g. a LAN test where latency was not captured on any host), the module falls back to `0.0` with clear logging.
4. **Non-Destructive**: The original Phase 7 dataset is never modified.

---

## 7. StandardScaler Normalization

Features have radically different physical scales:
- `total_flow_count`: $10^0$ to $10^4$
- `mean_throughput_mbps`: $0.0$ to $100.0$
- `tcp_flow_ratio`: $0.0$ to $1.0$

Without scaling, distance-based algorithms like K-Means would be dominated entirely by flow counts.

We apply scikit-learn's `StandardScaler`:
$$z = \frac{x - \mu}{\sigma}$$
Each feature is centered to zero mean and scaled to unit variance. The fitted scaler is saved to `data/profiling/scaler.pkl` to guarantee identical normalization in future phases.

---

## 8. K-Means Clustering Algorithm

**K-Means** is the primary clustering algorithm. It partitions $N$ device vectors into $K$ disjoint clusters $S = \{S_1, S_2, \dots, S_K\}$ by minimizing the within-cluster sum of squares (WCSS / Inertia):

$$\min_{S} \sum_{i=1}^{K} \sum_{\mathbf{x} \in S_i} \|\mathbf{x} - \boldsymbol{\mu}_i\|^2$$

- **Deterministic Initialization**: Configured with `random_state=42` and `n_init=10` to ensure complete reproducibility.
- **Convergence**: Iteratively assigns devices to nearest centroids and updates centroid positions until convergence.

---

## 9. K Selection Strategy

Rather than blindly assuming a fixed cluster count $K$, the module tests candidate $K$ values across a configurable range (e.g. $K \in [2, 6]$).

The optimal $K$ is selected based on:
1. Maximizing the **Silhouette Score**.
2. Evaluating the **Elbow / Inertia reduction rate**.
3. Small LAN constraints ($K < N$).

---

## 10. Inertia

**Inertia** measures cluster compactness:
$$\text{Inertia} = \sum_{i=1}^{n} \min_{\boldsymbol{\mu}_j \in C} (\|\mathbf{x}_i - \boldsymbol{\mu}_j\|^2)$$
- Decreases monotonically as $K$ increases.
- Used to observe the "elbow point" where additional clusters yield diminishing returns in variance reduction.

---

## 11. Silhouette Score

The **Silhouette Score** measures how similar a device is to its own cluster compared to neighboring clusters:

$$s(i) = \frac{b(i) - a(i)}{\max(a(i), b(i))}$$

- $a(i)$: Mean intra-cluster distance from sample $i$ to all other points in the same cluster.
- $b(i)$: Mean nearest-cluster distance from sample $i$ to points in the closest neighboring cluster.
- Range: $[-1.0, +1.0]$. High positive values indicate well-separated, cohesive clusters.

Results are exported to `data/profiling/clustering_evaluation.csv`.

---

## 12. Cluster Interpretation & Profile Types

Cluster IDs (`Cluster 0`, `Cluster 1`, ...) are mathematical labels. After clustering, the module computes factual summary statistics for each cluster and derives descriptive profile labels based on clearly defined, relative thresholds:

- **High-Throughput**: Clusters exhibiting top-tier average bandwidth consumption.
- **High-Flow-Activity / Connection-Heavy**: Clusters characterized by high flow counts and active sockets.
- **Low-Activity**: Clusters with low flow counts and minimal throughput.
- **Moderate-Activity / Baseline-Activity**: Balanced intermediary usage patterns.

> **Important Boundary Rule**:
> Descriptions are factual statements about observed network utilization. The profiling module does NOT infer user priority, "good vs. bad" behavior, or execute QoS bandwidth throttling.

---

## 13. Optional DBSCAN Comparison

Density-Based Spatial Clustering of Applications with Noise (**DBSCAN**) is implemented strictly as an **exploratory comparison**:
- Identifies core points with at least `min_samples` neighbors within distance `eps`.
- Labels isolated outliers as noise (`-1`).
- Does not require pre-specifying $K$.
- K-Means remains the main pipeline algorithm because small LANs often have sparse density distributions where DBSCAN classifies most points as noise.

---

## 14. PCA 2D Visualization

Because device vectors occupy high-dimensional feature space, **Principal Component Analysis (PCA)** is used **strictly for 2D visualization**:
- Projects scaled features onto the first 2 principal orthogonal variance axes.
- Plots devices as annotated points color-coded by cluster membership.
- Saved to `data/profiling/cluster_visualization.png`.
- **Note**: PCA axes represent composite variance directions, not raw physical network metrics.

---

## 15. Output Files Reference

| File Path | Format | Description |
| :--- | :---: | :--- |
| `data/profiling/behavior_profiles.csv` | CSV | Device-level assignments (`device_id`, `cluster_id`, `profile_label`, metrics) |
| `data/profiling/cluster_summary.csv` | CSV | Per-cluster mean metrics, device counts, and factual descriptions |
| `data/profiling/clustering_evaluation.csv` | CSV | K evaluation table (`k`, `inertia`, `silhouette_score`) |
| `data/profiling/clustering_model.pkl` | Pickle | Trained scikit-learn `KMeans` model |
| `data/profiling/scaler.pkl` | Pickle | Fitted scikit-learn `StandardScaler` |
| `data/profiling/clustering_features.json` | JSON | List of exact features used during training |
| `data/profiling/cluster_visualization.png` | PNG | 2D PCA cluster scatter plot with device annotations |

---

## 16. Commands & Usage

### Default Execution
```bash
python3 ml/profiling/behavior_profiler.py
```

### Custom Inputs & Outputs
```bash
python3 ml/profiling/behavior_profiler.py \
    --input data/features/network_features.csv \
    --output data/profiling/behavior_profiles.csv \
    --min-k 2 \
    --max-k 4
```

### Run Optional DBSCAN Comparison
```bash
python3 ml/profiling/behavior_profiler.py \
    --algorithm dbscan \
    --eps 0.8 \
    --min-samples 2
```

### Run Test Suite
```bash
python3 -m pytest -v ml/profiling/test_profiling.py
```

---

## 17. Limitations & Small LAN Handling

1. **Sample Size Boundaries**: In small LAN testbeds (e.g. 3–5 hosts), $K$ is bounded by $K < N$. The pipeline dynamically limits the evaluated $K$ range to avoid mathematical errors.
2. **Homogeneous Traffic Sessions**: If synthetic traffic generation runs identical workloads on all hosts, clusters will reflect uniform statistics. Diverse traffic scenarios (e.g. mixed bulk vs streaming) produce richer profile separation.
3. **Temporal Scope**: Profile labels reflect the observation window of the capture file. Continuous online re-profiling is deferred to future operational phases.
