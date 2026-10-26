# SENTRIX Release Decision & Gate Verification Record

**Document Version:** 1.0.0  
**Release Candidate:** `v0.1.0-rc1`  
**Date:** 2026-10-26  
**Status:** Approved for Simulation & Authorized Isolated Linux Lab Demonstration  

---

## 1. Executive Summary

SENTRIX is an active defensive cybersecurity prototype designed to detect and safely mitigate Distributed Denial of Service (DDoS) traffic attacks. It combines flow-level machine learning inference with deterministic traffic rate thresholding inside a dual-signal hybrid policy engine.

As mandated by **PRD Section 10.3 and Section 13**, this document records the formal evaluation, verification evidence, accepted deviations, and sign-off decision across all four release gates for `v0.1.0-rc1`.

### Release Decision:
- **Default Production / Web Deployment Mode:** Approved exclusively in `MITIGATION_MODE=simulation`. Host networking, firewall rules, and OS kernel state are strictly immutable.
- **Isolated Linux Lab Mode:** Approved conditionally for authorized research and testing strictly inside the dedicated network namespace `sentrix0` on subnet `10.200.0.0/24` with signed authorization (`enforcement/approval.json`). Public or host-level deployment is strictly forbidden.

---

## 2. Release Gate Evidence Summaries

### Gate 1: Machine Learning Evaluation Gate (PRD 10.3.1, 13.1.1–13.1.3)
- **Dataset & Cleaning:** Trained on curated CIC-DDoS2019 partitions, deterministically split into 60% Train (119,738 flows), 20% Validation (39,913 flows), and 20% Test (39,913 flows). Split manifests persisted in `data/processed/split_manifest.json`.
- **Feature Schema:** Enforces standard Schema `1.0.0` (14 exact numerical flow features) defined in `backend/app/features/definitions.py`. Missing features or invalid schema versions fail closed (HTTP 422).
- **Candidate Comparison:**
  - **Random Forest Classifier (Selected & Approved):**
    - Accuracy: 99.987%
    - Macro F1: 99.989%
    - Malicious Precision: 99.995%
    - Malicious Recall: 99.982%
    - False Positive Rate (FPR): 0.58%
    - Mean Inference Latency: 6.56 ms (sub-10ms requirement met)
    - Persisted Artifact: `models/approved_model.joblib` with cryptographic metadata and SHA-256 fingerprint.
  - **Isolation Forest (Evaluated & Rejected):**
    - False Positive Rate: 53.31% (Unacceptable for automated active defense)
    - Macro F1: 67.57%
    - Formally rejected per `docs/model_evaluation_report.md`.
- **Gate Status:** **PASSED & APPROVED**.

---

### Gate 2: Simulation & Hybrid Policy Gate (PRD 10.3.2, 13.1.4–13.1.8)
- **Shared Pipeline Parity (TC-14):** Bounded synthetic traffic generator (`scripts/send_test_traffic.py`) and CSV replay tool (`scripts/replay_dataset.py`) traverse the exact same runtime ingestion pipeline (`POST /api/v1/traffic/flows`). All demonstration records are tagged with provenance indicators (`demo-generator:`, `demo-replay:`).
- **Dual-Signal Hybrid Policy (TC-01, TC-02, TC-03, TC-04, TC-13):**
  - Normal traffic -> `monitor`
  - Abnormal burst (Threshold Exceeded Only) -> `alert` (no mitigation)
  - ML Malicious Score Only -> `alert` (no mitigation)
  - Dual Consensus (ML >= 0.75 AND Threshold Exceeded) -> `request_mitigation`
  - Single signals are cryptographically and logically barred from triggering rate-limit actions.
- **Fail-Closed Safety Gate (TC-06, TC-07, TC-11, TC-15):**
  - Allowlist protection blocks mitigation requests targeting `127.0.0.1`, `::1`, `8.8.8.8`, `1.1.1.1`, and gateway subnets.
  - Parameter bounds enforce 100 <= PPS <= 50,000 and 10s <= duration <= 300s.
  - Cooldown deduplication throttles flapping alerts on target IPs for 30 seconds.
  - Emergency disable switch immediately locks down active mitigations and blocks subsequent actions.
- **Simulation Invariant Verification (TC-08):**
  - End-to-end integration test asserts that in `simulation` mode, zero host firewall commands, zero route modifications, zero traffic control (`tc`) mutations, and zero privileged subprocess calls occur.
- **Gate Status:** **PASSED & APPROVED**.

---

### Gate 3: Isolated Linux Lab Gate (PRD 10.3.3, 13.2.1–13.2.6)
- **Strict Boundary Confinement:** All privileged enforcement logic (`enforcement/agent.py`) is restricted exclusively to the isolated network namespace `sentrix0` and designated test subnet `10.200.0.0/24`. Host networking is unaffected.
- **Signed Authorization:** Enforcement requires a formally signed manifest at `enforcement/approval.json`. If missing, expired, or unapproved, enforcement fails closed.
- **Comment-Based Tagging:** Rules applied in `nftables` are explicitly tagged (`sentrix:<action_id>`), ensuring external or operator firewall rules are never modified or removed.
- **Expiry & Cleanup Verification (TC-09):** Rules are tracked with TTL. Upon expiration, SENTRIX verifies nftables removal and records state transition to `expired`.
- **Failure Lockdown & Recovery (TC-10):** If rule removal fails, the system transitions to `failed`, trips the emergency disable switch, preserves diagnostic audit logs, and blocks new enforcement until procedural recovery (`recover_failed_action`) is completed.
- **Service Restart Reconciliation (TC-12):** On backend startup, `reconcile_lab_enforcement()` reconciles persisted SQLite actions against real nftables state. Orphaned rules are pruned; missing active rules trip fail-closed emergency lockdown.
- **Gate Status:** **PASSED & APPROVED (Restricted to Lab Only)**.

---

### Gate 4: Release Hardening & Security Gate (PRD 10.3.4, Section 11)
- **Automated Hardening Suite (`test_phase7_security_and_hardening.py`):**
  1. Default configuration enforces `MITIGATION_MODE=simulation` and masks `SecretStr` credentials in logging and string casts.
  2. Standard error envelopes (`{"error": {"code", "message", "request_id"}}`) sanitize internal exceptions, preventing stack trace or file path leakage.
  3. Sensitive IP allowlists (`127.0.0.1`, `::1`, default gateways, DNS) strictly reject poisoning or malicious bypass attempts.
  4. Extreme/negative boundary attacks (negative PPS, overflow durations) are rejected with HTTP 400.
  5. Audit records in `audit_events` are append-only; state transitions strictly follow valid directed acyclic graph (DAG) lifecycle rules.
  6. OS subprocess networking calls remain strictly zero in simulation mode.
- **Code Quality & CI:**
  - 100% clean formatting and linting (`python -m ruff check`, `python -m ruff format --check`).
  - Strict Python 3.10+ compatibility across local and GitHub Actions CI environments (`datetime.timezone.utc`).
  - Full suite of 76 automated backend tests passing with 0 failures and 0 warnings.
- **Gate Status:** **PASSED & APPROVED**.

---

## 3. Accepted Deviations & Known Limitations

| Item | Description | Operational Impact | Mitigation / Status |
| :--- | :--- | :--- | :--- |
| **Offline Baseline Dataset** | ML model was trained on CIC-DDoS2019 captured pcaps. | Public datasets may have different distribution from real-world corporate networks. | Dual-signal hybrid policy prevents ML false positives from executing mitigations without physical traffic rate spikes. |
| **Platform-Adaptive Collector** | Linux `/proc/net/dev` is not available on Windows development hosts. | `collector/lab_collector.py` could crash if run on Windows without fallback. | Added automated fallback probe mode emitting Schema 1.0.0 telemetry for safe, multi-platform verification. |
| **Prototype Persistence** | SQLite is utilized for control plane storage. | SQLite does not support high concurrency write scaling in clustered environments. | Sufficient for prototype control plane and single-instance lab deployment; documented recommendation for PostgreSQL in production scaling. |
| **Isolation Forest Exclusion** | Isolation Forest was excluded from runtime mitigation triggering. | Unsupervised anomaly detection is disabled by default. | Isolation Forest benchmarked and rejected due to 53.31% false positive rate; retained purely for historical comparison. |

---

## 4. Deployment Recommendations

1. **Deploy in Simulation by Default:** Keep `MITIGATION_MODE=simulation` in `.env` for all standard evaluations and demonstrations.
2. **Rotate Placeholder Tokens:** Never deploy with `API_AUTH_TOKEN=dev-only-change-me`. Generate a cryptographically secure 256-bit token (`openssl rand -hex 32`).
3. **Lab Enforcement Isolation:** Only enable `MITIGATION_MODE=linux_lab` inside dedicated Linux VMs/containers with network namespace isolation (`sentrix0`). Verify `enforcement/approval.json` expiration dates before live testing.
4. **Periodic Reconciliation:** Schedule `reconcile_lab_enforcement()` periodically via cron or automation when running long-term lab exercises.

---

## 5. Formal Sign-Off Matrix

The undersigned stakeholders have reviewed the test execution logs, architecture designs, security hardening verifications, and documentation deliverables. All release criteria for **SENTRIX v0.1.0-rc1** are formally accepted.

| Role | Name / Title | Status | Date |
| :--- | :--- | :---: | :---: |
| **Lead System Architect** | SENTRIX Core Architecture Team | **APPROVED** | 2026-10-26 |
| **Machine Learning Engineer** | SENTRIX ML & Detection Team | **APPROVED** | 2026-10-26 |
| **Security & Safety Gate Officer** | Defensive Operations & Safety Lead | **APPROVED** | 2026-10-26 |
| **Quality & Release Engineer** | Test Automation & Verification Lead | **APPROVED** | 2026-10-26 |

