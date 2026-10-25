# SENTRIX DDoS Defense Platform

> **Detect. Defend. Stay Resilient.**

SENTRIX is a planned lightweight machine-learning-powered DDoS detection and mitigation system. Its target design combines flow-level network feature analysis and time-window aggregation with Random Forest and Isolation Forest models, a hybrid policy engine, safety gates, and a Next.js monitoring dashboard.

> **Project status:** The PRD and architecture describe the target system. Features and endpoints are implemented phase by phase according to [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md); the structure may currently contain scaffolding or placeholders.

---

## 🌟 Key Features

- **Traffic Ingestion & Window Aggregation**: Planned Pydantic validation for incoming network flow data with versioned window-based feature statistics.
- **Dual ML Detection Engine**: Planned comparison of supervised (Random Forest) and unsupervised (Isolation Forest) models for threat scoring.
- **Hybrid Policy Engine**: Planned evaluation of ML scores alongside configurable rule thresholds.
- **Safety Gate & Simulation Adapter**: Planned bounds and authorization checks; **Simulation Mode** is the default, without host network modifications.
- **Operator Controls & Audit**: Planned protected endpoints for canceling/disabling mitigation actions and retrieving audit records.
- **Privileged Lab Enforcement**: A later-phase Linux enforcement agent (`tc`/`nftables`) for isolated lab environments, subject to expiry and recovery testing.
- **Next.js Dashboard**: Planned traffic visualization, active alerts, mitigation lifecycle tracking, and system configuration controls.

---

## 🛠️ Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Backend API** | Python 3.10+, FastAPI, Pydantic, SQLAlchemy, SQLite |
| **Machine Learning** | scikit-learn, joblib, pandas, NumPy, PyYAML |
| **Frontend** | Next.js 14, React, TypeScript, Tailwind CSS, Recharts |
| **Mitigation & Lab** | Simulation Adapter, Linux `nftables`/`tc` (Lab Mode) |

---

## 📂 Project Structure

```text
SENTRIX/
├── README.md                           # Project overview & getting started
├── IMPLEMENTATION_PLAN.md              # Phased development plan and exit gates
├── PRD.md                              # Product Requirements Document
├── SYSTEM_ARCHITECTURE.md              # System Architecture & Mermaid Workflows
├── .gitignore                          # Excluded patterns (data/, *.db, .env, etc.)
├── .env.example                        # Template environment configuration
│
├── data/                               # Datasets (git-ignored)
│   ├── README.md                       # Data source details, licensing & labels
│   ├── raw/                            # CIC-DDoS2019, CIC-IDS2017 datasets
│   ├── processed/                      # Cleaned features and train/val/test splits
│   └── lab/                            # Controlled lab environment traffic
│
├── notebooks/                          # Exploration and research notebooks
│   ├── 01_dataset_exploration.ipynb
│   ├── 02_feature_engineering.ipynb
│   ├── 03_random_forest.ipynb
│   ├── 04_isolation_forest.ipynb
│   └── 05_model_comparison.ipynb
│
├── ml/                                 # Reproducible ML training pipeline
│   ├── prepare_data.py                 # Schema validation, cleaning & splitting
│   ├── train_rf.py                     # Random Forest classifier training
│   ├── train_iforest.py                # Isolation Forest anomaly detection
│   ├── evaluate.py                     # Evaluation metrics (F1, FPR, Latency, CPU/RAM)
│   ├── export_model.py                 # Versioned model artifact export
│   └── configs/
│       └── training.yaml               # Training hyperparameters and seed configs
│
├── models/                             # Versioned model artifacts
│   ├── rf-1.0.0/                       # Model binary, schema & metrics JSON
│   ├── iforest-1.0.0/                  # Anomaly detection model artifacts
│   └── approved_model.joblib           # Currently active deployment model
│
├── backend/                            # FastAPI modular monolith
│   ├── pyproject.toml                  # Backend package & dependencies definition
│   ├── .gitignore
│   ├── app/
│   │   ├── main.py                     # FastAPI app factory & router registration
│   │   ├── core/                       # App settings, security, logging, error handler
│   │   ├── api/v1/                     # REST API endpoints (health, traffic, alerts, etc.)
│   │   ├── ingestion/                  # Traffic ingestion schemas & validation
│   │   ├── features/                   # Feature definitions, windows & preprocessing
│   │   ├── detection/                  # Model loaders, prediction & scoring
│   │   ├── policy/                     # Decision engine, thresholds & cooldowns
│   │   ├── safety/                     # Safety gate (auth, bounds, target check)
│   │   ├── mitigation/                 # Mitigation adapters (Simulation, Linux Lab)
│   │   ├── storage/                    # Database models, repositories & audit logs
│   │   └── services/                   # End-to-end detection & response pipeline
│   ├── migrations/                     # Database migration scripts
│   └── tests/                          # Unit, integration, security & test case suites
│
├── enforcement/                        # Privileged Linux enforcement process (Phase 6)
│   ├── README.md                       # Threat model & least-privilege security notes
│   ├── agent.py                        # Privileged enforcement daemon
│   ├── rules.py                        # tc/nftables wrapper
│   ├── expiry.py                       # Rules TTL cleanup & verification
│   ├── recovery.md                     # Cleanup failure recovery procedures
│   └── tests/                          # Lab-only isolation tests
│
├── collector/                          # Metrics collection utilities
│   └── lab_collector.py                # Posts flow metrics to /traffic/flows
│
├── frontend/                           # Next.js web dashboard
│   ├── package.json                    # Frontend dependencies & scripts
│   └── src/
│       ├── app/                        # App Router pages (overview, alerts, mitigation, etc.)
│       ├── components/                 # UI components (charts, tables, badges)
│       ├── lib/                        # API client & polling hooks
│       └── types/                      # TypeScript definitions
│
├── scripts/                            # Operational helper scripts
│   ├── setup_dev.sh                    # Development environment setup
│   ├── run_lab.sh                      # Isolated lab launcher
│   └── send_test_traffic.py            # Test traffic generator fixtures
│
└── docs/                               # System documentation
    ├── model_evaluation_report.md      # ML performance report
    ├── api_schemas.md                  # REST API schemas & payload examples
    ├── operations.md                   # Installation, operation & auditing guide
    ├── recovery.md                     # Troubleshooting & recovery instructions
    └── release_checklist.md            # Release gates & validation criteria
```

---

## 🚀 Getting Started

### Prerequisites

- **Python**: `3.10` or higher
- **Node.js**: `18.x` or higher
- **Package Manager**: `npm` / `pnpm` / `yarn` and `pip` / `poetry`

### 1. Environment Setup

Copy `.env.example` to create your local `.env` configuration:

```bash
cp .env.example .env
```

Default environment parameters:
```ini
APP_ENV=development
MITIGATION_MODE=simulation
MODEL_PATH=models/approved_model.joblib
DATABASE_URL=sqlite:///./sentrix.db
API_AUTH_REQUIRED=true
API_AUTH_TOKEN=dev-only-change-me
```

`API_AUTH_TOKEN` is a local-development placeholder. Replace it with a
secure secret in any shared or deployed environment, and never commit a
real token. Send it as a bearer token when calling protected API routes.

### 2. Backend Setup

From the repository root, install the backend and its dependencies using
the existing `backend/pyproject.toml`:

```bash
pip install -e "backend[dev]"
uvicorn app.main:app --reload --port 8000
```

The API documentation will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 3. Frontend Setup

In a separate terminal, navigate to `frontend/` and start the Next.js dev server:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser to view the SENTRIX dashboard.

### 4. Planned ML Pipeline & Tests

These are target commands from the implementation plan. The corresponding
scripts and test suites must be implemented in Phases 2 and 3 before these
commands perform the planned work.

- **Data Preparation & Training**:
  ```bash
  python ml/prepare_data.py
  python ml/train_rf.py
  python ml/evaluate.py
  ```

- **Run Backend Tests**:
  ```bash
  cd backend
  pytest
  ```

---

## 📖 Documentation

- [Implementation Plan](IMPLEMENTATION_PLAN.md) - Development phases, order, and exit gates
- [System Architecture](SYSTEM_ARCHITECTURE.md) - Target system diagrams and API contract
- [Product Requirements Document (PRD)](PRD.md) - Project scope, functional & non-functional requirements
- [API Specifications](docs/api_schemas.md) - OpenAPI & payload details
- [Operations Guide](docs/operations.md) - Deployment and operational procedures
- [Recovery Procedures](docs/recovery.md) - Emergency cleanup and recovery steps

---

## 🛡️ Security & Mitigation Notice

By default, SENTRIX requires API authentication (`API_AUTH_REQUIRED=true`)
and operates in **Simulation Mode**
(`MITIGATION_MODE=simulation`). In this mode, detection decisions and
mitigation policies are logged and tracked without making any host network
modifications. Linux enforcement (`nftables`/`tc`) is confined to isolated
lab environments.
