# SENTRIX DDoS Defense Platform 

> **Detect. Defend. Stay Resilient.**

SENTRIX is a defensive DDoS detection and mitigation prototype. It analyzes
flow-level network features and time-window statistics, evaluates
machine-learning inference alongside threshold-based traffic rules in a
dual-signal hybrid policy, and routes eligible mitigation requests through a
fail-closed safety gate.

SENTRIX is an active defensive prototype and control plane. It is tested
against public labeled datasets (CIC-DDoS2019) and controlled flow records.
By default, SENTRIX operates in `simulation` mode, recording and evaluating
mitigations without modifying host networking or firewall tables. It is not
production-ready and does not guarantee DDoS protection on arbitrary live networks.

## Current status

Phases 1, 2, and 3 are **verified complete**:
- **Phase 1 (Foundation):** Validated configuration, token-protected health endpoint, SQLite connection, Alembic migration framework, and runnable frontend navigation shell. Hosted CI is green (`40202861846` for commit `f15f000`).
- **Phase 2 (Data & ML Baseline):** The CIC-DDoS2019 dataset was validated, cleaned, and deterministically partitioned. Both Random Forest and Isolation Forest candidates were trained and evaluated on held-out test splits. Random Forest achieved 99.98% precision, 99.96% recall, 99.97% F1, 1.73% FPR, and 4.45 ms p95 latency, passing all criteria, and was exported as the runtime approved model (`models/approved_model.joblib`) under schema `1.0.0`. Isolation Forest produced a 54.76% FPR and was rejected. Detailed evidence is documented in [docs/model_evaluation_report.md](docs/model_evaluation_report.md).
- **Phase 3 (Backend, Detection, and Policy):** Fully implemented SQLAlchemy domain persistence (observations, detections, alerts, mitigations, thresholds, and audit), Pydantic ingestion with UTC timestamps and range validation, runtime model inference, sliding-window traffic aggregation, dual-signal hybrid policy engine, fail-closed safety gate (enforcing allowlists, duration/rate limits, concurrency caps, and emergency disable), simulation mitigation adapter, state machine lifecycle management, and all 14 PRD Section 7 REST API endpoints. The test suite comprises 33 passing automated tests with 0 lint errors.

Upcoming phases:
- **Phase 4 (Dashboard):** Wiring the Next.js React frontend to consume backend API endpoints for live telemetry, alerts, and controls.
- **Phase 5 (Simulation & Integration):** End-to-end traffic replay and verification of host network non-interference.
- **Phase 6 (Isolated Linux Lab):** Gated Linux `nftables`/`tc` enforcement in an isolated lab environment.
- **Phase 7 (Release Hardening):** Full regression, security review, and release verification.

## Intended workflow

### Offline model training

The planned training pipeline uses public labeled flow datasets, primarily
CIC-DDoS2019. CIC-IDS2017 is an optional secondary dataset where supported by
the requirements and available features. The workflow will validate and clean
data, create reproducible leakage-aware splits, apply a versioned feature
schema, train and compare Random Forest and Isolation Forest candidates, and
document model selection before an artifact is used for runtime inference.

Neither model is presumed to be selected. Random Forest outputs and Isolation
Forest anomaly scores have model-specific meanings; an anomaly score is not a
probability unless a calibration method is explicitly defined and validated.

### Demonstration and runtime path

The intended initial demonstration accepts both generated flow records and
prepared flow records replayed from a file. Both inputs must use the same
runtime ingestion, validation, feature processing and window aggregation,
inference, policy, persistence, and reporting path.

Generated or replayed records are **demonstration data, not live network
telemetry** and are not proof of real-world network protection. The generator
and file-replay workflow are planned; the current helper scripts are
placeholders and do not yet implement them.

### Detection and mitigation behavior

The target hybrid policy treats the model signal and threshold signal
separately:

- Neither indicates a threat: continue monitoring.
- Exactly one indicates a threat: create an alert and gather evidence by
  default; do not automatically mitigate.
- Both indicate a threat: consider a bounded mitigation request, subject to
  authorization, target validation, limits, mode, and all safety checks.

The PRD and implementation plan follow this policy. The mitigation lifecycle
also distinguishes terminal `simulated` outcomes from `expired` applied lab
actions; a simulated action is never a network change.

**Simulation is the default.** Simulation must not modify host firewall rules,
routing, traffic-control settings, or other host networking, and must not
invoke privileged enforcement or networking-modification operations. A
simulated action is not a network change.

Linux enforcement using `nftables` and/or `tc` is a later-stage, restricted
feature for an isolated lab. It is not a normal fallback from simulation and
must remain disabled until simulation-safety and authorization tests,
isolated enforcement/expiry/cleanup/restart-reconciliation tests, recovery
checks, required release gates, and explicit lab approval are complete.
Cleanup may affect only SENTRIX-owned resources.

## Technology stack

| Area | Intended technology and role |
| --- | --- |
| Backend | Python and FastAPI for the API and modular backend; Pydantic for request validation. |
| Persistence | SQLite, with the planned local database filename `sentrix.db`. |
| Machine learning | scikit-learn; Random Forest and Isolation Forest are candidate models. Planned data tooling includes pandas, NumPy, joblib, and PyYAML. |
| Frontend | Next.js is the frontend framework; React is the UI library, with TypeScript, Tailwind CSS, and Recharts. |
| Lab enforcement | Linux `nftables` and/or `tc` in a later, isolated lab phase only. |

The Python package manifest currently lists the backend dependencies in
[backend/pyproject.toml](backend/pyproject.toml). Frontend dependencies and
reproducible npm scripts are defined in
[frontend/package.json](frontend/package.json) and
[frontend/package-lock.json](frontend/package-lock.json).

## Repository map

This tree reflects the current repository snapshot. Paths marked **planned**,
**placeholder**, or **scaffold** are not represented as working features.

```text
SENTRIX/
├── README.md
├── PRD.md
├── SYSTEM_ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── .env.example                   # Local settings template with a development-only token
├── backend/
│   ├── pyproject.toml             # Python package and dependency manifest
│   ├── alembic.ini                # SQLite migration configuration
│   ├── migrations/                # Alembic environment and initial DDL revision
│   ├── app/
│   │   ├── main.py                # FastAPI application wiring all 14 API endpoints
│   │   ├── api/v1/                # Implemented API routers (health, models, traffic, detection, alerts, mitigations, config, audit)
│   │   ├── core/                  # Settings, auth dependencies, logging, error handlers
│   │   ├── detection/             # Model loader, predictor, and threat scoring
│   │   ├── features/              # Schema 1.0.0 definitions, sanitization, sliding windows
│   │   ├── ingestion/             # Pydantic validation schemas
│   │   ├── mitigation/            # Simulation adapter, lifecycle state machine, reconciliation
│   │   ├── policy/                # Dual-signal hybrid policy, allowlist, cooldown manager
│   │   ├── safety/                # Fail-closed safety gate (bounds, rate limits, emergency disable)
│   │   ├── services/              # Pipeline ingestion-to-simulation orchestration
│   │   └── storage/               # SQLite engine, domain models, typed repositories, audit
│   └── tests/                     # 33 automated tests (core, storage, unit, API contracts)
├── frontend/
│   ├── package.json              # Next.js app scripts and dependencies
│   └── src/app/                  # Accessible navigation and five dashboard route views
├── .github/workflows/            # Backend and frontend CI workflows
├── ml/                           # Data preparation, training, evaluation, and export scripts
├── models/                       # Versioned models and approved runtime artifact
├── notebooks/                    # Dataset and model exploration notebooks
├── data/
│   └── README.md                 # Dataset provenance, licensing, and schema 1.0.0 definition
├── collector/
│   └── lab_collector.py          # Placeholder for lab collector
├── enforcement/                  # Planned isolated Linux lab enforcement and documentation
├── scripts/                      # Setup and demo traffic helper scripts
└── docs/                         # API specification, ML evaluation report, operations guides
```

For the intended component design and data flow, see
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md). The architecture and PRD are
planning documents, not implementation evidence.

## Setup and checks

### Prerequisites

- Python 3.10 or later
- Node.js 20 or later and npm

### Backend

From the repository root, copy the development template and install the
backend package and development dependencies:

```powershell
Copy-Item .env.example .env
python -m pip install -e "backend[dev]"
python -m alembic -c backend/alembic.ini upgrade head
```

The example token is for local development only. Replace it before exposing
the service to anyone else; never commit a real secret. Start the API from the
repository root:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The backend provides 14 REST API endpoints under `/api/v1/`, all protected by
bearer token authentication by default. With the development template, test
service health with PowerShell:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/health `
  -Headers @{ Authorization = "Bearer dev-only-change-me" }
```

Alembic migrations automatically initialize all SQLite domain tables (`observations`,
`detections`, `alerts`, `mitigations`, `threshold_configs`, `audit_events`).
Configuration validation enforces SQLite database URLs and `simulation` mitigation
mode, preventing accidental host modification.

### Frontend

Install from the frontend directory, then start the navigation shell:

```powershell
Push-Location frontend
npm ci
npm run dev
```

The Overview, Alerts, Mitigation, History, and Settings routes currently show
scaffold notices, not real telemetry or operator controls. Use `npm run lint`,
`npm run typecheck`, and `npm run build` there to run frontend checks.

### Backend tests and lint

From the repository root:

```powershell
python -m ruff check backend/app backend/tests backend/migrations
python -m pytest backend/tests/core backend/tests/storage backend/tests/unit backend/tests/api/test_api_contracts.py -v
```

The test suite contains 33 automated tests covering configuration validation,
repeatable migrations, storage repositories, feature sanitization and sliding windows,
model loading and inference, dual-signal policy matrix, safety gate allowlists/bounds,
mitigation lifecycle state machine, and all 14 API endpoint contracts.

### CI

The workflow at `.github/workflows/ci.yml` runs backend tests/lint and frontend
lint/type-check/build on pushes and pull requests. The equivalent commands
have been run locally; a hosted CI run is still required before claiming the
Phase 1 exit gate is complete.

## Intended configuration and security

The environment template currently contains these intended values:

| Variable | Template value | Meaning |
| --- | --- | --- |
| `APP_ENV` | `development` | Intended environment label. |
| `MITIGATION_MODE` | `simulation` | Safe default; lab enforcement is not enabled. |
| `MODEL_PATH` | `models/approved_model.joblib` | Intended path; it does not establish that an approved runtime model is available. |
| `DATABASE_URL` | `sqlite:///./sentrix.db` | Intended SQLite database location. |
| `API_AUTH_REQUIRED` | `true` | The implemented health endpoint requires authentication by default. |
| `API_AUTH_TOKEN` | `dev-only-change-me` | Development-only placeholder; never use as a real shared/deployed secret. |

The backend validates these settings at startup. The health endpoint enforces
the bearer token when authentication is required; authorization for future
administrative operations is not implemented. The simulation mode is
validated, but no mitigation adapter is wired. When those features are
implemented:

- Protected API operations must be authenticated and authorized by the
  backend; dashboard controls are not an authorization boundary.
- Threshold updates, cancellation, emergency disable, audit access, and lab
  approval require defined permissions.
- Keep real credentials out of source control, logs, and error responses.
- Simulation must not invoke privileged networking operations or alter host
  networking.
- Future lab enforcement must use least privilege, bounded actions, expiry,
  SENTRIX-owned cleanup, restart reconciliation, and tested recovery.
- Audit records must distinguish requested actions from confirmed outcomes.

## API contract status

All 14 endpoints defined in the PRD are implemented in `backend/app/api/v1/` and
verified against contract test fixtures.

| Method | Endpoint | Purpose | Status |
| --- | --- | --- | --- |
| `GET` | `/api/v1/health` | Minimal authenticated service status | Implemented |
| `GET` | `/api/v1/models` | Model versions and active approved model | Implemented |
| `GET` | `/api/v1/models/metrics` | Evaluation metrics | Implemented |
| `POST` | `/api/v1/traffic/flows` | Submit validated flow observations | Implemented |
| `GET` | `/api/v1/traffic/summary` | Traffic and window summaries | Implemented |
| `POST` | `/api/v1/detection/analyze` | Analyze supplied flow/window features | Implemented |
| `GET` | `/api/v1/alerts` | Filtered, paginated alerts | Implemented |
| `GET` | `/api/v1/mitigations` | Mitigation history and status | Implemented |
| `POST` | `/api/v1/mitigations/simulate` | Evaluate and record a simulated action | Implemented |
| `POST` | `/api/v1/mitigations/{id}/cancel` | Cancel an authorized eligible action | Implemented |
| `POST` | `/api/v1/mitigations/disable` | Authorized emergency-disable control | Implemented |
| `GET` | `/api/v1/audit` | Authorized audit retrieval; optional JSON/CSV export | Implemented |
| `GET` | `/api/v1/config/thresholds` | Read threshold configuration | Implemented |
| `PATCH` | `/api/v1/config/thresholds` | Authorized threshold update | Implemented |

For canonical schemas, query parameters, request-body models, and error
responses, see [docs/api_schemas.md](docs/api_schemas.md).

## Development workflow

The development sequence follows the phases in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md):

1. Establish project requirements, repository structure, and skeleton.
2. Prepare public datasets, engineer versioned features, evaluate both model
   candidates, and document selection.
3. Implement persistence, ingestion, inference, hybrid policy, safety gate,
   simulation, and API contracts.
4. Connect the dashboard to backend data and make demonstration-data status
   visible.
5. Implement generator and prepared-file replay through the shared runtime
   path; test simulation, authorization, lifecycle, audit, and no-network
   modification.
6. Only after prior gates, verify restricted lab enforcement, expiry,
   SENTRIX-owned cleanup, restart reconciliation, and recovery in isolation.
7. Complete release hardening and operating, troubleshooting, and recovery
   documentation.

These are planned steps, not a record of completed work. Add runnable
commands and test instructions as each component is implemented and
validated.

## Documentation

- [Product Requirements Document](PRD.md) — scope, requirements, API
  contracts, tests, and acceptance gates.
- [System Architecture](SYSTEM_ARCHITECTURE.md) — intended architecture,
  trust boundaries, and workflows.
- [Implementation Plan](IMPLEMENTATION_PLAN.md) — development phases and
  exit criteria.
- [Dataset guidance](data/README.md) — dataset provenance, license, schema, and label semantics.
- [API schemas](docs/api_schemas.md) — complete specification for all 14 REST endpoints, request/response models, and error responses.
- [Model evaluation report](docs/model_evaluation_report.md) — candidate comparison, selection rationale, and performance evaluation.
- [Operations guide](docs/operations.md) — planned operating instructions;
  placeholder.
- [Recovery procedures](docs/recovery.md) — planned recovery guidance;
  placeholder.
- [Release checklist](docs/release_checklist.md) — planned release evidence;
  placeholder.
- [Lab enforcement overview](enforcement/README.md) and
  [lab recovery notes](enforcement/recovery.md) — planned lab-only
  documentation.

## Limitations

SENTRIX is intended as a research and defensive prototype. Public datasets
may not represent a deployment network, and model scores do not prove
malicious intent. Detection quality, latency, and resource use must be
measured and documented. No production-scale protection or guaranteed
detection capability is claimed.
