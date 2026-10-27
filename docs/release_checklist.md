# SENTRIX Release Checklist & Quality Gate Verification

## 1. Overview

This checklist is the final gate before a SENTRIX release. Every item must be checked before tagging a release candidate.

---

## 2. Phase-by-Phase Readiness Gates

### Phase 1: Foundation & Skeleton Gate

- [x] Python dependencies listed in `backend/pyproject.toml` with pinned minimum versions.
- [x] Config loading requires `APP_ENV`, `MITIGATION_MODE`, and `API_AUTH_REQUIRED`.
- [x] Basic `GET /api/v1/health` endpoint protected by Bearer token.
- [x] Database migrations (`alembic`) create the schema the same way every time.
- [x] CI workflow (`.github/workflows/ci.yml`) is green.

### Phase 2: Data & ML Baseline Gate

- [x] CIC-DDoS2019 dataset checked, cleaned, and split the same way every time (60/20/20 train/val/test).
- [x] Shared feature schema `v1.0.0` defined with exactly 14 features in `backend/app/features/definitions.py`.
- [x] Random Forest and Isolation Forest both trained and tested on the held-out test split.
- [x] Random Forest approved (F1: 99.989%, Precision: 99.995%, Recall: 99.982%, FPR: 0.58%, Latency: 6.56 ms).
- [x] Isolation Forest rejected because of high false positives on benign traffic (53.31% FPR).
- [x] Evaluation evidence written in `docs/model_evaluation_report.md`.
- [x] Approved model exported to `models/approved_model.joblib` with metadata.

### Phase 3: Backend, Detection & Policy Gate

- [x] SQLAlchemy models and repositories built for all entities.
- [x] Ingestion pipeline checks UTC ISO 8601 timestamps, finite numbers, and schema version.
- [x] Dual-signal policy keeps ML signals and traffic thresholds separate.
- [x] Fail-closed Safety Gate enforces allowlists, rate bounds (100 to 50,000 pps), duration bounds (10 to 300s), and concurrency limit (max 100).
- [x] Mitigation state machine allows only valid transitions (`proposed`, `simulated`, `cancelled`, `expired`).
- [x] All 14 PRD Section 7 REST API endpoints built and contract-tested.

### Phase 4: Dashboard Gate

- [x] Next.js 16+ frontend set up with TypeScript, Tailwind CSS, and Recharts.
- [x] All 5 core views built: Overview, Alerts Feed, Mitigation Control Room, History Audit Trail, and Settings.
- [x] Dark cybersecurity theme (`#050B14` with `#00E5FF` electric cyan) used everywhere.
- [x] Live polling handles loading, error, stale data, and server-down states.
- [x] Emergency Disable switch and cancel controls work, with confirmation prompts.
- [x] Frontend passes `npm run lint` and `npm run typecheck` with 0 errors.

### Phase 5: Simulation & Integration Gate

- [x] Bounded synthetic traffic generator built (`scripts/send_test_traffic.py`).
- [x] CSV replay tool built (`scripts/replay_dataset.py`).
- [x] Both tools send data through the runtime API (`POST /api/v1/traffic/flows`) and carry demo tags (`demo-generator:`, `demo-replay:`).
- [x] PRD Section 10.2 integration test cases verified:
  - TC-01: Normal traffic → `monitor`
  - TC-02: Abnormal burst → `alert` (threshold only)
  - TC-03: Suspected SYN flood → `request_mitigation` (dual signal)
  - TC-04: Threshold only → `alert` only (mitigation never starts)
  - TC-05: Invalid schema or features rejected (422)
  - TC-06: Protected infrastructure targets rejected by Safety Gate (400)
  - TC-07: Repeated alert cooldown and deduplication verified
  - TC-11: Unauthorized requests rejected (401)
  - TC-13: 4-quadrant decision matrix verified
  - TC-14: Generator and file replay give the same results
  - TC-15: Cancellation and Emergency Disable verified
  - TC-16: Invalid lifecycle transitions rejected and audited
- [x] TC-08 Simulation Safety Proof: zero OS networking or firewall changes happen.
- [x] Reliability and performance benchmarks saved in `data/fixtures/benchmark_evidence.json`:
  - Inference latency mean: `8.17 ms` (Target: `< 10.0 ms`)
  - Peak memory growth: `0.67 MB` (Target: `< 512.0 MB`)
- [x] Full backend test suite passes: **56 / 56 tests**.

### Phase 6: Scope Cleanup & Legacy Lab Removal Gate

- [x] Legacy Linux-lab enforcement implementation (`enforcement/`, `collector/lab_collector.py`, `backend/app/mitigation/linux_lab.py`, `backend/app/mitigation/reconcile.py`) removed.
- [x] Signed lab approval manifests, subnet dependencies (`sentrix0`, `10.200.0.0/24`), and host firewall execution paths removed.
- [x] Automated virtual lifecycle test suite in `backend/tests/test_cases/test_tc09_tc10_tc12_virtual_lifecycle.py` verified:
  - TC-09: Virtual mitigation expiry and confirmed status transition without OS alterations.
  - TC-10: Emergency lockdown, fail-closed safety gate rejection, and failure auditing.
  - TC-12: Simulator restart reconciliation and virtual expiration of in-flight actions.
- [x] `MITIGATION_MODE` removed from backend settings; simulation engine is the exclusive, pure simulation path.

### Phase 7: Release Hardening Gate

- [x] Automated security test suite built in `backend/tests/test_cases/test_phase7_security_and_hardening.py`.
- [x] Default config checked: `MITIGATION_MODE=simulation`, `API_AUTH_REQUIRED=true`, `SecretStr` masking.
- [x] Error envelope checked: `{ "error": { "code", "message", "request_id" } }` with no stack trace or file path leaks.
- [x] Sensitive IP allowlists tested against bypass attacks (`127.0.0.1`, `::1`, default gateways, public DNS).
- [x] Extreme parameter attacks fail closed (negative or too-large pps, duration overflow).
- [x] Audit log immutability and lifecycle state transition rules verified.
- [x] Subprocess isolation verified: no OS networking commands run in simulation mode.
- [x] Full test suite passing: **76 / 76 backend tests** with 0 failures and 0 warnings.
- [x] Formal release decision and gate evidence published in `docs/release_decision.md`.

---

## 3. Security & Safety Checklist

- [x] **Safe by default:** Engine operates strictly in pure simulation.
- [x] **No network mutation:** No host networking, firewall, or socket calls exist in the runtime path.
- [x] **Credential protection:** `.env` is git-ignored. No production secrets or hardcoded passwords in the repo.
- [x] **Error envelope sanitization:** API errors use `{ "error": { "code", "message", "request_id" } }` with no stack trace leaks.
- [x] **Immutable audit logging:** All sensitive actions and lifecycle changes create unchangeable records in `audit_events`.
- [x] **Allowlist integrity:** `127.0.0.1`, `::1`, default gateways, and public DNS servers cannot be rate-limited.

---

## 4. Code Quality & Formatting Gate

Check that all of these pass before tagging:

```powershell
# 1. Backend lint and format
python -m ruff check
python -m ruff format --check

# 2. Automated test suite
python -m pytest backend/tests -v

# 3. Frontend quality checks
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

---

## 5. Documentation Verification

- [x] `README.md`: Overview, quick start, architecture, test steps, and status.
- [x] `PRD.md`: Links to requirements and Section 10.2 test specs.
- [x] `IMPLEMENTATION_PLAN.md`: Phase status and exit gate criteria.
- [x] `docs/api_schemas.md`: Full specification of all 14 endpoint contracts.
- [x] `docs/model_evaluation_report.md`: Dataset, split, model comparison, and selection evidence.
- [x] `docs/operations.md`: Daily operating steps, tool usage, and policy rules.
- [x] `docs/recovery.md`: Emergency disable recovery, restart reconciliation, and runbooks.
- [x] `docs/release_checklist.md`: Quality gates and readiness checklist.
- [x] `docs/release_decision.md`: Formal release decision, gate evidence, accepted deviations, and sign-off table.

---

## 6. Formal Sign-Off

| Role | Name | Status | Date |
| :-- | :-- | :-: | :-- |
| **System Lead** | SENTRIX Core Team | Approved | 2026-10-26 |
| **ML Lead** | Machine Learning Team | Approved | 2026-10-25 |
| **Security & Safety** | Safety Gate Reviewer | Approved (Lab & Simulation) | 2026-10-26 |