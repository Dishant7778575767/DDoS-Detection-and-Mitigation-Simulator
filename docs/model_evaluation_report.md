# SENTRIX Model Evaluation & Selection Report

## 1. Executive Summary

In accordance with Phase 2 of the SENTRIX Implementation Plan and PRD Requirements FR-03, FR-04, and FR-06, both candidate machine learning models (**Random Forest Classifier** and **Isolation Forest**) were reproducibly trained, calibrated, and evaluated on a held-out test split of the CIC-DDoS2019 dataset using feature schema version `1.0.0`.

* **Selected and Approved Candidate**: **Random Forest Classifier (v1.0.0)** is approved for the Phase 2 baseline. It achieved an F1-score of **99.99%**, precision of **99.99%**, recall of **99.98%**, false-positive rate of **0.58%** (only 2 benign flows misclassified out of 347), and a p95 inference latency of **6.56 ms/observation** (well within the `< 100 ms` target).
* **Non-Selected Candidate**: **Isolation Forest (v1.0.0)** was evaluated as an unsupervised anomaly detection candidate. Despite tuning the decision threshold on validation data to maximize F1 (calibrated threshold: `0.2664`), it exhibited a **53.31% false-positive rate** on benign traffic (185 false alarms out of 347). In compliance with safety gates, it is **not approved** for runtime rate-limiting or mitigation.

---

## 2. Dataset & Split Provenance

* **Dataset Source**: University of New Brunswick (UNB) / Canadian Institute for Cybersecurity (CIC) CIC-DDoS2019 corpus.
* **Corpus Processing**:
  * Total prepared rows: 200,000 observations across reflection DDoS captures.
  * Cleaning: Stripped whitespace, dropped socket identifiers (`Source IP`, `Destination IP`, `Source Port`, `Destination Port`, `Timestamp`, `Flow ID`), sanitized `inf` and `NaN` rates resulting from zero-duration flows.
  * Deterministic Stratified Split (`seed=42`):
    * **Training Partition**: 120,000 rows (60%)
    * **Validation Partition**: 40,000 rows (20%) — used exclusively for hyperparameter tuning and Isolation Forest threshold calibration.
    * **Held-out Test Partition**: 40,000 rows (20%) — used solely for final candidate comparison.
  * Split Manifest: Recorded in `data/processed/manifest.json`.

---

## 3. Versioned Feature Schema (`v1.0.0`)

Both candidates and the runtime inference engine adhere strictly to feature schema `1.0.0` defined in `backend/app/features/definitions.py`. Exactly 14 features are extracted in fixed order:

| Index | Feature Name | Unit | Semantic Description |
| :---: | :--- | :--- | :--- |
| 1 | `Total Length of Fwd Packets` | bytes | Total cumulative payload bytes in forward direction |
| 2 | `Bwd Packet Length Max` | bytes | Maximum backward packet size observed in flow |
| 3 | `Flow Bytes/s` | bytes/s | Flow byte throughput rate |
| 4 | `Fwd IAT Total` | µs | Total inter-arrival time between forward packets |
| 5 | `Bwd IAT Total` | µs | Total inter-arrival time between backward packets |
| 6 | `Fwd PSH Flags` | count | Count of PSH flags set on forward packets |
| 7 | `Fwd Packets/s` | packets/s | Forward packet transmission rate |
| 8 | `FIN Flag Count` | count | Number of packets with FIN flag set |
| 9 | `Fwd Avg Bytes/Bulk` | bytes | Average bytes per forward bulk transfer |
| 10 | `Bwd Avg Bulk Rate` | bytes/s | Backward bulk transfer rate |
| 11 | `Subflow Fwd Packets` | count | Average packets in forward subflows |
| 12 | `Init_Win_bytes_forward` | bytes | Initial forward TCP window advertisement |
| 13 | `Active Mean` | µs | Mean flow active duration before idle state |
| 14 | `Idle Mean` | µs | Mean flow idle duration between bursts |

---

## 4. Head-to-Head Held-Out Test Evaluation Results

Measurements evaluated on the held-out test split (40,000 rows: 347 Benign, 39,653 DDoS) loaded directly from `models/rf-1.0.0/metrics.json` and `models/iforest-1.0.0/metrics.json`:

| Metric | Proposed Target | Random Forest (Supervised) | Isolation Forest (Unsupervised) | Compliance Assessment |
| :--- | :---: | :---: | :---: | :--- |
| **Accuracy** | — | **99.98%** (`0.999775`) | 99.43% (`0.994300`) | Random Forest superior |
| **Precision** | ≥ 90.0% | **99.995%** (`0.999950`) | 99.54% (`0.995351`) | Both pass |
| **Recall** | ≥ 90.0% | **99.982%** (`0.999823`) | 99.89% (`0.998916`) | Both pass |
| **F1-Score** | ≥ 90.0% | **99.989%** (`0.999887`) | 99.71% (`0.997130`) | Both pass |
| **False Positive Rate (FPR)** | ≤ 5.0% | **0.58%** (2 / 347) | **53.31%** (185 / 347) | **RF passes; IF fails gate** |
| **p95 Latency** | < 100 ms | **6.56 ms** | **4.81 ms** | Both well within latency budget |
| **Training Time** | — | 2.81 s | 0.09 s | Fast convergence |

### Confusion Matrices (from `metrics.json`)

#### Random Forest Classifier (Approved):
```
                Predicted Benign (0)   Predicted Attack (1)
Actual Benign            345                    2       (FPR: 0.58%)
Actual Attack              7                39,646      (FNR: 0.018%)
```

#### Isolation Forest (Experimental / Rejected):
```
                Predicted Benign (0)   Predicted Attack (1)
Actual Benign            162                  185       (FPR: 53.31%)
Actual Attack             43                39,610      (FNR: 0.11%)
```

---

## 5. Score Conventions & Interpretations (FR-06)

* **Random Forest**:
  * Output: Classification probability via `predict_proba(X)[:, 1]`.
  * Score convention: Bounded in `[0.0, 1.0]`. Values $\ge 0.5$ indicate predicted malicious traffic.
  * Caveat: While highly separable on reflection attacks, raw tree probabilities must not be treated as mathematically calibrated Bayesian posterior probabilities in production.
* **Isolation Forest**:
  * Output: Decision score via `decision_function(X)`.
  * Score convention: Continuous real values. Scores $< 0.2664$ (the calibrated validation threshold) represent anomalies. Negative scores denote deeper isolation (higher anomalous intensity).
  * Caveat: In accordance with FR-06, anomaly scores are **not represented as probabilities**.

---

## 6. Documented Limitations

1. **Synthetic Environment Overfitting**: The models were trained and tested on the CIC-DDoS2019 captured testbed. Performance may degrade on novel zero-day attack vectors or network architectures with differing MTU and packet header distributions.
2. **Concept Drift**: Flow duration and inter-arrival times depend heavily on network link bandwidth. Deployments on high-speed 10Gbps+ links will require retraining or threshold recalibration.
3. **Imbalance Sensitivity**: Because benign flows in DDoS captures are minority subsets, unsupervised detectors like Isolation Forest struggle with false positives when normal traffic exhibits bursty behaviors.

---

## 7. Approval Record

* **Approved Model Artifact**: `models/approved_model.joblib`
* **Versioned Model Directory**: `models/rf-1.0.0/`
* **Feature Schema Compatibility**: Version `1.0.0` confirmed with `backend/app/features/definitions.py`.
* **Decision**: **Random Forest is approved** as the single Phase 2 baseline detection candidate. Isolation Forest is retained as an experimental anomaly comparator only.

---

## 8. Phase 5 Runtime Inference & Reliability Verification

During Phase 5 integration testing, the approved Random Forest artifact was benchmarked under live runtime pipeline conditions within Python 3.14 on Windows. Performance evidence is recorded in `data/fixtures/benchmark_evidence.json`:

* **Inference Latency (N=100)**:
  * **Mean**: `8.17 ms` (Target: `< 10.0 ms` — **MET**)
  * **P50**: `7.95 ms`
  * **P95**: `12.45 ms`
  * **P99**: `14.82 ms`
* **Runtime Memory Overhead**: `0.67 MB` peak allocation growth (Target: `< 512.0 MB` — **MET**).
* **Pipeline Throughput**: `10.0 flows/sec` sustained real-time transaction ingestion with full database persistence and audit logging.
* **Failure Auditing**: In the event of a missing or corrupt model artifact, the runtime pipeline gracefully catches the failure, records an immutable audit event (`pipeline_failure: inference_failed`), and prevents unhandled server crashes.
