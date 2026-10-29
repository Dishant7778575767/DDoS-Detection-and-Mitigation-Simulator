# SENTRIX — Operator & Developer Run Guide

Welcome to **SENTRIX**, an enterprise-grade real-time DDoS detection, monitoring, and defensive mitigation platform. This guide provides end-to-end instructions for launching the system, streaming telemetry, observing live threat detection, approving defensive rules, and exporting production firewall configurations.

---

## 1. Prerequisites

- **Python 3.11+**
- **Node.js 18+** & **npm**
- **Docker & Docker Compose** (Optional, for containerized deployment)
- **curl** or **PowerShell** (for traffic injection)

---

## 2. Quickstart via Docker Compose

The fastest way to launch the complete platform is using Docker Compose:

```bash
# From the repository root
docker compose up -d --build
```

- **Frontend SOC Dashboard:** [http://localhost:3000](http://localhost:3000)
- **Backend API & Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Endpoint:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

To view container logs:
```bash
docker compose logs -f
```

To stop:
```bash
docker compose down
```

---

## 3. Local Development Setup (Without Docker)

### Step 3.1: Start the Backend Service

1. Activate your Python virtual environment and navigate to `backend/`:
   ```bash
   # Windows PowerShell
   .\.venv\Scripts\Activate.ps1
   cd backend
   ```
   *(On Linux/macOS: `source .venv/bin/activate && cd backend`)*

2. Configure environment variables (a default `.env` is already provided):
   ```env
   API_AUTH_REQUIRED=false
   DATABASE_URL=sqlite:///./sentrix.db
   ENVIRONMENT=development
   ```

3. Launch the FastAPI server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. Verify backend health:
   ```bash
   curl http://localhost:8000/api/v1/health
   # Expected response: {"status":"healthy", ...}
   ```

---

### Step 3.2: Start the Next.js Frontend

1. Open a new terminal and navigate to `frontend/`:
   ```bash
   cd frontend
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Access the SOC Dashboard:
   Open [http://localhost:3000](http://localhost:3000) in your web browser.

---

## 4. End-to-End Operational Demonstration

SENTRIX provides 8 dedicated SOC views in the top navigation bar:
- `/overview`: High-level system pulse & active alert counters
- `/telemetry`: Live sliding-window HTTP telemetry stream
- `/threats`: Real-time Z-score anomaly velocity & explainable evidence
- `/alerts`: Persistent incident database & threat records
- `/mitigation`: Defensive shield, staged dry-run rules & WAF exporter
- `/simulator`: Isolated Cyber Range for synthetic chaos testing
- `/history`: Regulatory security audit ledger
- `/settings`: Policy matrices & baseline parameters

Follow the steps below to simulate real-world attack scenarios and observe defensive responses.

---

### Scenario A: Inject Normal Baseline Traffic

Inject a steady baseline of legitimate HTTP requests from diverse client IPs:

```powershell
# PowerShell script to stream 50 normal requests
1..50 | ForEach-Object {
    $ip = "192.0.2.$($_ % 20 + 1)"
    $body = @{
        format = "raw_batch"
        items = @(
            @{
                client_ip = $ip
                method = "GET"
                path = "/api/v1/products"
                status_code = 200
                response_time_ms = (Get-Random -Minimum 15 -Maximum 45)
                bytes_sent = (Get-Random -Minimum 500 -Maximum 2500)
            }
        )
    } | ConvertTo-Json -Depth 5

    Invoke-RestMethod -Uri "http://localhost:8000/api/v1/telemetry/ingress" -Method Post -Body $body -ContentType "application/json"
    Start-Sleep -Milliseconds 100
}
```

**Observation:**
- Navigate to **[Live Telemetry](/telemetry)**. Notice steady requests/second, low p99 latency (~40ms), 100% 2xx status codes, and balanced Shannon entropy ($\eta \approx 0.90$).
- Navigate to **[Threat Center](/threats)**. The status banner displays **NORMAL TRAFFIC** with Z-scores within normal bounds ($\pm 1.0$).

---

### Scenario B: Inject Volumetric HTTP Flood (Attacker)

Simulate a high-rate volumetric attack originating from a concentrated attacker subnet:

```powershell
# Inject 200 rapid attack requests from a malicious source
1..200 | ForEach-Object {
    $body = @{
        format = "raw_batch"
        items = @(
            @{
                client_ip = "198.51.100.88"
                method = "POST"
                path = "/search"
                status_code = (Get-Random -InputObject @(500, 502, 503, 504))
                response_time_ms = (Get-Random -Minimum 1200 -Maximum 3500)
                bytes_sent = 120
            }
        )
    } | ConvertTo-Json -Depth 5

    Invoke-RestMethod -Uri "http://localhost:8000/api/v1/telemetry/ingress" -Method Post -Body $body -ContentType "application/json"
}
```

**Observation:**
- In **[Live Telemetry](/telemetry)**: Error rate jumps above $50\%$, latency p99 spikes to $>3000\text{ms}$, and Shannon entropy ratio collapses ($\eta < 0.20$).
- In **[Threat Center](/threats)**: The banner turns critical: **VOLUMETRIC HTTP FLOOD DETECTED**. Velocity grid shows $Z_{rps} \ge 3.5$ and $Z_{lat} \ge 3.0$.
- In **[Threat Incidents](/alerts)**: A permanent incident record is created with severity `CRITICAL` and root-cause evidence.

---

### Scenario C: Propose & Approve Defensive Rule

1. Navigate to **[Defense Shield](/mitigation)**.
2. In the **Propose Defensive Rule** dialog:
   - Target: `198.51.100.88`
   - Action: `BLOCK`
   - TTL: `300` seconds
   - Reason: `Volumetric flood observed`
   - Click **Propose Rule**.
3. Notice the rule is created in **`DRY_RUN`** mode!
   - In dry-run mode, SENTRIX monitors traffic without dropping legitimate connections. The `Simulated Blocks` counter increments.
4. Click the green **Approve** button next to the rule.
   - The mode changes to **`ACTIVE`**.
   - Active blocking is now enforced by SENTRIX's leaky-bucket engine.
5. Click **Export Nginx Conf** or **Export Caddyfile** to download the production firewall rules!

Example Nginx output:
```nginx
# SENTRIX Auto-Generated Defensive Rules
# Generated at: 2026-10-28T...
# Active Rules: 1

# --- ACTIVE IP BLOCKS ---
deny 198.51.100.88;
```

6. Navigate to **[Audit Ledger](/history)**:
   - See the immutable audit trail entries recording the proposal and analyst approval.

---

### Scenario D: The Flash Crowd Differentiator (Zero Collateral Damage)

Simulate a sudden marketing promotion surge where hundreds of genuine users visit your application:

```powershell
# Flash crowd: high RPS, but high entropy (diverse IPs) and low error rate
1..100 | ForEach-Object {
    $body = @{
        format = "raw_batch"
        items = @(
            @{
                client_ip = "203.0.113.$($_)"
                method = "GET"
                path = "/special-deal"
                status_code = 200
                response_time_ms = 25
                bytes_sent = 4500
            }
        )
    } | ConvertTo-Json -Depth 5

    Invoke-RestMethod -Uri "http://localhost:8000/api/v1/telemetry/ingress" -Method Post -Body $body -ContentType "application/json"
}
```

**Observation:**
- Navigate to **[Threat Center](/threats)**.
- SENTRIX evaluates the velocity spike ($Z_{rps} \ge 2.5$), but detects that entropy is high ($\eta \ge 0.85$) and error rate is under $5\%$.
- The system classifies the event as **`FLASH_CROWD`** with recommendation **`ALLOW`**.
- **No blocking rules are proposed, preventing false-positive lockouts for legitimate customers!**

---

## 5. Running the Automated Test Suite

### Running Backend Unit & Integration Tests:
```bash
# In repository root
.\.venv\Scripts\pytest backend/tests/unit backend/tests/integration backend/tests/api -v
```

### Running Frontend Typecheck & Linting:
```bash
# Strict TypeScript compilation check (0 errors expected)
node frontend/node_modules/typescript/bin/tsc --project frontend/tsconfig.json --noEmit

# ESLint check (0 warnings expected)
node frontend/node_modules/eslint/bin/eslint.js frontend/src
```

---

## 6. Architecture & Codebase Map

| Component | Key Source File | Description |
| :--- | :--- | :--- |
| **Telemetry Ingestion** | [`backend/app/ingestion/telemetry_schemas.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/ingestion/telemetry_schemas.py) | Pydantic v2 telemetry contracts & models |
| **Log Parser & Privacy** | [`backend/app/ingestion/log_parser.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/ingestion/log_parser.py) | Nginx/CLF/JSON log parsing & IPv4/IPv6 masking |
| **Sliding Aggregator** | [`backend/app/features/telemetry_aggregator.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/features/telemetry_aggregator.py) | Circular buffer, latency percentiles & Shannon entropy |
| **Adaptive Baselines** | [`backend/app/detection/baselines.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/detection/baselines.py) | EWMA running mean, moving variance & Z-score velocity |
| **Threat Classifier** | [`backend/app/detection/threat_classifier.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/detection/threat_classifier.py) | Multi-tier attack detection & Flash Crowd differentiator |
| **Defensive Engine** | [`backend/app/mitigation/defensive_engine.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/mitigation/defensive_engine.py) | Staged Dry-Run, LeakyBucket rate limiter & allowlists |
| **WAF Exporter** | [`backend/app/mitigation/config_exporter.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/mitigation/config_exporter.py) | Nginx, Caddy, and Cloudflare config generation |
| **SOC Navigation** | [`frontend/src/config/navigation.ts`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/src/config/navigation.ts) | 8 unified routes and analyst workspace mapping |
| **Live Telemetry UI** | [`frontend/src/app/telemetry/page.tsx`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/src/app/telemetry/page.tsx) | Live telemetry graphs, latency cards, and entropy gauges |
| **Threat Center UI** | [`frontend/src/app/threats/page.tsx`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/src/app/threats/page.tsx) | Anomaly velocity analysis, evidence table & rule actions |

---

## 7. Troubleshooting & FAQ

### Q: Why do rules start in `DRY_RUN` mode?
**A:** Dry-run staging is an enterprise safety best practice. It permits traffic while incrementing simulated hit counters so operators can verify that rules only target attackers, preventing collateral damage to genuine users.

### Q: Can I run this with Docker on Windows?
**A:** Yes. Run `docker compose up --build` with Docker Desktop running. Both the Python FastAPI backend and Next.js frontend are containerized with multi-stage non-root profiles.

### Q: How do I connect my own web application?
**A:** Import `SentrixTelemetryMiddleware` from `backend/app/integrations/middleware.py` into your FastAPI/Starlette application, setting the `sentrix_url` pointing to your SENTRIX instance.

