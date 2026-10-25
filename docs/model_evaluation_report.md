# SENTRIX Model Evaluation & Selection Report

## 1. Executive Summary

In accordance with Phase 2 of the SENTRIX Implementation Plan and PRD Requirements FR-03, FR-04, and FR-06, both candidate machine learning models (**Random Forest Classifier** and **Isolation Forest**) were reproducibly trained, calibrated, and evaluated on a held-out test split of the CIC-DDoS2019 dataset using feature schema version `1.0.0`.

* **Selected and Approved Candidate**: **Random Forest Classifier (v1.0.0)** is approved for the Phase 2 baseline. It achieved an F1-score of **99.97%**, precision of **99.98%**, recall of **99.96%**, false-positive rate of **1.73%**, and a p95 inference latency of **4.45 ms/observation** (well within the `< 100 ms` target).
* **Non-Selected Candidate**: **Isolation Forest (v1.0.0)** was evaluated as an unsupervised anomaly detection candidate. Despite tuning the decision threshold on validation data to maximize F1, it exhibited a **54.76% false-positive rate** on benign traffic. In compliance with safety gates, it is **not approved** for runtime rate-limiting or mitigation.

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

Measurements evaluated on the held-out test split (40,000 rows: 347 Benign, 39,653 DDoS):

| Metric | Proposed Target | Random Forest (Supervised) | Isolation Forest (Unsupervised) | Compliance Assessment |
| :--- | :---: | :---: | :---: | :--- |
| **Accuracy** | — | **99.95%** | 99.43% | Random Forest superior |
| **Precision** | ≥ 90.0% | **99.98%** | 99.52% | Both pass |
| **Recall** | ≥ 90.0% | **99.96%** | 99.90% | Both pass |
| **F1-Score** | ≥ 90.0% | **99.97%** | 99.71% | Both pass |
| **False Positive Rate (FPR)** | ≤ 5.0% | **1.73%** (6 / 347) | **54.76%** (190 / 347) | **RF passes; IF fails gate** |
| **ROC-AUC** | — | **0.99996** | 0.95789 | Random Forest near-optimal |
| **p95 Latency** | < 100 ms | **4.45 ms** | **5.00 ms** | Both well within latency budget |
| **Eval Time (40k rows)** | — | 0.118 s | 0.067 s | High-throughput capability |

### Confusion Matrices

#### Random Forest Classifier:
```
                Predicted Benign (0)   Predicted Attack (1)
Actual Benign            341                    6       (FPR: 1.73%)
Actual Attack             14                39,639      (FNR: 0.04%)
```

#### Isolation Forest:
```
                Predicted Benign (0)   Predicted Attack (1)
Actual Benign            157                  190       (FPR: 54.76%)
Actual Attack             40                39,613      (FNR: 0.10%)
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
