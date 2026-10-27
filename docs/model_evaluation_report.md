# SENTRIX Model Evaluation & Simulation Benchmark Report

## 1. Executive Summary

SENTRIX employs a dual-signal detection architecture combining machine learning flow inference with real-time volumetric traffic thresholds. To identify the optimal model for production runtime detection, two candidate algorithms were rigorously trained, cross-validated, and benchmarked on the standardized **CIC-DDoS2019** network flow dataset:

1. **Random Forest Classifier (`rf-1.0.0`) — SELECTED & APPROVED:**
   - Achieved **99.98% accuracy**, **99.99% precision**, **99.98% recall**, and an exceptionally low **0.58% false positive rate (FPR)**.
   - P95 inference latency of **6.56 ms**, well within the sub-10ms operational budget.
   - Exported as the runtime model artifact at [`models/approved_model.joblib`](../models/approved_model.joblib).
2. **Isolation Forest (`iforest-1.0.0`) — REJECTED:**
   - While achieving fast inference (4.81 ms), it exhibited an intolerable **53.31% false positive rate** on benign test traffic.
   - Automatically rejected under fail-closed safety criteria because dropping 53% of genuine user requests causes severe collateral outage.

---

## 2. Comparative Model Performance (`metrics.json`)

Both candidates were evaluated on a deterministic, stratified held-out test split of 40,000 network flows (347 benign, 39,653 DDoS flows) using Feature Schema `v1.0.0`.

| Metric | Random Forest (`rf-1.0.0`) | Isolation Forest (`iforest-1.0.0`) | Target Threshold | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Model Type** | Supervised Ensemble (100 Trees) | Unsupervised Anomaly Detection | — | — |
| **Validation Decision** | **APPROVED (Runtime Baseline)** | **REJECTED (High Collateral Risk)** | — | — |
| **Accuracy** | **99.9775%** | 99.4300% | $\ge 90.0\%$ | Passed (Both) |
| **Precision** | **99.9950%** | 99.5351% | $\ge 90.0\%$ | Passed (Both) |
| **Recall (Catch Rate)** | **99.9823%** | 99.8916% | $\ge 90.0\%$ | Passed (Both) |
| **F1-Score** | **99.9887%** | 99.7130% | $\ge 90.0\%$ | Passed (Both) |
| **False Positive Rate (FPR)** | **0.5764%** (2 / 347) | **53.3141%** (185 / 347) | $\le 5.0\%$ | **RF Passed / IF Failed** |
| **P95 Inference Latency** | **6.56 ms** | **4.81 ms** | $\le 100\text{ ms}$ | Passed (Both) |
| **Training Time** | 2.81 seconds | 0.088 seconds | — | Passed (Both) |
| **Calibrated Threshold** | 0.50 (Probability) | 0.2664 (Anomaly Score) | — | Standardized |

---

## 3. Confusion Matrices & Classification Breakdown

### 3.1 Random Forest Classifier (`rf-1.0.0`) — Approved

```
                         Predicted Benign (0)     Predicted Attack (1)      Total
Actual Benign (0)                345                       2                  347   (FPR: 0.58%)
Actual Attack (1)                  7                  39,646               39,653   (FNR: 0.018%)
Total Predicted                  352                  39,648               40,000
```
- **True Positives (TP):** 39,646 attacks correctly blocked.
- **True Negatives (TN):** 345 benign user sessions correctly permitted.
- **False Positives (FP):** 2 benign user sessions incorrectly flagged.
- **False Negatives (FN):** 7 stealth attack flows missed before volume threshold correlation.

### 3.2 Isolation Forest (`iforest-1.0.0`) — Rejected

```
                         Predicted Benign (0)     Predicted Attack (1)      Total
Actual Benign (0)                162                     185                  347   (FPR: 53.31%)
Actual Attack (1)                 43                  39,610               39,653   (FNR: 0.11%)
Total Predicted                  205                  39,795               40,000
```
- **Root Cause of Rejection:** Isolation Forest relies on tree partitioning depth. Normal bursty user web navigation features resemble low-density anomalous points, causing 185 out of 347 normal sessions to be misclassified as malicious (53.3% False Positive Rate).

---

## 4. Feature Schema Specification (`v1.0.0`)

The model receives a 14-dimensional normalized vector representing a 4-tuple bidirectional flow window:

| Index | Feature Key | Canonical Type | Security & Detection Significance |
| :---: | :--- | :---: | :--- |
| `0` | `Total Length of Fwd Packets` | Float | Measures total payload bytes in forward direction. Abnormally high in volumetric floods. |
| `1` | `Bwd Packet Length Max` | Float | Maximum response packet size. Highlights asymmetric reflection and amplification attacks. |
| `2` | `Flow Bytes/s` | Float | Core velocity metric (throughput in bytes per second). Directly triggers ingress alerts. |
| `3` | `Fwd IAT Total` | Float | Cumulative inter-arrival time between forward packets. Reveals automated scripted flooding. |
| `4` | `Bwd IAT Total` | Float | Cumulative inter-arrival time for reverse flow. Identifies non-responsive victim queues. |
| `5` | `Fwd PSH Flags` | Float | TCP PUSH flag count. High counts indicate HTTP GET or application layer request spamming. |
| `6` | `Fwd Packets/s` | Float | Packet velocity (PPS). Primary trigger for hardware CPU capacity saturation. |
| `7` | `FIN Flag Count` | Float | Premature connection teardown tracking. Used to detect connection-table exhaustion attacks. |
| `8` | `Fwd Avg Bytes/Bulk` | Float | Bulk payload transfer size. Differentiates heavy legitimate downloads from packet floods. |
| `9` | `Bwd Avg Bulk Rate` | Float | Server outbound bulk rate. Detects outbound saturation or reflection reflection patterns. |
| `10` | `Subflow Fwd Packets` | Float | Flow segment packet decomposition. Captures micro-bursts in stealth Slowloris vectors. |
| `11` | `Init_Win_bytes_forward` | Float | TCP initial congestion window size. Distinguishes authentic OS stacks from raw socket floods. |
| `12` | `Active Mean` | Float | Mean active duration before connection idle state. |
| `13` | `Idle Mean` | Float | Mean idle duration between packet trains. Low idle periods indicate robotic spamming. |

---

## 5. End-to-End Simulation Benchmark Evidence

To validate that the approved Random Forest model works effectively in a live reactive loop with the policy engine and virtual server infrastructure, a full 60-second chaos simulation was executed.

### 5.1 Telemetry Run Manifest

- **Simulation Run ID:** `sim_4f98c5d2f1ab`
- **Scenario:** Connection Overload Attack (`syn_flood`)
- **Total Duration:** 60 seconds (60 virtual ticks)
- **Target Ingress:** 10,000 PPS peak attack rate
- **Simulator Version:** `1.5.0`
- **Engine Version:** `rf-1.0.0`
- **Integrity Stamp:** SHA-256 Provenance Verified

### 5.2 Benchmark Scorecard Results

```json
{
  "run_id": "sim_4f98c5d2f1ab",
  "total_ticks": 60,
  "scorecard": {
    "time_to_detect_seconds": 0,
    "time_to_mitigate_seconds": 3,
    "attack_traffic_blocked_pct": 93.18,
    "collateral_legitimate_pct": 2.0,
    "downtime_seconds": 0,
    "average_availability_pct": 98.0,
    "average_latency_ms": 17.78,
    "max_latency_ms": 102.5,
    "total_ticks": 60,
    "attack_ticks": 43,
    "benign_ticks": 17,
    "true_positives": 43,
    "false_positives": 0,
    "true_negatives": 17,
    "false_negatives": 0,
    "precision": 1.0,
    "recall": 1.0,
    "false_positive_rate": 0.0,
    "total_offered_attack_packets": 369282.39,
    "total_blocked_attack_packets": 344096.93,
    "total_offered_legitimate_packets": 15009.36,
    "total_dropped_legitimate_packets": 300.82,
    "simulator_version": "1.5.0",
    "model_version": "rf-1.0.0",
    "schema_version": "1.0.0"
  }
}
```

### 5.3 Analysis of Simulation Metrics

1. **Instant AI Detection (`time_to_detect_seconds = 0`):**
   - The Random Forest model detected the attack signature on the exact first tick where attack traffic was introduced ($\text{tick } 9$), yielding a **$< 1.0\text{s}$ detection latency**.
2. **Rapid Defense Shield Engagement (`time_to_mitigate_seconds = 3`):**
   - In accordance with the dual-signal safety consensus, the policy engine confirmed the rate breach and engaged the rate-limiting defense shield within 3 seconds.
3. **93.18% Threat Traffic Neutralization:**
   - **Total Offered Attack:** $369,282.39$ packets
   - **Total Blocked Attack:** $344,096.93$ packets ($93.18\%$ blocked)
   - The virtual server CPU and bandwidth saturation were prevented from collapsing.
4. **98.0% Legitimate User Protection (Low Collateral):**
   - **Total Offered Legitimate Traffic:** $15,009.36$ packets
   - **Total Dropped Legitimate Traffic:** $300.82$ packets ($2.0\%$ collateral drop)
   - **$98.0\%$ of normal customers were served without interruption**, fulfilling the primary DevSecOps availability goal.
5. **Zero Downtime & Stable Latency:**
   - **Website Downtime:** `0.0s` (Zero crash or outage)
   - **Average Availability:** `98.0%`
   - **Average Latency:** `17.78 ms` (Queue stabilized from a congestion peak of `102.5 ms` back to baseline `15.0 ms` once the shield engaged).
6. **Live Classification Performance:**
   - Across the 60 ticks (43 attack ticks, 17 benign ticks), the policy generated **43 True Positives**, **17 True Negatives**, **0 False Positives**, and **0 False Negatives**, achieving **100% Precision**, **100% Recall**, and **0.0% False Positive Rate**.

---

## 6. Production Safety & Deployment Verification

- **Zero Host Mutation:** Verified that all mitigation rate limits and packet drops execute exclusively inside the virtual victim model without invoking host firewall (`iptables`, `nftables`, `netsh`) binaries.
- **Fail-Closed Gate:** In case of emergency or operator intervention, the global kill switch locks mitigation to `disabled` while preserving full read-only monitoring and audit trails.
