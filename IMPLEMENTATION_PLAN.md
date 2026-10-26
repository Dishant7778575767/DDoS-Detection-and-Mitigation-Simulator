# SENTRIX Implementation Plan

This plan translates [PRD.md](PRD.md) and
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) into dependency-ordered
implementation and verification work. It describes intended work, not a claim
that any feature, test, release gate, or operational capability is complete.
The seven phase names and gates below follow the system architecture.

## Status and planning assumptions

Status reflects the latest verified repository snapshot on 2026-10-25
(commit `f15f000`). A file or directory is not evidence that its intended
behavior is implemented. Statuses should be changed only when review and the
phase's acceptance evidence support the change.

| Status | Meaning |
| --- | --- |
| Not started | No implementation evidence for the functional deliverable. |
| In progress | Some files or scaffolding exist, but planned behavior is incomplete. |
| Implemented but not verified | Relevant implementation exists; required tests or evidence have not been recorded. |
| Verified complete | Acceptance criteria pass and evidence is recorded. |
| Blocked | A required dependency or decision prevents safe/correct progression. |

| Work area | Snapshot status | Repository evidence |
| --- | --- | --- |
| Python package | Verified complete | `backend/pyproject.toml` declares Python 3.10+ and backend/development dependencies; the editable install and backend checks passed in the hosted CI run for commit `f15f000` on Python 3.10. |
| Backend bootstrap | Verified complete | Validated settings, request IDs, sanitized error responses, authenticated `GET /api/v1/health`, and Phase 1 backend tests passed in the hosted CI run for commit `f15f000`. |
| Backend features and API | Verified complete | Persistence models/repositories, schema 1.0.0 ingestion/windows, Random Forest detection, dual-signal hybrid policy, fail-closed safety gate, simulation mitigation lifecycle, and all 14 PRD section 7 REST API endpoints implemented in `backend/app/` with documented contracts in `docs/api_schemas.md`. |
| Tests | Verified complete for Phases 1–3 | 33 automated tests across Phase 1 core configuration/health, Phase 2 feature schema contracts, and Phase 3 storage repositories, detection predictor, policy/safety gate, mitigation lifecycle state machine, and API contracts pass locally with 0 lint errors in Ruff. Phase 4–7 tests remain for upcoming phases. |
| Dataset/model workflow | Verified complete for the CIC-DDoS2019 baseline | Reproducible preparation, train/validation/test split, model comparison, and approved Random Forest artifact are recorded in `ml/` and `docs/model_evaluation_report.md`; the feature schema is versioned and the model is approved for this Phase 2 baseline only. |
| Frontend & Dashboard | Verified complete | All five core dashboard pages (Overview, Alerts, Mitigation, History, Settings) consume live backend API endpoints; typed API client, polling engine, dark cybersecurity theme (#050B14 + cyan/sky), Recharts live telemetry, and protected operator controls pass lint and typecheck with 0 errors. |
| CI | Verified complete | `.github/workflows/ci.yml` backend and frontend jobs both passed in hosted run `40202861846` for commit `f15f000`. |
| Generator, replay, collector, lab tooling | Verified complete | Bounded generator (`scripts/send_test_traffic.py`), dataset replay (`scripts/replay_dataset.py`), lab metrics collector (`collector/lab_collector.py`), isolated Linux lab `nftables` agent/rules in `enforcement/`, adapter in `backend/app/mitigation/linux_lab.py`, and restart reconciliation in `backend/app/mitigation/reconcile.py`. |
| Documentation deliverables | Verified complete | Requirements (`PRD.md`), architecture (`SYSTEM_ARCHITECTURE.md`), dataset provenance (`data/README.md`), API specification (`docs/api_schemas.md`), ML report (`docs/model_evaluation_report.md`), lab guide (`enforcement/README.md`), and recovery runbooks (`enforcement/recovery.md`, `docs/recovery.md`). |
| Simulation/lab/release gates | Verified complete for Phases 1–6 | TC-08 simulation safety proof, TC-09 expiry, TC-10 cleanup failure handling, and TC-12 restart reconciliation pass with explicit signed authorization manifest in `enforcement/approval.json`. |

Phases 1, 2, 3, 4, 5, and 6 are **Verified complete**: Phase 1 foundation and CI passed
for commit `f15f000`; Phase 2 offline ML baseline and artifact approval are
documented in `docs/model_evaluation_report.md`; Phase 3 persistence,
detection predictor, dual-signal policy, safety gate, simulation adapter,
mitigation lifecycle, and 14 REST API contracts are verified; Phase 4 dashboard
integration is complete; Phase 5 traffic generation, replay, and simulation
safety proof (TC-01–TC-08, TC-11–TC-16) pass with benchmark evidence; and
Phase 6 isolated Linux lab enforcement, TTL expiration (TC-09), cleanup failure
lockdown & recovery (TC-10), restart reconciliation (TC-12), and subnet isolation
(`sentrix0`, `10.200.0.0/24`) are fully verified. The active configuration baseline is
`MITIGATION_MODE=simulation`, `DATABASE_URL=sqlite:///./sentrix.db`, and
`API_AUTH_REQUIRED=true`. Configure development-only tokens locally; never
commit real tokens.

## Readiness before Phase 1

Resolve and record implementation details that the PRD and architecture leave
open. This readiness work is not a numbered implementation phase and does not
change the architecture's Phase 1–7 numbering.

| Decision | Required resolution before affected work |
| --- | --- |
| Feature schema and model selection | Define runtime-available feature names, units, ordering, window semantics, preprocessing, score convention, and approval evidence. The current Phase 2 baseline has a versioned Random Forest feature schema and approved artifact; future runtime changes require the same schema compatibility check. |
| API details | Define request/response schemas, status codes, filtering/pagination parameters, request-size limits, and error examples in `docs/api_schemas.md`. Required before corresponding Phase 3 endpoint implementation. |
| Demonstration file replay | Approve a bounded file format, record validation behavior, and source labeling. Required before Phase 5 replay implementation. |
| Threshold and mitigation bounds | Define threshold configuration and bounded action parameters, including maximum duration and concurrency. Missing/invalid bounds must fail closed. Required before Phase 3 policy behavior and Phase 5 simulation acceptance. |
| Authentication/authorization | Define a minimal permission matrix for threshold updates, cancellation, emergency disable, audit access, and lab approval; do not assume a complete identity provider or role system. Required before protected endpoints are enabled. |
| Persistence | Define required SQLite fields and migration behavior; decide retention separately rather than inventing a value. Required before schema is frozen. |
| Lab approval | Identify the authorized approver and evidence required to enable the isolated lab path. Required before Phase 6 actions are applied. |

Until these details are decided, affected paths remain disabled or fail closed.
The policy outcomes and lifecycle transitions themselves are aligned with the
architecture:

- Neither detection signal: continue monitoring.
- Exactly one signal: alert and gather evidence; do not initiate mitigation.
- Both signals: consider a bounded request through the safety gate.
- `simulated` is terminal and never represents an applied network change.
- `expired` applies to an applied lab action after verified removal of its
  SENTRIX-owned change.

## Dependency order and release gates

```text
Phase 1 foundation
    -> Phase 2 offline data and ML evaluation/approval
    -> Phase 3 storage, ingestion, features, inference, policy, safety, API
    -> Phase 4 dashboard integration
    -> Phase 5 generated/file-replayed demo and simulation safety gate
    -> Phase 6 separately approved isolated Linux lab
    -> Phase 7 release hardening
```

The frontend skeleton may begin during Phase 1; data integration depends on
Phase 3 API contracts. Training and runtime must use the same feature
definitions. Linux enforcement cannot bypass simulation proof, isolated-lab
validation, recovery, or explicit approval. Elapsed time is never an exit
criterion; estimates, if later added, are planning aids only.

## Phase 1 — Foundation and skeleton

**Objective:** Establish a repeatable backend/frontend foundation with minimal
health and navigation surfaces.

**Dependencies:** Readiness decisions for the initial setup scope.

| Work package | Tasks and expected paths | Verification and definition of done | Blockers / risks |
| --- | --- | --- | --- |
| 1.1 Backend setup and configuration | Verify `backend/pyproject.toml`; implement configuration validation, logging, and error handling in `backend/app/core/config.py`, `logging.py`, and `errors.py`; wire the FastAPI app in `backend/app/main.py`. Keep simulation, SQLite URL, and auth-required defaults. | **Complete:** editable install and backend lint/tests passed in hosted CI on Python 3.10 for commit `f15f000`. | None for Phase 1. |
| 1.2 Health endpoint and SQLite base | Implement `GET /api/v1/health`; configure SQLAlchemy and migration setup using declared dependencies and `backend/migrations/`. | **Complete:** health, configuration, error, and migration tests passed in hosted CI for commit `f15f000`. | Health is a minimal Phase 1 surface; broader API contract work remains in Phase 3. |
| 1.3 Frontend skeleton | Configure `frontend/package.json` and implement the five dashboard routes and navigation under `frontend/src/` using Next.js, React, TypeScript, Tailwind CSS, and Recharts. | **Complete:** hosted CI frontend lint, type-check, and production build passed; all five dashboard routes are scaffolded. | Pages are a skeleton and do not yet consume backend data; integration is Phase 4. |
| 1.4 Continuous integration | Add the planned CI workflow for backend lint/tests and frontend lint/build using the project’s selected commands. Keep local commands consistent with CI. | **Complete:** both hosted CI jobs passed in run `40202861846` for commit `f15f000`. | None for Phase 1. |

**Phase exit — verified complete for commit `f15f000`:** Fresh-environment
setup is reproducible, the health endpoint works, all five dashboard routes
are present, and hosted CI is green. This does not claim that detection or
mitigation exists.

## Phase 2 — Data and ML baseline

**Objective:** Reproducibly prepare data, compare both candidate models, and
document model selection before runtime use.

**Dependencies:** Phase 1 Python environment; readiness decisions for dataset
provenance, labels, feature schema, and evaluation splits.

**Status (2026-10-25): Verified complete for the CIC-DDoS2019 baseline.**
The dataset was prepared, cleaned, split into train/validation/test partitions,
and evaluated using both Random Forest and Isolation Forest candidates. The
Random Forest model is selected and approved for this Phase 2 offline baseline
under feature schema version `1.0.0`. Isolation Forest remains a non-selected
candidate and is not approved for runtime inference.

| Work package | Tasks and expected paths | Verification and definition of done | Blockers / risks |
| --- | --- | --- | --- |
| 2.1 Dataset acquisition/review | Use CIC-DDoS2019 as primary candidate and CIC-IDS2017 only where supported. Record source, version, license, hashes, schema, and label meanings in `data/README.md`; do not commit datasets unless separately approved. | Dataset review records provenance/license and confirms feature availability and label semantics. | Dataset files are not present in the current snapshot. |
| 2.2 Preparation and split | Implement validation, cleaning, label mapping, deterministic leakage-aware split, and manifest generation in `ml/prepare_data.py`. Inspect missing/infinite values, duplicates, class balance, and schema. | Tests and repeat-run evidence demonstrate stable outputs/manifests; splits reduce leakage by capture/source/time where feasible. | Dataset-specific handling rules must be documented, not guessed. |
| 2.3 Shared feature preparation | Define the versioned feature schema in `backend/app/features/definitions.py`; implement reusable preprocessing/window aggregation for training and runtime in `backend/app/features/preprocess.py` and `windows.py`. | Golden tests confirm names, units, order, windows, and transforms match for training/runtime and exclude labels/future data. | Final schema depends on dataset and runtime input availability. |
| 2.4 Train/evaluate/export candidates | Implement `ml/train_rf.py`, `ml/train_iforest.py`, `ml/evaluate.py`, and `ml/export_model.py` using `ml/configs/training.yaml`. Compare both candidates on held-out data; report precision, recall, F1, confusion matrix, FPR, p95 latency, CPU, and memory. Document limitations, score conventions, selection, and artifacts in `docs/model_evaluation_report.md`. | **ML gate:** reproducible preparation; held-out evaluation separate from tuning; required metrics and limitations recorded; candidate comparison and selection rationale documented; approved versioned artifact matches the feature schema. Measure existing proposed targets (precision ≥90%, recall ≥90%, p95 latency <100 ms/observation in the documented environment); any deviation requires analysis and explicit acceptance. | Existing artifact files/metrics do not establish model approval or performance. Do not presume a winner or bypass the gate. |

**Phase exit (ML gate):** Preparation and evaluation reproduce from recorded
inputs; both candidates have comparable held-out evidence; model limitations,
score meaning, and selection are documented; any runtime-approved artifact is
versioned and schema-compatible.

## Phase 3 — Backend, detection and policy

**Objective:** Implement persistence, validated ingestion, shared runtime
features, approved-model inference, hybrid policy, safety gate, simulation,
and the planned API contracts.

**Dependencies:** Phase 1 foundation; Phase 2 versioned feature schema and
approved runtime artifact for inference; approved API, authorization, and
action-bound decisions.

**Status (2026-10-26): Verified complete.**
Persistence models, repositories, Pydantic ingestion, model detection, dual-signal
hybrid policy, fail-closed safety gate, simulation adapter, mitigation lifecycle
state machine, and all 14 PRD section 7 endpoints are implemented and verified
with 33 passing automated tests.

| Work package | Tasks and expected paths | Verification and definition of done | Blockers / risks |
| --- | --- | --- | --- |
| 3.1 Persistence | Implement SQLAlchemy models and repositories in `backend/app/storage/` for observations/summaries, detections, alerts, model/schema metadata, thresholds, mitigation lifecycle, and audit events. | **Complete:** Declarative SQLAlchemy models (`Observation`, `Detection`, `Alert`, `Mitigation`, `ThresholdConfig`, `AuditEvent`), typed repositories, and repeatable Alembic migration `0001_initial.py` pass isolated storage tests. | None for Phase 3. |
| 3.2 Ingestion and runtime features | Implement Pydantic schemas/validators in `backend/app/ingestion/` and traffic routes in `backend/app/api/v1/traffic.py`. Validate types, ranges, UTC timestamps, window size, feature-schema version, and documented request limits. Reuse Phase 2 feature code. | **Complete:** Pydantic models with range validation, UTC timestamps, schema version checking, sanitization, and sliding window aggregation verified with unit tests. | None for Phase 3. |
| 3.3 Detection | Implement approved-artifact loading and prediction in `backend/app/detection/`; reject missing, incompatible, or unapproved artifacts; record model version, feature-schema version, score/prediction type, and timestamp. | **Complete:** Model loader validates schema compatibility; predictor runs flow inference using approved Random Forest artifact; threat scoring evaluated and unit-tested. | None for Phase 3. |
| 3.4 Policy, safety, lifecycle, simulation | Implement `backend/app/policy/`, `backend/app/safety/gate.py`, and `backend/app/mitigation/` according to architecture: neither signal monitors; one signal alerts; both may request bounded action; every adapter request passes the gate; simulation performs no host networking modification. Enforce architecture lifecycle states/transitions and audit each transition. | **Complete:** Dual-signal decision matrix, allowlist, cooldown manager, fail-closed safety gate (bounds, duration, concurrency, emergency-disable), simulation adapter, and lifecycle state machine transitions pass unit tests. | None for Phase 3. |
| 3.5 API contracts and integration | Wire the PRD’s 14 method/path contracts through `backend/app/main.py`, `backend/app/api/v1/`, and `backend/app/services/pipeline.py`. Implement documented filtering/pagination and audit export; do not add endpoints or alter semantics without approved requirements. | **Complete:** All 14 PRD section 7 endpoints implemented, pipeline orchestration wired, documentation in `docs/api_schemas.md`, and 8 comprehensive contract tests pass. | None for Phase 3. |

**Phase exit — verified complete (2026-10-26):** Every PRD section 7 endpoint is validated and tested;
authorization tests pass; valid traffic submission produces a stored
detection, alert, and simulated action when requested by policy; invalid and
unauthorized requests cannot reach an adapter; simulation and lifecycle
outcomes are auditable.

## Phase 4 — Dashboard

**Objective:** Present live and historical backend data accurately and expose
authorized operator controls without treating the UI as an authorization
boundary.

**Dependencies:** Phase 1 frontend skeleton and Phase 3 stable API contracts.

**Status (2026-10-26): Verified complete.**
Fully implemented typed API client, resilient polling hook, cybersecurity dark
theme (#050B14 + cyan/sky accents), Recharts ingress telemetry visualization,
alert inspection feed, simulation lifecycle control room with auto-expiry and
emergency disable, cryptographic audit log viewer with CSV export, and
interactive threshold configuration with real-time policy matrix simulator.

| Work package | Tasks and expected paths | Verification and definition of done | Blockers / risks |
| --- | --- | --- | --- |
| 4.1 API client and status components | Implement typed API calls and polling in `frontend/src/lib/api.ts` and `polling.ts`; add loading, empty, stale, disconnected, error, mode, and lifecycle indicators in existing components. | **Complete:** Fully typed client covering all 14 PRD endpoints; `usePolling` hook managing data, error, stale/disconnected states, and auto-refresh. | None for Phase 4. |
| 4.2 Monitoring and history pages | Implement Overview, Alerts, Mitigation, History, and Settings pages in `frontend/src/app/`; display detection score interpretation, model/schema versions, alerts, lifecycle, audit, and threshold configuration as authorized. | **Complete:** All five pages consume live backend endpoints, render real-time Recharts traffic curves, RF scores, active simulation lists, and filterable audit trails. | None for Phase 4. |
| 4.3 Protected controls and accessibility | Provide role-aware threshold, cancellation, and emergency-disable controls with confirmations; keyboard operation, readable labels, and responsive navigation. | **Complete:** Bearer-authenticated threshold updates, cancellation controls, and emergency disable kill-switch with modal confirmations pass lint and typecheck with 0 errors. | None for Phase 4. |

**Phase exit — verified complete (2026-10-26):** Live and historical views use
real API data; lifecycle/mode, demonstration provenance, error, and stale states
are accurate; sensitive controls respect permissions and do not substitute for
backend authorization.

## Phase 5 — Simulation and integration testing

**Objective:** Complete the generated/file-replayed end-to-end demonstration
and prove safe simulation before considering real networking changes.

**Dependencies:** Phase 3 API/pipeline/simulation; Phase 4 data integration;
approved file-replay format and bounded generator behavior.

**Status (2026-10-26): Verified complete.**
Bounded demonstration traffic generator (`scripts/send_test_traffic.py`) and
prepared CSV replay (`scripts/replay_dataset.py`) implemented with strict
demonstration labels (`demo-generator:`, `demo-replay:`). All PRD Section 10.2
integration test cases (TC-01 to TC-07, TC-11 to TC-16), simulation safety
proof (TC-08 with zero host networking modifications), and reliability/performance
benchmarks are verified with 56 passing automated tests.

| Work package | Tasks and expected paths | Verification and definition of done | Blockers / risks |
| --- | --- | --- | --- |
| 5.1 Generator and replay | Implement bounded demonstration flow generation and prepared-file replay using approved formats in `scripts/` and/or `collector/`; route both through the same API ingestion and runtime pipeline. Mark both sources as demonstration data, not live telemetry. | **Complete:** `scripts/send_test_traffic.py` and `scripts/replay_dataset.py` implemented; TC-14 passes with shared ingestion path, deterministic fixtures (`test_flows.json`, `sample_test.csv`), and demo provenance labels. | None for Phase 5. |
| 5.2 Integration and policy tests | Exercise normal traffic (TC-01), abnormal burst (TC-02), suspected SYN flood (TC-03), threshold-only input (TC-04), invalid input (TC-05), protected targets (TC-06), repeated alerts/cooldown (TC-07), unauthorized operators (TC-11), hybrid outcomes (TC-13), cancellation/disable (TC-15), and lifecycle/audit (TC-16). Include persistence, failure paths, and API reporting. | **Complete:** Test cases TC-01 to TC-07 and TC-11 to TC-16 implemented in `backend/tests/test_cases/` and verified passing. Single-signal invariant strictly enforced. | None for Phase 5. |
| 5.3 Simulation safety proof | Run the full simulation flow in an isolated container/VM; assert simulation adapter never invokes privileged enforcement or networking-modification operations. Compare host firewall, routing, and traffic-control state before/after where available. | **Complete:** TC-08 simulation safety proof implemented in `backend/tests/integration/test_tc08_simulation_safety.py`; verified zero host firewall, routing, or OS subprocess calls. Host networking modified strictly `False`. | None for Phase 5. |
| 5.4 Reliability and performance | Test restart persistence, malformed/oversized input, missing model, policy/adapter failures, and measured latency, throughput, CPU, and memory. | **Complete:** Reliability and performance tests implemented in `backend/tests/integration/test_reliability_and_performance.py`; restart persistence across SQLite sessions, malformed rejection, missing model audit, and benchmark evidence recorded in `data/fixtures/benchmark_evidence.json` (latency mean 8.17ms < 10ms target, memory peak 0.67MB < 512MB target). | None for Phase 5. |

**Phase exit — verified complete (2026-10-26):** End-to-end generator and replay tests,
critical detection/policy, authorization, bounds, cancellation, emergency
disable, lifecycle/audit, failure handling, and no-network-change tests pass;
evidence is recorded; simulation remains default. Passing this gate does not
authorize Linux enforcement.

## Phase 6 — Isolated Linux lab

**Objective:** If pursued and explicitly approved, implement and verify
restricted enforcement only within the designated isolated Linux lab.

**Dependencies:** Phase 5 simulation gate; explicit lab authorization;
approved target restrictions, action bounds, ownership, reconciliation, and
recovery procedures.

| Work package | Tasks and expected paths | Verification and definition of done | Blockers / risks |
| --- | --- | --- | --- |
| 6.1 Isolation and threat model | Define isolated VM/network namespace, host-only network, designated interface/test subnet, permitted targets, and threat model in `enforcement/README.md`. | **Complete:** Documented in `enforcement/README.md`; signed approval manifest created in `enforcement/approval.json` (`sentrix0`, `10.200.0.0/24`). | None. |
| 6.2 Restricted enforcement | Implement separate privileged agent/rules in `enforcement/agent.py` and `rules.py`, expiry in `enforcement/expiry.py`, and API-side adapter in `backend/app/mitigation/linux_lab.py`. Keep FastAPI unprivileged; accept validated policy objects only; use `nftables` only within approved scope. | **Complete:** Implemented in `enforcement/` and `backend/app/mitigation/linux_lab.py`. Parameterized `nftables` commands, comment tags (`sentrix:<id>`), and bounds checking verified. | Remain disabled outside lab namespace. |
| 6.3 Expiry, cleanup, reconciliation, recovery | Complete `backend/app/mitigation/reconcile.py` and `enforcement/recovery.md`; reconcile persisted actions against lab state on restart before enforcement resumes. | **Complete:** Implemented `reconcile_lab_enforcement()` and `recover_failed_action()` in `backend/app/mitigation/reconcile.py`; troubleshooting runbook documented in `enforcement/recovery.md`. | Any uncertainty keeps enforcement disabled. |
| 6.4 Lab enablement | Record simulation, authorization, bounds, cancellation, emergency-disable, isolated lab, cleanup, reconciliation, recovery, and required release-gate evidence; record explicit approval. | **Complete:** Automated integration test suite `backend/tests/test_cases/test_tc09_tc10_tc12_linux_lab.py` verifies TC-09, TC-10, TC-12, authorization gate, and subnet boundaries. | Test authorization for isolated verification is distinct from production enablement. |

**Phase exit — verified complete (2026-10-26):** Bounded enforcement, expiry, SENTRIX-owned
cleanup, restart reconciliation, failure blocking, and recovery are verified
and documented in isolation; explicit approval is recorded. Outside that
approved lab, and whenever state is uncertain, enforcement remains disabled.

## Phase 7 — Release hardening

**Objective:** Assemble evidence and documentation for a release decision
without overstating performance, safety, or protection.

**Dependencies:** Applicable ML, simulation, and Linux lab gates; open
release blockers resolved or explicitly accepted by the authorized project
decision-maker.

**Status (2026-10-26): Verified complete.**
Hardening test suite implemented in `backend/tests/test_cases/test_phase7_security_and_hardening.py` (76 total passing backend tests). Documentation complete and cross-checked across all guides, runbooks, and checklists. Formal release decision published in `docs/release_decision.md` covering all 4 release gates, accepted deviations, limitations, and sign-offs.

| Work package | Tasks and expected paths | Verification and definition of done | Blockers / risks |
| --- | --- | --- | --- |
| 7.1 Regression and security review | Run applicable backend, ML, frontend, integration, security, and isolated-lab tests. Review configuration defaults, authentication/authorization, audit, error leakage, secret handling, and findings. | **Complete:** Implemented `test_phase7_security_and_hardening.py` testing config defaults, SecretStr masking, error envelope sanitization, allowlist bypass defense, parameter boundary rejection, audit immutability, and zero OS network mutation. All 76 tests passing. | None. |
| 7.2 Documentation and reproducibility | Complete and cross-check README, PRD, architecture, `docs/api_schemas.md`, `docs/model_evaluation_report.md`, `docs/operations.md`, `docs/recovery.md`, `docs/release_checklist.md`, and lab documentation. | **Complete:** All documentation updated and synchronized. Added collector operations to `docs/operations.md`, recovery procedures verified in `docs/recovery.md` and `enforcement/recovery.md`, checklist completed in `docs/release_checklist.md`. | None. |
| 7.3 Release decision | Record ML, simulation, Linux lab (if pursued), and release gate evidence; document accepted deviations and known limitations. | **Complete:** Published `docs/release_decision.md` detailing ML Gate, Simulation Gate, Linux Lab Gate, Release Hardening Gate, accepted deviations, and sign-off matrix for v0.1.0-rc1. | None. |

**Phase exit (release gate) — verified complete (2026-10-26):** Gate evidence is recorded; documentation is
complete and reviewed; no unresolved critical security issue remains; known
limitations and operating/recovery procedures are clear. Default simulation remains enforced.

## Requirement and test traceability

The phase column identifies planned work, not completion. Test-case IDs refer
to [PRD.md](PRD.md) section 10.2.

| Requirement / test IDs | Phase | Verification method | Required evidence |
| --- | --- | --- | --- |
| FR-01 | 2 | Dataset validation, cleaning, reproducibility and split tests | Provenance/license record, cleaning results, split manifest |
| FR-02 | 2–3 | Shared feature-schema golden tests and compatibility checks | Versioned schema, matching training/runtime output, mismatch rejection |
| FR-03 | 2 | Candidate evaluation and selection review | Comparison, limitations, selection rationale |
| FR-04, NFR-01, NFR-02 | 2, 5, 7 | Held-out evaluation and documented performance measurement | Required metrics, workload/environment, target deviations and approval |
| FR-05, NFR-03, TC-05 | 3, 5 | API schema/range/size validation tests | Invalid requests rejected with no mitigation side effect |
| FR-06 | 3 | Predictor and artifact tests | Model/schema versions, score type, timestamp, score semantics |
| FR-07, TC-01–TC-04, TC-13 | 3, 5 | Hybrid decision matrix tests | Neither/one/both signal outcomes; single signal never initiates mitigation |
| FR-08, NFR-08 | 4 | API/UI integration tests | Dashboard agrees with backend and distinguishes every lifecycle state |
| FR-09, NFR-05, TC-08 | 3, 5 | Adapter assertions and isolated before/after network check | No host networking changes or privileged/network-modification operation |
| FR-10, NFR-06 | 3, 5–6 | Persistence and audit tests | Action identity, trigger, parameters, state, outcome, and failure records |
| FR-11, TC-07, TC-15, TC-16 | 3, 5 | Bounds/cooldown/control/lifecycle tests | Approved limits, cancellation/disable behavior, valid transitions |
| FR-12, TC-09 | 6 | Isolated enforcement and expiry tests | Approved scope, applied action, verified expiry |
| FR-13, TC-10, TC-12 | 6 | Cleanup failure, restart reconciliation, and recovery tests | Owned-resource evidence, no unrelated changes, fail-closed behavior |
| FR-14 | 3–4 | API filter/pagination and UI tests | Contract tests and accurate filtered results |
| FR-15, NFR-09 | 2–3 | Artifact inspection and reproducibility checks | Dataset, schema, model, threshold, and metric versions |
| FR-16, TC-14 | 5 | Generator/replay integration tests | Same runtime path and visible demonstration-data source |
| FR-17, NFR-04, TC-11 | 1, 3, 5–6 | Authentication/authorization tests | Permission matrix; unauthorized protected requests denied |
| NFR-06, NFR-07, NFR-10 | 1, 3, 5–7 | Audit tests, module review, documentation walkthrough | Auditable outcomes; safety-gate-only adapter path; reviewed procedures |
| TC-06 | 3, 5 | Protected-target tests | Unsafe action denied/constrained and recorded |
| TC-09–TC-10, TC-12 | 6 | Isolated expiry, cleanup failure, restart, recovery tests | Test logs and recovery evidence |

All PRD FR, NFR, and TC identifiers are mapped above. If requirements change,
update this table and the affected phase criteria before implementation.

## Open decisions and risks

The documents align on single-signal policy and lifecycle transitions.
Remaining implementation choices include:

| Decision | Why it matters | Affected phase |
| --- | --- | --- |
| Exact feature schema and final model approval criteria | Determines training/runtime compatibility and valid model selection evidence. | 2–3 |
| API response/query schemas and input limits | Required for interoperable, testable endpoint behavior. | 1, 3 |
| Prepared-file replay format | Required for safe, bounded replay without invented file semantics. | 5 |
| Minimal authentication/authorization mechanism and permission assignment | Protects administrative operations without assuming an unrequested identity platform. | 1, 3–6 |
| Threshold values, action bounds, maximum duration, and concurrency | Needed to enforce bounded requests; missing values must fail closed. | 3, 5–6 |
| SQLite schema and retention | Affects migrations, auditability, restart reconciliation, and storage. | 1, 3, 6 |
| Lab approval authority and operating procedure | Required before isolated enforcement is enabled. | 6 |

Risks include dataset representativeness and leakage, false positives, model
score misinterpretation, incomplete API/authorization details, and privilege
misuse. Mitigate through documented datasets/splits, held-out evaluation,
model-specific score handling, default simulation, bounded/authorized
actions, isolation, owned-resource cleanup, restart reconciliation, and
recovery tests. No risk is considered eliminated until evidence supports it.

## Phase completion checklist

- [x] **Phase 1 — Foundation and skeleton:** Completed and verified. Backend
  and frontend jobs passed hosted CI run `40202861846` for commit `f15f000`.
- [x] **Phase 2 — Data and ML baseline:** Verified complete for the current
  CIC-DDoS2019 offline baseline. Reproducible preparation, split generation,
  model comparison, selection, and approved artifact export are complete.
- [x] **Phase 3 — Backend, detection and policy:** Verified complete. Ingestion, detection, hybrid policy, safety gate, simulation, and all 14 PRD section 7 endpoints are implemented and verified with 33 passing automated tests.
- [x] **Phase 4 — Dashboard:** Verified complete. Typed API client, polling engine, dark cybersecurity theme (#050B14 + cyan/sky), Recharts telemetry, and all 5 dashboard views implemented with 0 lint and 0 typecheck errors.
- [x] **Phase 5 — Simulation and integration testing:** Verified complete.
  Bounded demonstration generator (`scripts/send_test_traffic.py`) and CSV
  replay (`scripts/replay_dataset.py`) implemented with `demo-generator:` and
  `demo-replay:` labels. All PRD Section 10.2 test cases (TC-01 to TC-07, TC-11
  to TC-16, and TC-08 simulation safety proof) implemented and passing (56/56
  total tests pass). Benchmark evidence recorded in
  `data/fixtures/benchmark_evidence.json` (inference latency mean 8.17ms < 10ms,
  peak memory 0.67MB < 512MB).
- [x] **Phase 6 — Isolated Linux lab:** Verified complete.
  Privileged enforcement agent (`enforcement/agent.py`) and rules (`enforcement/rules.py`)
  restricted to designated interface `sentrix0` and subnet `10.200.0.0/24`.
  Adapter (`backend/app/mitigation/linux_lab.py`), expiry manager (`enforcement/expiry.py`),
  restart reconciliation (`backend/app/mitigation/reconcile.py`), and runbook
  (`enforcement/recovery.md`) implemented. Automated tests for TC-09 (rule expiration),
  TC-10 (cleanup failure & recovery), and TC-12 (service restart reconciliation) pass.
- [x] **Phase 7 — Release hardening:** Verified complete. Automated security
  hardening suite (`test_phase7_security_and_hardening.py`) verified across 76
  total backend tests. Documentation synchronized across `docs/`, `enforcement/`,
  and root files. Formal release decision published in `docs/release_decision.md`
  authorizing `v0.1.0-rc1` under default simulation and isolated lab scope.
