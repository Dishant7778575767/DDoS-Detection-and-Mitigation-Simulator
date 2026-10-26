# SENTRIX Release Checklist & Quality Gate Verification

## 1. Overview

This checklist serves as the formal release and readiness gate for SENTRIX. All items must be verified and checked off prior to tagging a release candidate.

---

## 2. Phase-by-Phase Readiness Gates

### Phase 1 — Foundation & Skeleton Gate
- [x] Python dependencies declared in `backend/pyproject.toml` with pinned minimum versions.
- [x] Configuration loading enforces required variables (`APP_ENV`, `MITIGATION_MODE`, `API_AUTH_REQUIRED`).
- [x] Minimal `GET /api/v1/health` endpoint protected by Bearer token authentication.
- [x] Database migration framework (`alembic`) initializes repeatable schema.
- [x] Hosted CI workflow (`.github/workflows/ci.yml`) is green.

### Phase 2 — Data & ML Baseline Gate
- [x] CIC-DDoS2019 dataset validated, cleaned, and deterministically partitioned (60/20/20 train/val/test).
- [x] Shared feature schema `v1.0.0` defined with exact 14 features in `backend/app/features/definitions.py`.
- [x] Both Random Forest and Isolation Forest candidates trained and evaluated on held-out test split.
- [x] Random Forest approved (F1: 99.989%, Precision: 99.995%, Recall: 99.982%, FPR: 0.58%, Latency: 6.56 ms).
- [x] Isolation Forest rejected due to high benign false-positive rate (53.31% FPR).
- [x] Evaluation evidence documented in `docs/model_evaluation_report.md`.
- [x] Approved artifact exported to `models/approved_model.joblib` with metadata.

### Phase 3 — Backend, Detection & Policy Gate
- [x] SQLAlchemy domain models and repositories implemented for all entities.
- [x] Ingestion pipeline enforces UTC ISO 8601 timestamps, finite numbers, and schema version checking.
- [x] Dual-signal hybrid policy strictly separates ML signals from traffic volume thresholds.
- [x] Fail-closed Safety Gate enforces allowlists, rate bounds (100–50,000 pps), duration bounds (10–300s), and concurrency limits (max 100).
- [x] Mitigation lifecycle state machine enforces valid state transitions (`proposed`, `simulated`, `cancelled`, `expired`).
- [x] All 14 PRD Section 7 REST API endpoints implemented and contract-tested.

### Phase 4 — Dashboard Gate
- [x] Next.js 16+ frontend configured with TypeScript, Tailwind CSS, and Recharts.
- [x] All 5 core views implemented: Overview, Alerts Feed, Mitigation Control Room, History Audit Trail, and Settings.
- [x] Dark cybersecurity theme (`#050B14` + `#00E5FF` electric cyan) applied consistently.
- [x] Live polling hook handles loading, error, stale data, and disconnected server states gracefully.
- [x] Emergency Disable kill-switch and action cancellation controls functional with confirmations.
- [x] Frontend passes `npm run lint` and `npm run typecheck` with 0 errors.

### Phase 5 — Simulation & Integration Gate
- [x] Bounded synthetic traffic generator implemented (`scripts/send_test_traffic.py`).
- [x] Prepared-file CSV replay implemented (`scripts/replay_dataset.py`).
- [x] Both tools route through runtime API ingestion (`POST /api/v1/traffic/flows`) and carry demonstration tags (`demo-generator:`, `demo-replay:`).
- [x] PRD Section 10.2 integration test cases verified:
  - TC-01: Normal traffic -> `monitor`
  - TC-02: Abnormal burst -> `alert` (threshold only)
  - TC-03: Suspected SYN flood -> `request_mitigation` (dual signal)
  - TC-04: Threshold only -> `alert` only (mitigation never initiated)
  - TC-05: Invalid schema / features rejected (422)
  - TC-06: Protected infrastructure targets rejected by safety gate (400)
  - TC-07: Repeated alerts cooldown deduplication verified
  - TC-11: Unauthorized operator requests rejected (401)
  - TC-13: 4-Quadrant hybrid decision matrix verified
  - TC-14: Generator and file replay parity verified
  - TC-15: Cancellation and Emergency Disable verified
  - TC-16: Lifecycle invalid transition rejection and audit verified
- [x] TC-08 Simulation Safety Proof: verified zero OS networking or firewall modifications occur.
- [x] Reliability & Performance benchmarks recorded in `data/fixtures/benchmark_evidence.json`:
  - Inference latency mean: `8.17 ms` (Target: `< 10.0 ms`)
  - Peak memory growth: `0.67 MB` (Target: `< 512.0 MB`)
- [x] Entire backend test suite passes: **56 / 56 tests passing**.

### Phase 6 — Isolated Linux Lab Gate
- [x] Lab network architecture and isolation boundary documented in `enforcement/README.md` (`sentrix0`, `10.200.0.0/24`).
- [x] Formal signed approval manifest implemented in `enforcement/approval.json`.
- [x] Privileged enforcement agent implemented in `enforcement/agent.py` using parameterized `nftables` commands.
- [x] Comment-based tagging (`sentrix:<action_id>`) ensures zero touch on non-SENTRIX firewall rules.
- [x] TTL expiration manager implemented in `enforcement/expiry.py`.
- [x] Lab adapter implemented in `backend/app/mitigation/linux_lab.py`.
- [x] Service restart reconciliation engine implemented in `backend/app/mitigation/reconcile.py`.
- [x] Troubleshooting & recovery runbook documented in `enforcement/recovery.md`.
- [x] Automated integration test suite `backend/tests/test_cases/test_tc09_tc10_tc12_linux_lab.py` verified:
  - TC-09: Rule expiration & verified removal.
  - TC-10: Cleanup failure, fail-closed emergency lockdown & procedural recovery.
  - TC-12: Service restart reconciliation, orphaned rule pruning & missing rule lockdown.
  - Subnet boundaries (`10.200.0.0/24`) and parameter bounds enforcement.

---

## 3. Security & Safety Checklist

- [ ] **Default Safe Mode**: `MITIGATION_MODE` is strictly set to `simulation`.
- [ ] **No Public Enforcement**: Linux `nftables`/`tc` enforcement remains disabled outside approved lab.
- [ ] **Credential Protection**: `.env` is git-ignored; no production secrets or hardcoded passwords exist in repo.
- [ ] **Error Envelope Sanitization**: API errors return structured envelope `{ "error": { "code", "message", "request_id" } }` without stack trace leakage.
- [ ] **Immutable Audit Logging**: All sensitive actions and lifecycle transitions create unmodifiable records in `audit_events`.
- [ ] **Allowlist Integrity**: `127.0.0.1`, `::1`, default gateways, and public DNS resolvers cannot be targeted for rate-limiting.

---

## 4. Code Quality & Formatting Gate

Verify all checks pass before tagging:

```powershell
# 1. Backend Lint & Format
python -m ruff check
python -m ruff format --check

# 2. Automated Test Suite
python -m pytest backend/tests -v

# 3. Frontend Quality Checks
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

---

## 5. Documentation Verification

- [x] `README.md`: System overview, quick start, architecture, test instructions, and status.
- [x] `PRD.md`: Traceability to requirements and Section 10.2 test specifications.
- [x] `IMPLEMENTATION_PLAN.md`: Phase status and exit gate criteria.
- [x] `docs/api_schemas.md`: Full specification of all 14 endpoint contracts.
- [x] `docs/model_evaluation_report.md`: Complete dataset, split, model comparison, and selection evidence.
- [x] `docs/operations.md`: Day-to-day operating procedures, tool usage, and policy rules.
- [x] `docs/recovery.md`: Emergency disable recovery, restart reconciliation, and runbooks.
- [x] `docs/release_checklist.md`: Quality gates and readiness checklist.
- [x] `enforcement/README.md`: Isolated lab architecture, namespace, and threat model.
- [x] `enforcement/recovery.md`: TC-10 cleanup failure and TC-12 restart recovery runbooks.

---

## 6. Formal Sign-Off

| Role | Name | Status | Date |
| :--- | :--- | :---: | :--- |
| **System Lead** | SENTRIX Core Team | Approved | 2026-10-26 |
| **ML Lead** | Machine Learning Team | Approved | 2026-10-25 |
| **Security & Safety** | Safety Gate Reviewer | Approved (Lab & Simulation) | 2026-10-26 |
