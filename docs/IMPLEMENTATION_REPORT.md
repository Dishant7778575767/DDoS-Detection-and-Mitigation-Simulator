# SENTRIX — Implementation Report & Architectural Evolution

**Project Name:** SENTRIX (Secure Enterprise Network Telemetry & Real-Time Incident X-Defend)  
**Version:** 2.0.0-RELEASE  
**Date:** October 2026  
**Status:** All 5 Transformation Milestones Implemented & Verified  

---

## 1. Executive Summary

SENTRIX has been transformed from an isolated discrete-event DDoS simulation tool into an **Enterprise-Grade Real-World DDoS Detection, Telemetry Ingress, and Defensive Mitigation Platform**. 

The evolution preserves the existing discrete-event Cyber Range lab and Random Forest flow-level classifier while introducing an autonomous, real-time HTTP telemetry ingestion pipeline, an adaptive statistical anomaly detection engine, an explainable threat classifier with Flash Crowd differentiation, a defensive mitigation engine featuring staged dry-run rules, and a unified 8-section SOC analyst dashboard.

---

## 2. Milestone 1: Real-Time Telemetry Pipeline & Privacy Ingress

### 2.1 Pydantic v2 Ingress Schemas
- **File:** [`backend/app/ingestion/telemetry_schemas.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/ingestion/telemetry_schemas.py)
- **Implemented Models:**
  - `RequestTelemetryItem`: Represents a single HTTP request telemetry sample including `client_ip`, `method`, `path`, `status_code`, `response_time_ms`, `bytes_sent`, `user_agent`, and `timestamp`.
  - `TelemetryIngressRequest`: Batch request wrapper accommodating up to 10,000 items per ingestion payload with format specification (`raw_batch`, `nginx_combined`, `clf`, `json`).
  - `LatencyPercentiles`: Computes $p_{50}$, $p_{90}$, and $p_{99}$ response times.
  - `StatusCodeDistribution`: Segregates counts and percentages of 2xx, 3xx, 4xx, and 5xx responses.
  - `ClientEntropyMetrics`: Carries Shannon entropy $H(X)$, maximum entropy $H_{max}$, and normalized entropy ratio $\eta$.
  - `TelemetrySummaryResponse`: Full sliding-window aggregation payload.

### 2.2 Robust Log Parser & GDPR/Privacy Masking
- **File:** [`backend/app/ingestion/log_parser.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/ingestion/log_parser.py)
- **Functions:**
  - `parse_nginx_combined_line()`: High-performance regular expression parser for standard Nginx Combined access logs, including optional upstream response time and request time fields.
  - `parse_clf_line()`: Common Log Format (CLF) parser.
  - `parse_json_log_line()`: Structured JSON access log parser with fallbacks.
  - `mask_ip_address()`: Network subnet privacy masker that converts IPv4 addresses to `/24` subnets (e.g., `192.168.1.45` $\rightarrow$ `192.168.1.0/24`) and IPv6 addresses to `/48` prefixes (e.g., `2001:db8:85a3:8d3:1319:8a2e:370:7348` $\rightarrow$ `2001:db8:85a3::/48`).

### 2.3 Circular Sliding-Window Telemetry Aggregator
- **File:** [`backend/app/features/telemetry_aggregator.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/features/telemetry_aggregator.py)
- **Features:**
  - Thread-safe deque-based circular buffer with `threading.Lock`.
  - Configurable rolling time window (default 60 seconds).
  - Out-of-window telemetry points automatically evicted upon ingestion.
  - High-precision percentiles computed using `numpy.percentile`.
  - Continuous Shannon Entropy computation:
    $$H(X) = -\sum_{i=1}^{n} P(x_i) \log_2 P(x_i)$$
    $$\text{Entropy Ratio } \eta = \frac{H(X)}{\log_2(n)}$$
    Where $n$ is the number of distinct client IP addresses.

### 2.4 Telemetry API Endpoints & ASGI Middleware
- **File:** [`backend/app/api/v1/telemetry.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/api/v1/telemetry.py)
  - `POST /api/v1/telemetry/ingress`: Ingests batched telemetry items or raw logs with auto-parsing. Synchronizes with both `telemetry_aggregator` and the NetFlow `window_aggregator`.
  - `GET /api/v1/telemetry/summary`: Returns current sliding-window metrics (RPS, throughput, latency percentiles, error rate, entropy).
  - `POST /api/v1/telemetry/reset`: Clears the telemetry circular buffer and resets counters.
- **File:** [`backend/app/integrations/middleware.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/integrations/middleware.py)
  - `SentrixTelemetryMiddleware`: Zero-overhead ASGI middleware for external web services to stream telemetry directly into SENTRIX.

---

## 3. Milestone 2: Multi-Tier Detection Engine & Anomaly Baselines

### 3.1 Adaptive EWMA Statistical Baseline Tracker
- **File:** [`backend/app/detection/baselines.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/detection/baselines.py)
- **Mathematical Model:**
  - Tracks running mean $\mu_t$ and running moving variance $\sigma_t^2$ using Exponentially Weighted Moving Average (EWMA):
    $$\mu_t = \alpha \cdot x_t + (1 - \alpha) \cdot \mu_{t-1}$$
    $$\sigma_t^2 = (1 - \alpha) \cdot (\sigma_{t-1}^2 + \alpha \cdot (x_t - \mu_{t-1})^2)$$
  - Calculates instantaneous statistical Z-scores:
    $$Z_t = \frac{x_t - \mu_t}{\max(\sigma_t, \epsilon)}$$
  - Evaluates velocity across 4 dimensions: $Z_{rps}$, $Z_{err}$ (4xx/5xx error rate), $Z_{lat}$ (p99 latency), and $Z_{bps}$ (byte throughput).
  - Configurable warm-up threshold (default 10 observations) ensures no false alarms during initial startup.

### 3.2 Explainable Threat Classifier with Flash Crowd Differentiator
- **File:** [`backend/app/detection/threat_classifier.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/detection/threat_classifier.py)
- **Classification Rules:**
  1. **Volumetric HTTP Flood:** High $Z_{rps} \ge 3.0$, low-to-medium entropy ($\eta \le 0.40$), and elevated error rate $\ge 15\%$. Confidence: $0.85$–$0.95$. Action: `BLOCK` or `RATE_LIMIT`.
  2. **Slowloris Attack:** Low $Z_{rps}$ but extreme latency $Z_{lat} \ge 3.0$, high connection hold times, low throughput. Confidence: $0.90$. Action: `TERMINATE_IDLE`.
  3. **Credential Stuffing:** High 4xx error rate $Z_{err} \ge 3.0$ focused on authentication/login URI patterns (`/login`, `/auth`, `/token`). Confidence: $0.88$. Action: `CAPTCHA` or `RATE_LIMIT`.
  4. **Distributed Botnet Flood:** High $Z_{rps}$, wide client distribution with moderate entropy ($0.40 < \eta < 0.70$), high error rate. Confidence: $0.85$. Action: `CHALLENGE_JS`.
  5. **Flash Crowd (CRITICAL DIFFERENTIATOR):**
     - Velocity: $Z_{rps} \ge 2.0$.
     - Entropy Ratio: $\eta \ge 0.75$ (high diversity across the IP space).
     - Distinct Clients: $\ge 5$.
     - Error Rate: $< 10\%$ (legitimate users receiving 200 OK responses).
     - **Decision:** Explicitly classified as `FLASH_CROWD`, confidence $0.90$, recommendation `ALLOW` (zero collateral damage).

### 3.3 Real-Time Threat Evaluation & Incident Persistence Loop
- **File:** [`backend/app/api/v1/detection.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/api/v1/detection.py)
  - `GET /api/v1/detection/live`: Pulls current telemetry sliding window, updates baseline, classifies threat pattern, and **commits alerts into SQLite/PostgreSQL `AlertModel` and `AuditEventModel`**.
  - `POST /api/v1/detection/evaluate-telemetry`: Ad-hoc evaluation of arbitrary telemetry summaries.
  - `GET /api/v1/detection/baseline` & `POST /api/v1/detection/baseline/reset`: Inspect and reset baseline states.

---

## 4. Milestone 3: Defensive Mitigation Engine & WAF Exporters

### 4.1 Staged Mitigation Engine & Leaky Bucket Rate Limiter
- **File:** [`backend/app/mitigation/defensive_engine.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/mitigation/defensive_engine.py)
- **Core Architecture:**
  - **Staged Dry-Run Default:** All new defensive rules are initially proposed with mode `DRY_RUN`. In dry-run mode, matching traffic is permitted while incrementing `simulated_blocked_count` to measure impact before active enforcement.
  - **Operator Approval Promotion:** SOC analysts explicitly review and promote rules to `ACTIVE` mode (`approve_rule()`).
  - **Leaky Bucket Algorithm:** Per-client bucket tracking with token replenishment rate $r$ and capacity $C$.
  - **Mandatory TTL Expiry:** All rules enforce a strict time-to-live (`ttl_seconds`, default 300s). Expired rules are auto-pruned, preventing permanent collateral lockouts.
  - **Protected Infrastructure Allowlist:** Guaranteed bypass for internal subnets (`127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`, healthcheck IPs). Any attempt to block protected targets raises a validation error.
  - **Emergency Kill-Switch Integration:** Global emergency stop instantly disables all active mitigations.

### 4.2 Production WAF Configuration Exporters
- **File:** [`backend/app/mitigation/config_exporter.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/mitigation/config_exporter.py)
- **Supported Formats:**
  - **Nginx:** Generates ready-to-include configuration blocks containing `deny <IP>;` directives and `limit_req_zone` rate-limiting maps.
  - **Caddy:** Generates Caddyfile snippets with `@sentrix_blocked` remote IP matchers and `respond @sentrix_blocked 429`.
  - **Cloudflare WAF:** Exports JSON-formatted custom expression lists for API-based rule deployment.

### 4.3 Mitigation API Endpoints with Audit Trail
- **File:** [`backend/app/api/v1/mitigations.py`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/app/api/v1/mitigations.py)
  - `POST /api/v1/mitigations/defensive/propose`: Proposes a block, rate limit, or challenge rule.
  - `GET /api/v1/mitigations/defensive/rules`: Lists active and staged rules.
  - `POST /api/v1/mitigations/defensive/{rule_id}/approve`: Promotes rule to `ACTIVE`. Automatically records audit event.
  - `POST /api/v1/mitigations/defensive/{rule_id}/revoke`: Immediately removes rule. Automatically records audit event.
  - `GET /api/v1/mitigations/export/nginx` & `GET /api/v1/mitigations/export/caddy`: Downloadable configuration text.

---

## 5. Milestone 4: Unified SOC Frontend Integration

### 5.1 Route Architecture & Navigation Matrix
- **File:** [`frontend/src/config/navigation.ts`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/src/config/navigation.ts)
- Defined 8 dedicated routes:
  1. `/overview` (Live System Overview & Traffic Pulse)
  2. `/telemetry` (Live HTTP Telemetry Stream & Metrics)
  3. `/threats` (Real-Time Threat Detection & Velocity Analysis)
  4. `/alerts` (Threat Incidents & Historical Event Log)
  5. `/mitigation` (Defense Shield & Active Mitigation Center)
  6. `/simulator` (Cyber Range & Chaos Lab — 100% Isolated)
  7. `/history` (Security Audit Ledger & Regulatory Log)
  8. `/settings` (Policy Configuration & System Tuning)

### 5.2 TypeScript Interfaces & Client API
- **File:** [`frontend/src/types/telemetry.ts`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/src/types/telemetry.ts)
  - Full TypeScript type contracts matching backend Pydantic models.
- **File:** [`frontend/src/lib/api.ts`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/src/lib/api.ts)
  - Added `fetchLiveTelemetry()`, `fetchLiveDetection()`, `fetchDefensiveRules()`, `proposeDefensiveRule()`, `approveDefensiveRule()`, `revokeDefensiveRule()`, `downloadNginxConfig()`, and `downloadCaddyConfig()`.

### 5.3 Operational SOC Pages
- **Live Telemetry Stream:** [`frontend/src/app/telemetry/page.tsx`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/src/app/telemetry/page.tsx)
  - Live metric cards (RPS, Bandwidth, 4xx/5xx Error Rates, Shannon Entropy).
  - Latency distribution gauges (p50, p90, p99).
  - Status code breakdown bar and top visited URIs with percentage visualization.
  - Automatic 3-second background polling with manual pause/resume controls.
- **Threat Detection Center:** [`frontend/src/app/threats/page.tsx`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/src/app/threats/page.tsx)
  - Threat status alert banner with severity-driven dynamic colorization.
  - Z-Score Velocity Analysis Matrix ($Z_{rps}, Z_{err}, Z_{lat}, Z_{bps}$).
  - Explainable Decision Evidence log detailing root-cause reasoning.
  - Flash Crowd indicator card confirming zero-collateral protection.
  - One-click "Stage Defensive Rule" drawer for instant response.
- **Defensive Rules Control Room:** [`frontend/src/components/mitigation/DefensiveRulesCard.tsx`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/src/components/mitigation/DefensiveRulesCard.tsx)
  - Rule management table displaying rule ID, target IP/CIDR, mode (`DRY_RUN` vs `ACTIVE`), action type, TTL remaining, and hit counts.
  - Interactive "Approve" button promoting staged dry-run rules to active enforcement.
  - Interactive "Revoke" button removing rules.
  - One-click config exporter buttons ("Export Nginx Conf", "Export Caddyfile").
- **Cyber Range & Chaos Lab Isolation:** [`frontend/src/app/simulator/page.tsx`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/src/app/simulator/page.tsx)
  - Rebranded and clearly separated as a synthetic chaos-testing sandbox.
  - Allows red-team operators to launch synthetic attack profiles (Slowloris, Volumetric UDP, SYN Flood) without interfering with real telemetry ingress.

---

## 6. Milestone 5: DevSecOps Containerization & Packaging

### 6.1 Multi-Stage Containerization
- **Backend Dockerfile:** [`backend/Dockerfile`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/backend/Dockerfile)
  - Build stage: Installs dependencies using clean virtual environment.
  - Runtime stage: `python:3.11-slim`, non-root user `sentrix` (UID `10001`), hardened file permissions, and active healthcheck probing `/api/v1/health`.
- **Frontend Dockerfile:** [`frontend/Dockerfile`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/frontend/Dockerfile)
  - Build stage: Compiles Next.js with standalone output configuration (`next.config.ts`).
  - Runtime stage: `node:20-alpine`, non-root user `nextjs` (UID `1001`), serving optimized production assets.
- **Orchestration:** [`docker-compose.yml`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/docker-compose.yml)
  - Orchestrates both services with environment parameterization, volume mounting for persistent SQLite database, network isolation, and automatic restart policies.
- **Deployment Manual:** [`DEPLOYMENT.md`](file:///d:/DDoS-Detection-and-Mitigation-Simulator/DEPLOYMENT.md)
  - Comprehensive operational runbook covering reverse proxy setup (Nginx / Cloudflare), TLS termination, environment variable secrets, and log rotation.

---

## 7. Verification & Compliance Matrix

| Milestone | Target Deliverable | Implementation Artifact | Status |
| :--- | :--- | :--- | :--- |
| **M1** | Schemas & Parsers | `backend/app/ingestion/telemetry_schemas.py`, `log_parser.py` | **100% COMPLETE** |
| **M1** | Sliding-Window Aggregator | `backend/app/features/telemetry_aggregator.py` | **100% COMPLETE** |
| **M1** | Telemetry Ingress API | `backend/app/api/v1/telemetry.py` | **100% COMPLETE** |
| **M1** | Client Middleware | `backend/app/integrations/middleware.py` | **100% COMPLETE** |
| **M2** | Adaptive EWMA Baselines | `backend/app/detection/baselines.py` | **100% COMPLETE** |
| **M2** | Threat Classifier & Flash Crowd | `backend/app/detection/threat_classifier.py` | **100% COMPLETE** |
| **M2** | Detection API & Persistence | `backend/app/api/v1/detection.py` | **100% COMPLETE** |
| **M3** | Defensive Mitigation Engine | `backend/app/mitigation/defensive_engine.py` | **100% COMPLETE** |
| **M3** | Nginx/Caddy Exporters | `backend/app/mitigation/config_exporter.py` | **100% COMPLETE** |
| **M3** | Defensive API & Audit Logging | `backend/app/api/v1/mitigations.py` | **100% COMPLETE** |
| **M4** | SOC Navigation & Routing | `frontend/src/config/navigation.ts` | **100% COMPLETE** |
| **M4** | Live Telemetry Page | `frontend/src/app/telemetry/page.tsx` | **100% COMPLETE** |
| **M4** | Threat Detection Center | `frontend/src/app/threats/page.tsx` | **100% COMPLETE** |
| **M4** | Defensive Rules Card & Room | `frontend/src/components/mitigation/DefensiveRulesCard.tsx` | **100% COMPLETE** |
| **M4** | Cyber Range Isolation | `frontend/src/app/simulator/page.tsx` | **100% COMPLETE** |
| **M5** | Multi-Stage Dockerfiles | `backend/Dockerfile`, `frontend/Dockerfile` | **100% COMPLETE** |
| **M5** | Production Compose Spec | `docker-compose.yml`, `DEPLOYMENT.md` | **100% COMPLETE** |

The codebase transformation is complete, fully integrated, and verified against all functional requirements.

