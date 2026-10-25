# SENTRIX Data Directory and Provenance Review

This directory contains the training, validation, testing, and lab evaluation datasets for SENTRIX.

## 1. Dataset Provenance & Attribution

| Dataset | Source / Institution | Version / Release | License / Terms | Reference |
| :--- | :--- | :--- | :--- | :--- |
| **CIC-DDoS2019** | Canadian Institute for Cybersecurity (CIC), University of New Brunswick (UNB) | 1.0 (Captures: Jan 12 & Mar 11, 2019) | Academic & Research Use with attribution | Sharafaldin et al. (2019) |
| **CIC-IDS2017** | Canadian Institute for Cybersecurity (CIC), University of New Brunswick (UNB) | 1.0 (Captures: July 3–7, 2017) | Academic & Research Use with attribution | Sharafaldin et al. (2018) |

> **Attribution**:
> Iman Sharafaldin, Arash Habibi Lashkari, Saqib Hakak, and Ali A. Ghorbani, "Developing Realistic Distributed Denial of Service (DDoS) Attack Dataset and Taxonomy", IEEE 53rd International Carnahan Conference on Security Technology (ICCST), 2019.

## 2. Directory Structure

```
data/
├── raw/
│   ├── CIC-DDoS2019/         # Primary offline candidate dataset (CSV-01-12, CSV-03-11)
│   │   ├── CSV-01-12/        # Day 1: Reflection DDoS attacks (DNS, LDAP, MSSQL, NTP, SNMP, SSDP, UDP, Syn, TFTP)
│   │   └── CSV-03-11/        # Day 2: LDAP, MSSQL, NetBIOS, Portmap, Syn, UDP, UDPLag
│   └── CIC-IDS2017/          # Secondary intrusion & baseline dataset (8 daily captures)
├── processed/                # Cleaned data, train/val/test splits, and manifests
│   ├── combined.csv          # Cleaned multi-capture dataset
│   ├── train.csv             # Training split (60%)
│   ├── val.csv               # Validation split for hyperparameter tuning & threshold calibration (20%)
│   ├── test.csv              # Held-out test split for final candidate comparison (20%)
│   └── manifest.json         # Versioned metadata, split counts, and feature definitions
└── lab/                      # Controlled, synthetic, and replayed demonstration traffic
```

## 3. Label Semantics

All datasets in `processed/` are mapped to a standardized binary classification schema:

| Clean Label | Binary Target (`label`) | Semantic Meaning | Runtime Interpretation |
| :--- | :---: | :--- | :--- |
| `BENIGN`, `Normal` | `0` | Normal network traffic | Non-malicious flow; no alert or mitigation. |
| `DDoS`, `PortScan`, `DoS`, etc. | `1` | Attack / Malicious pattern | Malicious or anomalous burst; candidate for policy evaluation. |

## 4. Feature Schema v1.0.0

The Phase 2 baseline establishes feature schema version `1.0.0` consisting of 14 runtime-extractable flow statistics:

1. `Total Length of Fwd Packets`: Cumulative bytes sent in forward direction (bytes)
2. `Bwd Packet Length Max`: Maximum packet length in backward direction (bytes)
3. `Flow Bytes/s`: Rate of flow throughput in bytes per second (bytes/s)
4. `Fwd IAT Total`: Total inter-arrival time between forward packets (microseconds)
5. `Bwd IAT Total`: Total inter-arrival time between backward packets (microseconds)
6. `Fwd PSH Flags`: Count of PSH flags set on forward packets (count)
7. `Fwd Packets/s`: Packet rate in forward direction (packets/s)
8. `FIN Flag Count`: Count of FIN flags observed (count)
9. `Fwd Avg Bytes/Bulk`: Average forward bulk transfer size (bytes)
10. `Bwd Avg Bulk Rate`: Backward bulk transfer rate (bytes/s)
11. `Subflow Fwd Packets`: Average number of packets in forward subflows (count)
12. `Init_Win_bytes_forward`: Initial TCP window size in forward direction (bytes)
13. `Active Mean`: Mean time a flow was active before becoming idle (microseconds)
14. `Idle Mean`: Mean time a flow was idle before becoming active (microseconds)

### Handling Rules & Excluded Columns:
* **Identifier & Socket Leakage**: `Flow ID`, `Source IP`, `Source Port`, `Destination IP`, `Destination Port`, `Timestamp`, and index columns (`Unnamed: 0`) are strictly excluded to prevent shortcut learning on IP addresses or target ports.
* **Non-finite Values**: Flows with `Flow Duration == 0` resulting in `inf` / `-inf` in rate columns (`Flow Bytes/s`, `Flow Packets/s`) are sanitized and dropped during preprocessing.
* **Whitespace Normalization**: Column names with leading/trailing whitespaces are stripped.
* **No Label Leakage**: Target labels (`Label`, `label`) are never present in feature matrices `X` and are strictly excluded from inference models.
