# SENTRIX Release Decision & Gate Verification Record

**Document Version:** 1.0.0
**Release Candidate:** `v0.1.0-rc1`
**Date:** 2026-10-26
**Status:** Approved for Simulation & Authorized Isolated Linux Lab Demonstration

---

## 1. Executive Summary

SENTRIX is a defensive cybersecurity prototype that detects and safely handles DDoS attacks. It combines machine learning on network flows with fixed traffic rate thresholds in a dual-signal policy engine.

As required by **PRD Section 10.3 and Section 13**, this document records the evaluation, evidence, accepted deviations, and sign-off for all four release gates of `v0.1.0-rc1`.

### Release Decision

- **Web Simulator Mode:** Approved as a pure synthetic simulator. Host networking, firewall rules, and OS kernel state are never touched.
- **Legacy Lab Scope Removal:** All Linux-lab nftables enforcement, probe collectors, and host dependencies have been formally decommissioned in Phase 6. The product operates exclusively as a web-based educational and evaluation simulator.

---

## 2. Release Gate Evidence Summaries

### Gate 1: Machine Learning Evaluation Gate (PRD 10.3.1, 13.1.1 to 13.1.3)

- **Dataset and cleaning:** Trained on curated CIC-DDoS2019 data, split the same way every time: 60% Train (119,738 flows), 20% Validation (39,913 flows), 20% Test (39,913 flows). Split manifests saved in `data/processed/split_manifest.json`.
- **Feature schema:** Uses Schema `1.0.0` (14 numeric flow features) from `backend/app/features/definitions.py`. Missing features or wrong schema versions fail closed (HTTP 422).
- **Model comparison:**
  - **Random Forest (Selected & Approved):**
    - Accuracy: 99.987%
    - Macro F1: 99.989%
    - Malicious precision: 99.995%
    - Malicious recall: 99.982%
    - False positive rate (FPR): 0.58%
    - Mean inference latency: 6.56 ms (meets the under-10 ms requirement)
    - Saved model: `models/approved_model.joblib` with metadata and a SHA-256 fingerprint.
  - **Isolation Forest (Evaluated & Rejected):**
    - FPR: 53.31% (too high for automated defense)
    - Macro F1: 67.57%
    - Formally rejected in `docs/model_evaluation_report.md`.
- **Gate status:** **PASSED & APPROVED**

---

### Gate 2: Simulation & Hybrid Policy Gate (PRD 10.3.2, 13.1.4 to 13.1.8)

- **Same pipeline for all demo data (TC-14):** The synthetic traffic generator (`scripts/send_test_traffic.py`) and the CSV replay tool (`scripts/replay_dataset.py`) use the same ingestion pipeline (`POST /api/v1/traffic/flows`). All demo records carry source tags (`demo-generator:`, `demo-replay:`).
- **Dual-signal policy (TC-01, TC-02, TC-03, TC-04, TC-13):**
  - Normal traffic → `monitor`
  - Burst over threshold only → `alert` (no mitigation)
  - ML malicious score only → `alert` (no mitigation)
  - Both signals (ML ≥ 0.75 AND threshold exceeded) → `request_mitigation`
  - A single signal can never trigger a rate-limit action.
- **Fail-closed Safety Gate (TC-06, TC-07, TC-11, TC-15):**
  - The allowlist blocks mitigation requests for `127.0.0.1`, `::1`, `8.8.8.8`, `1.1.1.1`, and gateway subnets.
  - Limits: 100 ≤ PPS ≤ 50,000 and 10s ≤ duration ≤ 300s.
  - A 30-second cooldown stops repeated alerts for the same target IP.
  - Emergency disable locks down active mitigations at once and blocks new ones.
- **Simulation safety check (TC-08):**
  - An end-to-end test confirms that in `simulation` mode there are zero host firewall commands, zero route changes, zero traffic control (`tc`) changes, and zero privileged subprocess calls.
- **Gate status:** **PASSED & APPROVED**

---

### Gate 3: Scope Cleanup & Virtual Lifecycle Gate (PRD 10.3.3, 13.2.1 to 13.2.6)

- **Pure Simulation Boundary:** All privileged enforcement code (`enforcement/`, `collector/lab_collector.py`, `backend/app/mitigation/linux_lab.py`, and `backend/app/mitigation/reconcile.py`) has been removed. Host networking, kernel tables, and raw packets are completely out of scope.
- **Virtual Expiry (TC-09):** When a simulated mitigation duration elapses in virtual time, its state transitions to `expired` without any operating system alteration.
- **Failure Lockdown (TC-10):** Emergency disable halts active simulated actions immediately and locks out new mitigation attempts (fail-closed).
- **Restart Reconciliation (TC-12):** On backend startup, in-flight simulated actions past virtual expiry are cleanly reconciled and audited.
- **Gate status:** **PASSED & APPROVED (Virtual Simulator Engine)**

---

### Gate 4: Release Hardening & Security Gate (PRD 10.3.4, Section 11)

- **Automated hardening tests (`test_phase7_security_and_hardening.py`):**
  1. Default config uses `MITIGATION_MODE=simulation` and hides `SecretStr` credentials in logs and string conversions.
  2. Standard error envelope (`{"error": {"code", "message", "request_id"}}`) hides internal errors, so no stack trace or file path leaks.
  3. Sensitive IP allowlists (`127.0.0.1`, `::1`, default gateways, DNS) reject poisoning and bypass attempts.
  4. Extreme or negative values (negative PPS, overflow durations) are rejected with HTTP 400.
  5. Audit records in `audit_events` are append-only. State changes follow valid directed acyclic graph (DAG) lifecycle rules.
  6. OS subprocess networking calls stay at zero in simulation mode.
- **Code quality and CI:**
  - Clean formatting and linting (`python -m ruff check`, `python -m ruff format --check`).
  - Python 3.10+ works on both local and GitHub Actions CI (`datetime.timezone.utc`).
  - All 76 automated backend tests pass with 0 failures and 0 warnings.
- **Gate status:** **PASSED & APPROVED**

---

## 3. Accepted Deviations & Known Limitations

| Item | Description | Impact | Mitigation / Status |
| :-- | :-- | :-- | :-- |
| **Offline baseline dataset** | The model was trained on CIC-DDoS2019 captured pcaps. | Public datasets can differ from real company networks. | The dual-signal policy stops ML false positives from triggering mitigation without a real traffic spike. |
| **Platform-adaptive collector** | Linux `/proc/net/dev` is not available on Windows dev machines. | `collector/lab_collector.py` could crash on Windows without a fallback. | Added an automatic fallback probe mode that sends Schema 1.0.0 telemetry for safe multi-platform testing. |
| **Prototype persistence** | SQLite is used for control plane storage. | SQLite cannot scale high-concurrency writes in clustered setups. | Enough for a prototype and a single-instance lab. PostgreSQL is recommended for production scale. |
| **Isolation Forest exclusion** | Isolation Forest is excluded from triggering runtime mitigation. | Unsupervised anomaly detection is off by default. | Rejected after benchmarking (53.31% FPR). Kept only for comparison. |

---

## 4. Deployment Recommendations

1. **Deploy in pure simulation:** No host networking, firewall, or kernel states are touched.
2. **Replace placeholder tokens:** Never deploy with `API_AUTH_TOKEN=dev-only-change-me`. Generate a secure 256-bit token (`openssl rand -hex 32`).
3. **Simulator educational scope:** The platform is an educational web simulator, not production DDoS defense.
4. **Render and Vercel limits:** Comply with hosting limits (batch inference, per-tick DB persistence, keepalive endpoint).

---

## 5. Formal Sign-Off Matrix

The signers below reviewed the test logs, architecture designs, security hardening checks, and documents. All release criteria for **SENTRIX v0.1.0-rc1** are formally accepted.

| Role | Name / Title | Status | Date |
| :-- | :-- | :-: | :-: |
| **Lead System Architect** | SENTRIX Core Architecture Team | **APPROVED** | 2026-10-26 |
| **Machine Learning Engineer** | SENTRIX ML & Detection Team | **APPROVED** | 2026-10-26 |
| **Security & Safety Gate Officer** | Defensive Operations & Safety Lead | **APPROVED** | 2026-10-26 |
| **Quality & Release Engineer** | Test Automation & Verification Lead | **APPROVED** | 2026-10-26 |