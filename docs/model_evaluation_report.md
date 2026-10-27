# SENTRIX Model Evaluation Report

## 1. Summary

Two ML models were trained and tested to detect DDoS attacks on the CIC-DDoS2019 dataset.

- **Selected: Random Forest.** Very high accuracy, very few false alarms, and fast.
- **Rejected: Isolation Forest.** Too many false alarms on normal traffic, so it is not safe to use for mitigation.

| Metric | Random Forest (Selected) | Isolation Forest (Rejected) |
| :-- | :-: | :-: |
| F1-score | **99.99%** | 99.71% |
| Precision | **99.99%** | 99.54% |
| Recall | **99.98%** | 99.89% |
| False positive rate | **0.58%** (2 of 347) | 53.31% (185 of 347) |
| p95 latency | 6.56 ms | 4.81 ms |

Targets: F1/precision/recall at least 90%, false positive rate at most 5%, latency under 100 ms. Random Forest meets all of them. Isolation Forest fails the false positive limit.

## 2. Data and Split

- **Data Source:** CIC-DDoS2019 (University of New Brunswick (UNB) / Canadian Institute for Cybersecurity).
- **Size:** 200,000 rows.
- **Cleaning:** Removed whitespace, dropped IP/port/timestamp/flow ID columns, fixed `inf` and `NaN` values.
- **Split (fixed seed 42, stratified):**
  - Train: 120,000 (60%)
  - Validation: 40,000 (20%), used for tuning only
  - Test: 40,000 (20%), used for the final comparison only (347 benign, 39,653 DDoS)

## 3. Features (Schema v1.0.0)

These 14 features are numbers about one network flow (a short session of packets between two machines). The model reads them to decide if traffic is normal or a DDoS attack.

- **Fwd** = traffic going from sender to receiver.
- **Bwd** = traffic coming back.

### 3.1 Feature Table

| # | Feature | Simple meaning |
| :-: | :-- | :-- |
| 1 | `Total Length of Fwd Packets` | Total bytes sent in the forward direction |
| 2 | `Bwd Packet Length Max` | Size of the biggest packet that came back (bytes) |
| 3 | `Flow Bytes/s` | Bytes sent per second (data speed) |
| 4 | `Fwd IAT Total` | Total time gap between forward packets (microseconds) |
| 5 | `Bwd IAT Total` | Total time gap between backward packets (microseconds) |
| 6 | `Fwd PSH Flags` | Number of forward packets with the PSH flag ("send this data now" signal) |
| 7 | `Fwd Packets/s` | Forward packets sent per second |
| 8 | `FIN Flag Count` | Number of packets with the FIN flag (signal to close a connection) |
| 9 | `Fwd Avg Bytes/Bulk` | Average bytes in one forward bulk transfer |
| 10 | `Bwd Avg Bulk Rate` | Speed of backward bulk transfer (bytes/s) |
| 11 | `Subflow Fwd Packets` | Average forward packets in one subflow |
| 12 | `Init_Win_bytes_forward` | TCP window size at connection start (how much data the receiver can accept) |
| 13 | `Active Mean` | Average time the flow stays active before going idle |
| 14 | `Idle Mean` | Average idle time between bursts |

### 3.2 Why These Features Help Detect DDoS

- **Volume:** `Flow Bytes/s`, `Fwd Packets/s`, and `Total Length of Fwd Packets` are very high in an attack because the attacker sends packets very fast.
- **Timing:** `Fwd IAT Total`, `Active Mean`, and `Idle Mean` show if traffic looks like a machine (very regular) or a human (bursty). Attack traffic is often very regular.
- **Reply pattern:** `Bwd Packet Length Max`, `Bwd IAT Total`, and `Bwd Avg Bulk Rate` show how much the target replies. In reflection attacks, this pattern is different from normal traffic.
- **TCP flags and handshake:** `Fwd PSH Flags`, `FIN Flag Count`, and `Init_Win_bytes_forward` show connection behaviour. A value of `-1` usually means the window value was not recorded (for example, UDP traffic).

### 3.3 Why the Order Is Fixed

The order stays the same in training and in the live system, so every number always sits in the same position. If the order changes, the model will give wrong predictions.

## 4. Confusion Matrices (Test Set)

**Random Forest (Approved)**

```
                 Predicted Benign (0)   Predicted Attack (1)
Actual Benign          345                    2        (FPR: 0.58%)
Actual Attack            7               39,646        (FNR: 0.018%)
```

**Isolation Forest (Experimental / Rejected)**

```
                 Predicted Benign (0)   Predicted Attack (1)
Actual Benign          162                  185        (FPR: 53.31%)
Actual Attack           43               39,610        (FNR: 0.11%)
```

FPR = false positive rate (benign flagged as attack). FNR = false negative rate (attack missed).

## 5. How Scores Work

- **Random Forest:** Gives a score from 0 to 1. 0.5 or higher means attack. It is not a true probability, so do not treat it as one.
- **Isolation Forest:** Gives an anomaly score. Below 0.2664 (tuned on validation data) means anomaly. It is not a probability.

## 6. Limitations

1. **Single dataset:** Results may drop on new attack types or different networks.
2. **Network speed:** Flow timings depend on link speed. 10 Gbps+ links need retraining or new thresholds.
3. **Few benign samples:** Only 347 benign flows in the test set (under 1%). High scores are partly because attacks dominate the data, so the false positive rate is the more meaningful number.

## 7. Decision

- **Approved:** Random Forest v1.0.0 (`models/approved_model.joblib`) as the Phase 2 baseline.
- **Kept for comparison only:** Isolation Forest.

## 8. Live Pipeline Test (Phase 5)

Latest recorded run: Python 3.14.7 on Windows. The persisted pipeline
benchmark uses a temporary SQLite database. Evidence is recorded in
`data/fixtures/benchmark_evidence.json`.
Inference latency is measured around `run_flow_inference` (100 warmed-up
iterations); throughput and memory are measured separately over 30 persisted
pipeline flows, including database writes and audit logging. These are
different measurements and should not be compared as if both describe full
HTTP request latency.

| Check | Latest result | Target / status |
| :-- | :-: | :-- |
| Mean inference latency (100 runs) | 12.953 ms | under 10 ms (not met) |
| P50 / P95 / P99 inference latency | 12.385 / 16.956 / 18.796 ms | Reported |
| Persisted pipeline throughput (30 flows) | 6.4 flows/sec | Real-time bounded workload; reported |
| Peak memory growth | 1.261 MB | under 512 MB (met) |

The bounded HTTP generator smoke test also exercised the running local API.
In the `all` scenario run, four scenarios returned HTTP 201 and the normal
scenario timed out on its first request. A subsequent five-flow SYN-flood
scenario run returned HTTP 201 for all five requests. The initial timeout's
cause is undetermined; do not count it as a successful request or as a
benchmark latency measurement.

The current run does not meet the mean inference-latency target. Benchmark
results can vary with the machine, Python/runtime, database, and system load;
use the JSON evidence as the source for the latest recorded run and repeat
the benchmark before drawing performance conclusions.

**Failure handling:** If the model file is missing or corrupt, the system does not crash. It logs an audit event (`pipeline_failure: inference_failed`) and continues safely.