# SENTRIX Production Deployment & DevSecOps Guide

This guide describes how to deploy the **SENTRIX DDoS Detection, Monitoring & Mitigation Platform** in production, staging, or authorized security evaluation environments.

---

## 1. Architecture Overview

SENTRIX operates as an autonomous web defense appliance:
- **Frontend:** Next.js 16 standalone web application (Port 3000) providing the SOC Command Center, Live Telemetry Stream, Threat Center, and isolated Cyber Range simulator.
- **Backend:** FastAPI high-performance asynchronous API (Port 8000) providing:
  - Real-time HTTP log & request ingestion pipeline (`/api/v1/telemetry/ingress`)
  - Adaptive EWMA baseline & Z-score velocity detection (`/api/v1/detection/live`)
  - Random Forest ML classifier (CIC-DDoS2019 dataset)
  - Defensive Rate-Limiting & Reverse-Proxy Configuration Exporter (`/api/v1/mitigations/export/nginx`)
  - Isolated discrete-event chaos simulator (`/api/v1/simulations`)

---

## 2. Quickstart with Docker Compose (Recommended)

### Prerequisites:
- Docker Engine $\ge 24.0$
- Docker Compose $\ge 2.20$

### Step 1: Clone & Configure Environment
```bash
git clone https://github.com/your-org/DDoS-Detection-and-Mitigation-Simulator.git
cd DDoS-Detection-and-Mitigation-Simulator

# Copy environment template
cp .env.example .env

# Generate a strong 32-character authentication token
openssl rand -hex 16
# Edit .env and paste token into API_AUTH_TOKEN
```

### Step 2: Build & Start Containers
```bash
docker compose up -d --build
```

### Step 3: Verify Health Checks
```bash
# Check container status
docker compose ps

# Backend health probe
curl -f http://localhost:8000/api/v1/health

# Access Web Dashboard:
# http://localhost:3000
```

---

## 3. Integrating Live Web Application Telemetry

To protect your web applications, choose either **Log Streaming** or **In-App Middleware**.

### Option A: Reverse-Proxy Log Ingestion (Nginx / Apache / Caddy)
Configure your reverse proxy to emit JSON or Combined access logs to SENTRIX via curl/promtail/fluent-bit:

```bash
curl -X POST http://localhost:8000/api/v1/telemetry/ingress \
  -H "Authorization: Bearer <API_AUTH_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_logs": [
      "198.51.100.22 - - [28/Oct/2026:20:00:00 +0000] \"GET /api/v1/checkout HTTP/1.1\" 200 1450 \"-\" \"Mozilla/5.0\" 0.045"
    ],
    "anonymize_ips": true,
    "source_identifier": "edge-proxy-01"
  }'
```

### Option B: FastAPI / Starlette In-App Middleware
If your web application is built on FastAPI or Starlette, drop in the SENTRIX telemetry middleware:

```python
from fastapi import FastAPI
from app.integrations.middleware import SentrixTelemetryMiddleware

app = FastAPI()

# Mount SENTRIX Telemetry Middleware
app.add_middleware(
    SentrixTelemetryMiddleware,
    sentrix_endpoint="http://localhost:8000/api/v1/telemetry/ingress",
    api_token="<API_AUTH_TOKEN>",
    batch_size=50,
    flush_interval_seconds=2.0,
    anonymize_ips=True,
)
```

---

## 4. Exporting & Applying Defensive Mitigations

When a threat (e.g. Volumetric HTTP Flood, Credential Stuffing, or Slowloris) is detected:
1. Navigate to **Threat Center** (`/threats`) and click **"Propose Staged Mitigation"** (creates rule in safe `DRY_RUN` mode).
2. Go to **Defense Shield** (`/mitigation`) to review simulated blocked requests vs legitimate traffic.
3. Once approved, click **"Export Nginx"** or **"Export Caddyfile"** to download the configuration snippet:
   ```bash
   # Download active Nginx blocklist directly:
   curl -H "Authorization: Bearer <API_AUTH_TOKEN>" \
        http://localhost:8000/api/v1/mitigations/export/nginx \
        -o /etc/nginx/conf.d/sentrix_defense.conf

   # Reload Nginx without downtime:
   nginx -t && nginx -s reload
   ```

---

## 5. Security & DevSecOps Hardening Checklist

- [x] **Non-Root Execution:** Docker containers run under dedicated unprivileged users (`sentrix:10001` and `nextjs:1001`).
- [x] **Subnet Privacy Masking:** Client IP addresses are masked to `/24` subnets (`198.51.100.0/24`) by default to protect user privacy.
- [x] **Protected Infrastructure Guard:** Loopback (`127.0.0.1`), DNS gateways (`8.8.8.8`, `1.1.1.1`), and internal routers can never be targeted for mitigation.
- [x] **Mandatory Rule Expiry (TTL):** Every defensive rule automatically expires after a configured TTL (e.g., 600s) to prevent permanent accidental lockouts.
- [x] **Emergency Kill-Switch:** Instant operator kill-switch halts all mitigations across the fleet in $< 1$ millisecond.
- [x] **Traceability:** Dynamic `X-Request-ID` is stamped on every incoming request and propagated to logs and audit trails.

