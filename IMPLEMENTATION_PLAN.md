# SENTRIX Implementation Plan

Step-by-step build plan for the SENTRIX DDoS Defense Platform, based on PRD v1.1, the README project structure and SYSTEM\_ARCHITECTURE.md. October 2026.

## Plan at a glance

| Phase | Focus | Sub-phases | Suggested time | Exit condition |
| --- | --- | --- | --- | --- |
| 1 | Foundation and skeleton | 1.1 to 1.4 | Weeks 1-2 | Health endpoint works, 5 dashboard routes load, CI is green |
| 2 | Data and ML baseline | 2.1 to 2.6 | Weeks 3-6 | ML gate: reproducible training and evaluation report |
| 3 | Backend, detection and policy | 3.1 to 3.7 | Weeks 7-9 | Every PRD section 7 endpoint validated and tested |
| 4 | Dashboard | 4.1 to 4.5 | Weeks 10-11 | Live and historical views run on real API data |
| 5 | Simulation and integration testing | 5.1 to 5.4 | Weeks 12-13 | Simulation gate: critical tests pass |
| 6 | Isolated Linux lab | 6.1 to 6.5 | Weeks 14-16 | Linux lab gate: enforcement, expiry, recovery verified |
| 7 | Release hardening | 7.1 to 7.3 | Week 17 | Release gate: docs complete, no critical security issues |

Times are proposals for part-time work. Adjust them to your schedule, but keep the order.

**Working rules for every phase**

- Build in dependency order: storage, ingestion, features, detection, policy, safety gate, adapters, API, dashboard.
- Write tests together with the code, not after it.
- Keep `MITIGATION_MODE=simulation` everywhere until the Linux lab gate passes.
- Feature definitions live only in `backend/app/features/`. Training scripts and notebooks import them; nothing is duplicated.
- Use one Git branch per phase and merge only when the phase exit condition is met.
- If the ML targets are not met, improve data, features or policy. Do not enable enforcement early.

## Pre-coding fixes (resolved)

The five inconsistencies found earlier are resolved in PRD v1.1, the README, `.env.example`, `backend/pyproject.toml` and SYSTEM\_ARCHITECTURE.md. Treat the table below as the project baseline.

| Item | Decision now in the repo |
| --- | --- |
| Auth default | `API_AUTH_REQUIRED=true` with a local `API_AUTH_TOKEN` placeholder |
| Dependencies | `backend/pyproject.toml`, installed with `pip install -e "backend[dev]"` |
| Database | `sentrix.db` (`sqlite:///./sentrix.db`) |
| License | No license claim for now. Add a `LICENSE` file only when you pick one |
| Operator endpoints | `POST /api/v1/mitigations/{id}/cancel`, `POST /api/v1/mitigations/disable`, `GET /api/v1/audit` |

Resolved setup and API details:

- The README starts Uvicorn from the repository root after installing the editable `app*` package from `backend/`.
- Authorized audit export is included as an optional `format=json|csv` query parameter on `GET /api/v1/audit`; JSON is the default.

## Phase 1: Foundation and skeleton

Covers: NFR-07, NFR-10. Goal: a running empty system with a repeatable setup.

### 1.1 Repository and tooling

Done when: a fresh clone has the full folder tree and ignore rules.

1. **Repository.** Run `git init`. Add the root `.gitignore` (`data/`, `*.db`, `.env`, `__pycache__/`, `node_modules/`, model binaries if not using Git LFS), `.env.example` and, once you choose a license, `LICENSE`.
2. **Folder tree.** Create the structure from the README, with placeholder files in empty folders. Put it in `scripts/setup_dev.sh`.

### 1.2 Backend skeleton

Done when: the API starts and `/api/v1/health` passes a pytest smoke test.

1. **Backend package.** Maintain `backend/pyproject.toml` with fastapi, uvicorn, pydantic-settings, sqlalchemy, alembic, scikit-learn, joblib, pandas, numpy and pyyaml as runtime dependencies; include pytest, httpx and ruff in the `dev` extra. Install with `pip install -e "backend[dev]"`.
2. **Settings.** In `core/config.py`, load and validate environment variables. Reject an unknown `MITIGATION_MODE` and refuse to start in `linux_lab` mode unless an explicit authorization setting is present.
3. **Error contract.** In `core/errors.py`, implement the PRD error format (`code`, `message`, `request_id`) with the status codes from PRD section 7.3. Never return stack traces.
4. **First endpoint.** Add `GET /api/v1/health` and a pytest smoke test.
5. **Database.** In `storage/database.py`, set up the SQLAlchemy engine for SQLite and initialize Alembic.

### 1.3 Frontend skeleton

Done when: all 5 routes load inside the sidebar layout.

1. **Next.js app.** Run `create-next-app` (TypeScript, Tailwind) and add Recharts.
2. **Layout and routes.** Build the fixed sidebar with the 5 routes: Overview, Alerts, Mitigation, History, Settings. Pages can be empty.
3. **API client.** Add `lib/api.ts` with a typed client for `/api/v1`.

### 1.4 Continuous integration

Done when: the pipeline is green on every push.

1. **Workflow.** Add a GitHub Actions workflow that runs ruff and pytest for the backend, plus lint and build for the frontend.

**Exit:** baseline requirements approved, `/api/v1/health` returns OK, all 5 dashboard routes load, CI passes.

## Phase 2: Data and ML baseline

Covers: FR-01 to FR-04, FR-15, NFR-01, NFR-02, NFR-09. Goal: a trustworthy model comparison before any detection logic is built.

### 2.1 Dataset acquisition and review

Done when: datasets are downloaded, documented and understood.

1. **Datasets.** Download CIC-DDoS2019 (primary) and optionally CIC-IDS2017. Record source, license, version and file hashes in `data/README.md`. Confirm what each label means.
2. **Exploration (notebook 01).** Check class balance, missing values, infinite values and duplicate rows. Note that CIC column names often have leading spaces.

### 2.2 Data preparation and split

Done when: `ml/prepare_data.py` produces the same train, validation and test files on every run.

1. **Data preparation (`ml/prepare_data.py`).**
   - Validate the schema and normalize column names.
   - Drop or fix NaN and infinite values.
   - Map labels to normal and attack.
   - Write a dataset version and hash into the output.
2. **Leakage-aware split.** Split by capture day, attack type or time period instead of random rows. Use a fixed seed and save the split manifest so the split can be reproduced.

### 2.3 Feature engineering

Done when: `features-v1` is defined once and used by training and inference.

1. **Feature definition (notebook 02, then `features/definitions.py`).**
   - Version the schema as `features-v1`: names, units, order and preprocessing.
   - Map dataset columns to the PRD features: packets per second, bytes per second, SYN rate, SYN-to-ACK ratio, new flows per second, flow duration, unique sources per window, rolling averages and burst statistics.
   - CIC files are flow-level, so window features (new flows per second, unique sources) must be derived by grouping flows into time windows. Build this in `features/windows.py`.
   - Drop any feature that is not available at inference time or that leaks the label or future data.

### 2.4 Model training

Done when: both candidate models are trained and saved from config.

1. **Random Forest (`train_rf.py`).** Use class weighting, tune tree count and depth on validation data, and use group-aware cross-validation.
2. **Isolation Forest (`train_iforest.py`).** Fit on benign traffic only. Tune the decision threshold on a separate labeled validation set. Document the score convention.

### 2.5 Evaluation and error analysis

Done when: both models have a full metric set on the held-out test set.

1. **Evaluation (`evaluate.py`).** Report precision, recall, F1, confusion matrix and false-positive rate. Measure p95 inference latency per observation, CPU and memory in a documented environment.
2. **Error analysis.** Inspect false positives and false negatives, especially SYN-flood-like cases.

### 2.6 Export and report

Done when: artifacts are versioned and the selection decision is written down.

1. **Export (`export_model.py`).** Write `models/rf-1.0.0/` containing `model.joblib`, `feature_schema.json` and `metrics.json` with thresholds. Do the same for `iforest-1.0.0/`. Add an approved-model pointer.
2. **Report.** Write `docs/model_evaluation_report.md` with the comparison, limitations, dataset-specific results and the model-selection decision.

**Exit (ML gate):** the pipeline reruns from raw data to artifacts and gives the same result, and metrics are documented. Targets are 90% precision, 90% recall and p95 latency under 100 ms. If a target is missed, either improve features and data or explicitly accept the deviation in the report.

## Phase 3: Backend, detection and policy

Covers: FR-05, FR-06, FR-07, FR-10, FR-11, FR-15, NFR-03, NFR-04, NFR-06, NFR-07. Goal: the full pipeline working through the API, in simulation mode.

Build in this order. Each step gets unit tests.

### 3.1 Storage layer

Done when: all tables and repositories exist with tests.

1. **Storage (`storage/`).** Tables for flow observations, detection events, alerts, mitigation actions, threshold configuration, model versions and audit events. Add repositories and an append-only `audit.py`.

### 3.2 Ingestion and runtime features

Done when: valid input is accepted and invalid input is rejected without side effects.

1. **Ingestion (`ingestion/`).** Pydantic schemas that match the PRD example request. Validate ranges, types, timestamp format (UTC ISO 8601), window size and feature-schema version. Invalid input returns 422 and never triggers mitigation (TC-05).
2. **Runtime features.** Finish `windows.py` and `preprocess.py` so inference uses the exact same code as training.

### 3.3 Detection engine

Done when: an observation returns a model-specific score with model version and timestamp.

1. **Model loader.** `model_loader.py` loads the approved artifact and refuses to start if its feature-schema version does not match.
2. **Predictor.** `predictor.py` returns a model-specific score with model version and timestamp. Never treat Isolation Forest scores as probabilities.

### 3.4 Policy engine

Done when: the decision table below is fully covered by unit tests.

1. **Policy engine (`policy/`).** Implement the decision table below.
2. **Cooldowns and allowlist.** Add `cooldown.py` for cooldowns and deduplication (TC-07) and `allowlist.py` for protected management targets (TC-06).

**Policy decision table**

| ML signal | Threshold signal | Outcome |
| --- | --- | --- |
| No | No | Continue monitoring |
| Yes | No | Alert and gather more evidence |
| No | Yes | Alert. Emergency action only if emergency criteria and safety checks pass |
| Yes | Yes | Request a bounded rate limit after safety validation |
| Any | Protected target or unauthorized | Deny or constrain |
| Any | Policy or enforcement failure | Stop new enforcement requests and alert the operator |

### 3.5 Safety gate and mitigation

Done when: no mitigation can reach an adapter except through the gate.

1. **Safety gate (`safety/gate.py`).** Check authorization, target validity, action bounds (rate, burst, duration, concurrency) and the current mode. The gate is the only path to an adapter.
2. **Mitigation (`mitigation/`).** Define the adapter interface in `base.py`, implement `simulation.py` (no host changes) and `lifecycle.py` with the states proposed, simulated, applied, expired, failed and recovered. Audit every state change.

### 3.6 Pipeline service

Done when: one call runs the whole chain and stores each result.

1. **Pipeline (`services/pipeline.py`).** Chain ingestion, features, detection, policy, safety gate and adapter, storing each result.

### 3.7 Authentication and API routes

Done when: every endpoint matches its documented schema and authorization tests pass.

1. **Authentication.** Add roles (for example viewer and admin). Threshold changes, cancel and disable require admin.
2. **API routes.** Implement all PRD v1.1 section 7 endpoints, including mitigation cancel, mitigation disable and audit. Support authorized audit export with `format=json|csv` (default `json`). Add pagination and filters (time, severity, status) to alerts and mitigations (FR-14), and rate limiting that returns 429.

**Exit:** every endpoint matches its documented schema, authorization tests pass, and a request sent to `/traffic/flows` produces a stored detection, alert and simulated action.

## Phase 4: Dashboard

Covers: FR-08, FR-14, NFR-08. Goal: an honest, readable view of real backend data.

### 4.1 Test data source

Done when: a script feeds normal and abnormal traffic to the running API.

1. **Traffic script.** Before building pages, write `scripts/send_test_traffic.py` to post normal and abnormal observations to the API. Without it the dashboard has nothing real to show, and the PRD forbids presenting sample data as live.

### 4.2 Shared UI building blocks

Done when: every page can reuse polling, state banners and the mode badge.

1. **Shared pieces.** `lib/polling.ts` (a polling hook with last-update time), `StatusBanner` (loading, empty, stale, disconnected, error), and `ModeBadge` that clearly separates normal, suspicious, simulated and enforced states.

### 4.3 Monitoring pages

Done when: Overview and Alerts show real data with filters.

1. **Overview.** Packet and byte rates, threat status, model health, open alerts, mitigation status, recent events and trends.
2. **Detection and Alerts.** Flow and window features, prediction, score with its documented meaning, model version, and filters by severity, time and status.

### 4.4 Control and history pages

Done when: operators can review, cancel and disable actions, and read history.

1. **Mitigation.** Current mode, action list with reason, duration, expiration and cleanup status, plus authorized cancel and emergency disable controls with confirmation dialogs.
2. **History and Analytics.** Historical trends, alert and mitigation timeline, audit records and export for authorized roles.
3. **Settings and Model Evaluation.** Threshold configuration (admin only), model version and evaluation metrics.

### 4.5 Accessibility and access control

Done when: the dashboard is usable by keyboard and respects roles.

1. **Accessibility.** Keyboard navigation, text labels next to colors, readable contrast, and a sidebar that collapses on small screens.
2. **Auth in the UI.** Hide or disable admin actions for non-admin roles. The backend still enforces the check.

**Exit:** all five pages show real API data, every error and stale state displays correctly, and the simulation-versus-enforced distinction is always visible.

## Phase 5: Simulation and integration testing

Covers: FR-09, NFR-05, TC-01 to TC-08, TC-11. Goal: prove the system is safe and correct before touching real networking.

### 5.1 Automated test cases

Done when: every listed test case exists as an automated test.

1. **Test cases.** Write automated tests for TC-01 normal traffic, TC-02 abnormal burst, TC-03 suspected SYN flood, TC-04 emergency threshold, TC-05 invalid values, TC-06 protected management traffic, TC-07 repeated alerts, TC-08 simulation safety and TC-11 unauthorized operator.

### 5.2 Simulation safety proof

Done when: it is shown that simulation never changes host networking.

1. **No-network-change proof (TC-08).** Run the full flow in a container or VM. Compare `nft list ruleset` and `tc qdisc show` before and after, and assert that the simulation adapter never calls a subprocess.

### 5.3 Security and integration tests

Done when: unsafe requests are denied and the full path is tested end to end.

1. **Security tests.** Unauthorized and malformed requests, invalid or protected targets, oversized payloads, and checks that no secrets or stack traces leak in errors.
2. **Integration tests.** One test that runs from `POST /traffic/flows` through to a recorded simulated mitigation, including cooldown and expiry.

### 5.4 Performance and fixes

Done when: measured numbers are recorded and open failures are fixed.

1. **Performance tests.** Measure latency percentiles, throughput, CPU and memory under load. Report measured values and do not claim real-time performance beyond them.
2. **Fix and document.** Record failures, fix them, and keep the results for the release checklist.

**Exit (simulation gate):** all critical detection, policy, authorization and no-network-change tests pass.

## Phase 6: Isolated Linux lab

Covers: FR-12, FR-13, NFR-04, NFR-10, TC-09, TC-10, TC-12. Goal: controlled enforcement, only inside an isolated lab.

### 6.1 Lab environment and threat model

Done when: the isolated lab exists and the threat model is written.

1. **Lab environment.** Use Linux virtual machines or network namespaces on an isolated, host-only network. Designate one lab interface and one test subnet. Nothing in the lab may reach outside systems.
2. **Threat model.** Write `enforcement/README.md`: what the agent can change, who can talk to it, and what happens if the API is compromised.

### 6.2 Enforcement agent

Done when: the agent applies and removes only its own rules, from validated objects only.

1. **Agent design (`enforcement/agent.py`).**
   - Runs as a separate privileged process. The FastAPI process stays unprivileged.
   - Listens on a local Unix socket with restricted permissions.
   - Accepts only validated policy objects (target, rate, burst, TTL). It never accepts shell commands or rule expressions.
   - Refuses any target outside the lab interface and subnet.
2. **Rule wrapper (`rules.py`).** Use a dedicated nftables table or tc class owned by SENTRIX, so cleanup never touches administrator rules. Tag every rule with its action ID.
3. **Expiry (`expiry.py`).** Remove rules at their TTL, then verify removal and report the result.

### 6.3 API-side integration

Done when: the API can request enforcement only through the adapter and gate.

1. **Adapter (`mitigation/linux_lab.py`).** A client of the agent behind the same adapter interface. It is selectable only with explicit configuration and authorization.
2. **Reconciliation (`mitigation/reconcile.py`).** On service start, compare stored action states with actual lab rules and fix mismatches before enforcement resumes (TC-12).

### 6.4 Recovery and lab traffic

Done when: a cleanup failure has a tested recovery path and lab traffic is ready.

1. **Recovery.** Write `enforcement/recovery.md` for cleanup failure (TC-10) and test that a failure raises an operator alert and stops new enforcement.
2. **Lab traffic.** Build a bounded generator in `collector/` and `scripts/` for benign and attack-like traffic. Use it only against your own lab targets, with strict rate and count limits. Keep this lab data separate from data used to tune thresholds, and evaluate the chosen model on it.

### 6.5 Lab tests

Done when: all three lab test cases pass.

1. **Run tests.** TC-09 rule expiration verified, TC-10 cleanup failure and recovery, TC-12 service restart reconciliation.

**Exit (Linux lab gate):** enforcement, expiration, restart reconciliation and recovery are all verified in isolation.

## Phase 7: Release hardening

Goal: pass the release gate and make the project reproducible for others.

### 7.1 Documentation

Done when: every command in the README works from a clean clone.

1. **Documentation.** Complete `docs/operations.md`, `docs/recovery.md`, `docs/api_schemas.md` and `docs/release_checklist.md`. Fix the README so every command works from a clean clone.

### 7.2 Security and deployment review

Done when: no critical issue is open and all three environments are verified.

1. **Security review.** Check there are no hardcoded secrets, authentication is on by default, admin routes are protected and the emergency disable works.
2. **Deployment check.** Verify Environment A (local), Environment B (web, enforcement disabled) and Environment C (lab). Do not assume serverless hosting can run collectors or privileged networking.

### 7.3 Final gates and demo

Done when: all 4 gate results are recorded and the demo runs.

1. **Final run.** Execute the 4 release gates in order: ML, simulation, Linux lab, release. Record the results.
2. **Demo and write-up.** Prepare a short demo script covering normal traffic, a simulated attack, an alert, a simulated mitigation and its expiry. Describe known limitations honestly: the project is a research and defensive prototype, not production DDoS protection.

**Exit (release gate):** no unresolved critical security issues, emergency disable and operations documentation complete.

## Requirement coverage by phase

| Requirements | Built in |
| --- | --- |
| FR-01, FR-03, FR-04 | Phase 2 |
| FR-02, FR-15, NFR-09 | Phases 2 and 3 |
| FR-05, FR-06, FR-07, FR-10, FR-11 | Phase 3 |
| FR-08, FR-14 | Phase 4 |
| FR-09, NFR-05, TC-01 to TC-08, TC-11 | Phases 3 and 5 |
| FR-12, FR-13, TC-09, TC-10, TC-12 | Phase 6 |
| NFR-01, NFR-02 | Phases 2 and 5 |
| NFR-03, NFR-04, NFR-06, NFR-07 | Phase 3, tested in Phase 5 |
| NFR-08 | Phase 4 |
| NFR-10 | Phases 1, 6 and 7 |

## Main risks and how the plan handles them

- **Dataset does not match your lab traffic.** Validate the chosen model on separate lab traffic in Phase 6 and document the gap.
- **Inflated metrics from leakage.** Split by capture or time and keep lab data away from threshold tuning.
- **False positives disrupt legitimate traffic.** Require both signals for normal actions, bound every action, use allowlists and cooldowns, and always allow operator disable.
- **Enforcement privilege misuse.** Keep the agent separate, accept only validated objects and own only its own rules.
- **Schedule slips in Phase 2.** The ML baseline decides whether the project works. Finish it before spending time on the dashboard polish.
