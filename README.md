# SENTRIX — Intelligent DDoS Detection, Monitoring & Defense Platform

> **Detect Threats in Seconds. Block Malicious Traffic. Keep Real Users Connected.**

SENTRIX is a DDoS detection prototype with HTTP telemetry ingestion (including AWS CloudFront Real-Time Logs via Amazon Kinesis Data Streams), adaptive statistical baselining (EWMA), threat classification, staged mitigation rules, and a discrete-event Cyber Range simulator. It does not capture packets from the host network or automatically modify production AWS WAF rules without operator authorization. Production use requires a trusted telemetry source, durable shared state, provider integration, and operational validation.

---

## 1. Core Architectural Pillars

1. **Real-Time Telemetry Streaming & Ingress:**
   - Ingests access logs (Nginx Combined, CLF, JSON) and live request telemetry via REST API (`POST /api/v1/telemetry/ingress`) or zero-overhead ASGI middleware.
   - Built-in GDPR privacy masking converts IPv4 addresses to `/24` subnets and IPv6 addresses to `/48` prefixes.
   - Thread-safe sliding-window circular buffer computes requests per second (RPS), byte throughput (Bps), P50/P90/P95/P99 latency percentiles via NumPy, and Shannon entropy $H(X)$ to quantify client IP dispersion.

2. **Multi-Tier Statistical Anomaly Detection & EWMA Baselines:**
   - Adaptive Exponentially Weighted Moving Average (EWMA) tracks running mean $\mu_t$ and moving variance $\sigma_t^2$ in $O(1)$ constant time.
   - Computes statistical velocity Z-scores ($Z_{rps}, Z_{err}, Z_{lat}, Z_{bps}$).
   - Explainable Threat Classifier detects Volumetric Floods, Slowloris, Credential Stuffing, and Botnets.
   - **Flash Crowd Differentiator (Zero Collateral Damage):** Surges with $Z_{rps} \ge 2.0$, high client entropy ($\eta \ge 0.75$), and low error rate ($< 10\%$) are classified as `FLASH_CROWD` and awarded action `ALLOW` without false-positive lockouts.

3. **Defensive Mitigation Engine & WAF Exporters:**
   - **Staged Dry-Run Default:** New rules default to `DRY_RUN` mode, permitting traffic while recording simulated drop counts to measure false positives.
   - **Operator Approval Promotion:** Rules can be staged and reviewed by an operator. The current in-process rate limiter is an application-level control, while edge enforcement is performed via exported AWS WAFv2 rulesets.
   - **WAF Configuration Exporters:** One-click generation of native **AWS WAFv2** (CloudFront Scope `us-east-1` IPSet JSON and deployment CLI script), **Nginx** (`deny <ip>;`, `limit_req_zone`), and **Caddy** (`@sentrix_blocked`) firewall configurations.
   - **Protected Allowlist:** Loopback (`127.0.0.1`), internal subnets (`10.0.0.0/8`, `192.168.0.0/16`), and healthcheck probes can never be mitigated.

4. **Dedicated Cyber Range & Chaos Lab (Isolated Sandbox):**
   - Retains a discrete-event chaos simulator modeling 6 traffic scenarios (SYN Flood, UDP Amplification, HTTP GET Flood, Slowloris, Mixed Multi-Vector, Flash Crowd) and server queuing theory (M/M/1 queue) without touching real infrastructure.

---

## 2. Unified 8-Section SOC Navigation Matrix

| Route | View Name | Description |
| :--- | :--- | :--- |
| **`/overview`** | **System Pulse** | High-level traffic graphs, availability, active alerts, and quick shield status. |
| **`/telemetry`** | **Live Telemetry Stream** | Sliding-window RPS, throughput, P50-P99 latencies, status distribution, and top clients. |
| **`/threats`** | **Threat Detection Center** | Statistical velocity Z-scores, explainable decision evidence, and one-click mitigation. |
| **`/alerts`** | **Threat Incidents** | Searchable persistent incident log connecting live telemetry alerts and history. |
| **`/mitigation`** | **Defense Shield** | Staged Dry-Run rules, operator approval/revocation, and AWS WAFv2/Nginx/Caddy export download. |
| **`/simulator`** | **Cyber Range & Chaos Lab** | Synthetic red-team attack scenarios, M/M/1 queuing simulation, and AI scorecards. |
| **`/history`** | **Security Audit Ledger** | Immutable regulatory audit log tracking rule promotions, alerts, and system actions. |
| **`/settings`** | **Policy Configuration** | Dynamic EWMA sensitivity thresholds, ML cutoff scores, and emergency kill-switch. |

---

## 3. Simulator Benchmark Results

The following figures describe synthetic simulator evidence only; they are not measurements of real network traffic or a production AWS CloudFront deployment:

| Key Performance Indicator | Measured Result | Significance |
| :--- | :---: | :--- |
| **AI Time to Detect (TTD)** | **< 1.0s (Instantaneous)** | Detected and classified attack on initial sliding-window tick. |
| **Time to Mitigate (TTM)** | **3.0 Seconds** | Dry-run rule staged and operator-promoted to active defense within 3s. |
| **Simulated Attack Traffic Dropped** | **> 93%** | Synthetic simulator benchmark only; not packets captured from a real network. |
| **Simulated Legitimate Traffic Served** | **98.0%** | Synthetic victim-model result; not a production availability guarantee. |
| **Simulated Flash-Crowd False Positive Rate** | **0.0%** | Synthetic scenario result; requires evaluation against real application traffic. |
| **Average Server Latency** | **17.78 ms** | Queue stabilized back to baseline normal after defense activation. |

---

## 4. Quickstart Guide

### Option A: Complete Platform via Docker Compose
```bash
# Start backend and frontend in containerized production mode
docker compose up -d --build
```
- **SOC Web Dashboard:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Control Plane & Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Endpoint:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Option B: Local Development

#### 1. Backend Service
```bash
# In repository root
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Dashboard
```bash
# In separate terminal
cd frontend
npm install
npm run dev
```

---

## 5. Technology Stack

- **Machine Learning & Baselines:** Scikit-learn (Random Forest ensemble trained on CIC-DDoS2019), NumPy, Adaptive EWMA Moving Variance Engine.
- **Backend Control Plane:** FastAPI, Pydantic v2, Python 3.11+, SQLAlchemy ORM, Uvicorn, SQLite / PostgreSQL.
- **Frontend Presentation:** Next.js 16 (App Router), React 19, Tailwind CSS, Recharts, Lucide Icons.
- **DevSecOps & Testing:** Pytest 9.2, FastAPI TestClient, Multi-Stage Dockerfiles (non-root `UID 10001`/`1001`), Docker Compose, GitHub Actions.

---

## 6. Project Documentation Index

- **[`RUN_GUIDE.md`](RUN_GUIDE.md):** Complete operator manual with PowerShell/curl scripts for demonstrating normal traffic, attacks, and Flash Crowds.
- **[`DEPLOYMENT.md`](DEPLOYMENT.md):** Production DevSecOps deployment runbook with reverse proxy, TLS, and container security.
- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md):** Detailed system architecture specification with Mermaid diagrams.
