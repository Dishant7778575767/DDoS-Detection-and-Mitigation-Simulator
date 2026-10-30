# SENTRIX — Developer & Operator Run Guide

> **Step-by-step local execution guide for running, testing, injecting traffic, and operating SENTRIX.**

This document provides clear, verified instructions for running the complete SENTRIX platform locally on **Windows PowerShell** and **Linux / macOS Bash**.

---

## 1. Required Software Installations

Ensure the following tools are installed on your workstation:

| Requirement | Supported Versions | Verification Command | Notes |
| :--- | :---: | :--- | :--- |
| **Python** | `3.10` or `3.11` | `python --version` | Python 3.11 recommended |
| **Node.js** | `18.x`, `20.x`, `22.x` | `node -v` | Node 20 LTS recommended |
| **npm** | `9.x` or `10.x` | `npm -v` | Installed with Node.js |
| **Git** | `2.x+` | `git --version` | For cloning repository |
| **Docker** (Optional) | `24.0+` | `docker --version` | Required for containerized setup |
| **Docker Compose** | `2.20+` | `docker compose version` | Required for containerized setup |

---

## 2. Repository Setup

Clone the repository and enter the root project directory:

```bash
# Clone the repository
git clone https://github.com/your-org/DDoS-Detection-and-Mitigation-Simulator.git

# Navigate into the project root
cd DDoS-Detection-and-Mitigation-Simulator
```

**Expected Result:** You are in `d:\DDoS-Detection-and-Mitigation-Simulator` (Windows) or `/path/to/DDoS-Detection-and-Mitigation-Simulator` (Linux/macOS).

---

## 3. Virtual Environment Setup

Create an isolated Python virtual environment inside the repository root.

### On Windows (PowerShell):
```powershell
# Directory: Repository Root
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
```

> **Troubleshooting Execution Policy Error:**
> If PowerShell shows `cannot be loaded because running scripts is disabled on this system`, run:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\.venv\Scripts\Activate.ps1
> ```

### On Linux / macOS (Bash / Zsh):
```bash
# Directory: Repository Root
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate
```

**Expected Result:** Your terminal prompt will be prefixed with `(.venv)`.

---

## 4. Backend Dependency Installation

Install the backend package with development and testing dependencies in editable mode:

```bash
# Directory: Repository Root (with .venv active)
pip install -e "backend[dev]"
```

**Expected Result:** Pip installs FastAPI, Uvicorn, SQLAlchemy, Alembic, Scikit-learn, NumPy, Pandas, Boto3, Pytest, and Ruff without errors.

---

## 5. Frontend Dependency Installation

Install Next.js and React dependencies:

```bash
# Directory: frontend/
cd frontend
npm install
cd ..
```

**Expected Result:** `node_modules` is populated and `package-lock.json` is verified.

---

## 6. Environment Configuration File

Create your local `.env` configuration from the provided `.env.example`:

### On Windows (PowerShell):
```powershell
# Directory: Repository Root
Copy-Item .env.example .env
```

### On Linux / macOS (Bash):
```bash
# Directory: Repository Root
cp .env.example .env
```

Open `.env` in an editor. For standard local development, the following default settings are recommended:

```ini
APP_ENV=development
MODEL_PATH=models/approved_model.joblib
DATABASE_URL=sqlite:///./sentrix.db
API_AUTH_REQUIRED=false
API_AUTH_TOKEN=local-dev-secret-token
AWS_REGION=ap-south-1
AWS_KINESIS_STREAM_NAME=sentrix-cloudfront-realtime-logs
AWS_KINESIS_CONSUMER_ENABLED=false
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

> [!NOTE]
> Setting `API_AUTH_REQUIRED=false` allows quick local exploration without needing to paste Bearer tokens on every curl request. In production, always set `API_AUTH_REQUIRED=true`.

---

## 7. Database Initialization & Migrations

SENTRIX uses SQLAlchemy 2.0 with Alembic database migrations.

Initialize the SQLite database and apply all schema migrations up to `head`:

```bash
# Directory: Repository Root (with .venv active)
alembic -c backend/alembic.ini upgrade head
```

**Expected Result:** Alembic applies migrations `0001_initial`, `0002_observation_target_ip`, and `0003_aws_cloudfront_kinesis`, creating `sentrix.db`.

---

## 8. Running the Application (Dual Terminal Mode)

For local development with live code reloading:

### Terminal 1: Backend Service (FastAPI)
```powershell
# Windows PowerShell (Repository Root)
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

```bash
# Linux / macOS Bash (Repository Root)
source .venv/bin/activate
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

**Expected Output:**
```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

Verify backend health in a browser or curl:
```bash
curl http://127.0.0.1:8000/api/v1/health
```
**Response:** `{"status":"healthy","version":"0.1.0","environment":"development",...}`

---

### Terminal 2: Frontend Service (Next.js 16)
Open a new terminal window:

```bash
# Directory: frontend/
cd frontend
npm run dev
```

**Expected Output:**
```text
   ▲ Next.js 16.4.3
   - Local:        http://localhost:3000
   - Network:      http://192.168.x.x:3000

 ✓ Starting...
 ✓ Ready in 1200ms
```

---

## 9. Running via Docker Compose (Single Command Mode)

To run the entire system in production-equivalent containers:

```bash
# Directory: Repository Root
docker compose up -d --build
```

**Containers Launched:**
- `sentrix-backend`: Listens on `http://localhost:8000`
- `sentrix-frontend`: Listens on `http://localhost:3000`

To launch the optional standalone AWS Kinesis streaming worker:
```bash
docker compose --profile aws-worker up -d
```

To stop containers:
```bash
docker compose down
```

---

## 10. Application URLs & Documentation

| Service / View | URL | Purpose |
| :--- | :--- | :--- |
| **SOC Web Dashboard** | [http://localhost:3000](http://localhost:3000) | Main operator console |
| **Live Traffic Stream** | [http://localhost:3000/traffic](http://localhost:3000/traffic) | Real-time incoming request table with pagination |
| **Attack Detection Center** | [http://localhost:3000/detection](http://localhost:3000/detection) | Statistical Z-score velocity & explainable AI |
| **Machine Learning Hub** | [http://localhost:3000/models](http://localhost:3000/models) | Model health, schemas, metrics & interactive test |
| **Attack Protection** | [http://localhost:3000/protection](http://localhost:3000/protection) | Defensive firewall rules, staging & WAF export |
| **Cyber Range Simulator** | [http://localhost:3000/simulator](http://localhost:3000/simulator) | Synthetic chaos scenarios, M/M/1 queuing curves |
| **AWS Integrations** | [http://localhost:3000/integrations](http://localhost:3000/integrations) | Amazon Kinesis stream status & mock test replay |
| **System Health & Audit** | [http://localhost:3000/health](http://localhost:3000/health) | Service health & immutable audit log (CSV export) |
| **Interactive Swagger Docs**| [http://localhost:8000/docs](http://localhost:8000/docs) | OpenAPI interactive explorer |
| **ReDoc Specification** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Alternative formatted API specification |

---

## 11. Generating & Injecting Test Traffic

SENTRIX includes built-in test traffic generators to verify live detection.

### Method 1: Interactive Browser Injection
1. Navigate to [http://localhost:3000/integrations](http://localhost:3000/integrations).
2. Click **"Send Test Telemetry Batch"**.
3. Navigate to [http://localhost:3000/traffic](http://localhost:3000/traffic) to observe incoming requests populate the table in real-time.

### Method 2: Python Traffic Injection Script
Execute the bundled traffic simulation script:

```bash
# Directory: Repository Root (with .venv active)
python scripts/send_test_traffic.py --target http://127.0.0.1:8000 --rps 50 --duration 10
```

### Method 3: Ingesting Raw Access Logs via cURL
Send sample Nginx Combined access logs directly to the telemetry ingress endpoint:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/telemetry/ingress \
  -H "Content-Type: application/json" \
  -d '{
    "raw_logs": [
      "198.51.100.25 - - [30/Oct/2026:10:00:00 +0000] \"GET /login HTTP/1.1\" 401 512 \"-\" \"Mozilla/5.0\"",
      "198.51.100.25 - - [30/Oct/2026:10:00:01 +0000] \"GET /login HTTP/1.1\" 401 512 \"-\" \"Mozilla/5.0\"",
      "198.51.100.25 - - [30/Oct/2026:10:00:02 +0000] \"GET /login HTTP/1.1\" 401 512 \"-\" \"Mozilla/5.0\""
    ]
  }'
```

---

## 12. Running Automated Tests

Run the complete backend automated test suite (184 tests):

```bash
# Directory: Repository Root (with .venv active)
pytest backend/tests -v
```

### Run Specific Test Modules:
```bash
# Run AWS CloudFront & Kinesis integration tests:
pytest backend/tests/integration/test_aws_cloudfront_kinesis.py -v

# Run Cyber Range simulation and M/M/1 queuing tests:
pytest backend/tests/integration/test_tc08_simulation_safety.py -v

# Run API contract tests:
pytest backend/tests/api/test_api_contracts.py -v
```

### Run Code Formatting & Lint Checks:
```bash
# Format check:
python -m ruff format --check backend

# Linter check:
python -m ruff check backend
```

---

## 13. Stopping Services

- **Local Development (Terminal):** Press `Ctrl + C` in both the backend and frontend terminal windows.
- **Docker Compose:** Run `docker compose down` in the repository root.

---

## 14. Common Errors and Solutions

### 1. `ValidationException: Value 'mock-seq-...' at 'startingSequenceNumber' failed to satisfy constraint`
- **Cause:** A mock sequence number generated during local testing was stored in `kinesis_checkpoints` and passed to AWS GetShardIterator API.
- **Solution:** The codebase now contains a strict numeric regex guard and automatically purges non-numeric checkpoints. To manually wipe:
  ```powershell
  python -c "import sqlite3; con = sqlite3.connect('sentrix.db'); con.execute('DELETE FROM kinesis_checkpoints'); con.commit()"
  ```

### 2. `Address already in use: Port 8000 or 3000`
- **Cause:** A previous instance of Uvicorn or Node.js is still running in the background.
- **Solution:**
  - **Windows:** Run `Get-Process python, node | Stop-Process` in PowerShell.
  - **Linux/macOS:** Run `kill -9 $(lsof -t -i:8000) $(lsof -t -i:3000)`.

### 3. `401 Unauthorized: Authentication required`
- **Cause:** `API_AUTH_REQUIRED=true` is set in `.env`, but no Bearer token was provided in the HTTP request.
- **Solution:** Either provide `-H "Authorization: Bearer <TOKEN>"` in your request, or set `API_AUTH_REQUIRED=false` in `.env` for local testing.

### 4. `psycopg2 / DLL load failed` on Windows
- **Cause:** Windows AppLocker or missing PostgreSQL C-runtime libraries.
- **Solution:** SENTRIX automatically falls back to pure-Python `pg8000` driver if `psycopg2` cannot load. You can also use SQLite for local development (`DATABASE_URL=sqlite:///./sentrix.db`).

### 5. `Cannot list Kinesis shards: AWS credentials missing`
- **Cause:** `AWS_KINESIS_CONSUMER_ENABLED=true` is enabled, but AWS credentials are not configured.
- **Solution:** Set `AWS_KINESIS_CONSUMER_ENABLED=false` in `.env` if you do not have an active AWS Kinesis stream running. Local mock testing can still be executed via `/api/v1/integrations/aws/kinesis/mock-ingest`.

