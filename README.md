# SENTRIX DDoS Defense Platform

> **Detect. Defend. Stay Resilient.**

SENTRIX is a planned defensive DDoS detection and mitigation prototype. Its
target design analyzes flow-level network features and time-window statistics,
compares machine-learning evidence with threshold-based rules, and routes
eligible mitigation requests through a safety gate. A web dashboard is
planned for monitoring detections, alerts, and action outcomes.

SENTRIX is not production-ready and does not guarantee DDoS protection.
Architecture diagrams and planned API contracts describe intended behavior;
they do not demonstrate that a component is implemented or operational.

## Current status

The repository is an early implementation scaffold. Phase 1 now provides
validated backend settings, a token-protected health endpoint, a SQLite
connection/migration baseline, and a runnable frontend navigation shell. The
frontend pages are placeholders and do not consume backend data. The remaining
API, detection, policy, persistence domain models, mitigation, ML, generator,
and replay workflows are not implemented. Phase 1 checks have been run locally;
the configured hosted CI workflow has not yet reported a result.

Some model artifact files exist, but the repository does not establish that a
candidate has been evaluated and approved for runtime use. A file or module
path alone does not prove that its planned behavior is complete.

The implementation roadmap and exit criteria are in
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Do not treat the presence of
a file, model binary, endpoint module, or documentation as evidence that its
planned behavior has passed testing.

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
│   ├── migrations/                # Migration environment and initial revision
│   ├── app/
│   │   ├── main.py                # FastAPI app with request IDs and health route
│   │   ├── api/v1/                # Planned API modules/scaffolds
│   │   ├── core/                  # Settings, health auth, logging, error handling
│   │   ├── detection/             # Planned inference and model loading
│   │   ├── features/              # Planned versioned feature pipeline
│   │   ├── ingestion/             # Planned Pydantic schemas and validation
│   │   ├── mitigation/            # Planned simulation and lab adapters/lifecycle
│   │   ├── policy/                # Planned hybrid policy and safeguards
│   │   ├── safety/                # Planned safety gate
│   │   ├── services/              # Planned end-to-end pipeline
│   │   └── storage/               # SQLite engine/session base; repositories and audit planned
│   └── tests/                     # Phase 1 settings, health, and migration tests
├── frontend/
│   ├── package.json              # Next.js app scripts and dependencies
│   └── src/app/                  # Accessible navigation and five placeholder routes
├── .github/workflows/            # Backend and frontend CI checks
├── ml/                           # Training/evaluation script placeholders and config
├── models/                       # Artifact files present; approval/evaluation not established
├── notebooks/                    # Dataset/model exploration notebooks
├── data/
│   └── README.md                 # Dataset guidance; datasets are not included
├── collector/
│   └── lab_collector.py          # Placeholder
├── enforcement/                  # Planned isolated lab component and documentation
├── scripts/                      # Setup, lab, and traffic scripts are placeholders
└── docs/                         # API, operations, recovery, evaluation, release docs
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

The implemented `GET /api/v1/health` endpoint requires a bearer token by
default. With the unchanged development template, check it in PowerShell with:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/health `
  -Headers @{ Authorization = "Bearer dev-only-change-me" }
```

The initial Alembic revision establishes migration tracking only; domain
tables and the planned API workflows are not implemented. Configuration
validation rejects non-SQLite URLs and any mitigation mode other than
`simulation`. The service fails to start when authentication is required but
no token is configured.

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
python -m pytest backend/tests -q
```

The current tests cover Phase 1 configuration defaults/validation, authenticated
health responses, safe error output, and repeatable migrations. Broader
detection, policy, simulation, lab, ML, and demonstration tests remain planned.
The ML, traffic-generation, and replay helpers are still placeholders.

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

Only `GET /api/v1/health` is currently wired. All other listed routes are
planned contracts from the PRD and architecture, not available endpoints.

| Method | Endpoint | Purpose | Status |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Minimal authenticated service status | Implemented |
| `GET` | `/api/v1/models` | Model versions and active approved model | Planned |
| `GET` | `/api/v1/models/metrics` | Evaluation metrics | Planned |
| `POST` | `/api/v1/traffic/flows` | Submit validated flow observations | Planned |
| `GET` | `/api/v1/traffic/summary` | Traffic and window summaries | Planned |
| `POST` | `/api/v1/detection/analyze` | Analyze supplied flow/window features | Planned |
| `GET` | `/api/v1/alerts` | Filtered, paginated alerts | Planned |
| `GET` | `/api/v1/mitigations` | Mitigation history and status | Planned |
| `POST` | `/api/v1/mitigations/simulate` | Evaluate and record a simulated action | Planned |
| `POST` | `/api/v1/mitigations/{id}/cancel` | Cancel an authorized eligible action | Planned |
| `POST` | `/api/v1/mitigations/disable` | Authorized emergency-disable control | Planned |
| `GET` | `/api/v1/audit` | Authorized audit retrieval; optional JSON/CSV export | Planned |
| `GET` | `/api/v1/config/thresholds` | Read threshold configuration | Planned |
| `PATCH` | `/api/v1/config/thresholds` | Authorized threshold update | Planned |

For canonical purposes, safety semantics, and error requirements, see
[PRD.md](PRD.md). API response schemas are planned in
[docs/api_schemas.md](docs/api_schemas.md); that document is currently a
placeholder.

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
- [Dataset guidance](data/README.md) — intended dataset organization.
- [API schemas](docs/api_schemas.md) — planned API details; placeholder.
- [Model evaluation report](docs/model_evaluation_report.md) — planned
  evaluation evidence; placeholder.
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
