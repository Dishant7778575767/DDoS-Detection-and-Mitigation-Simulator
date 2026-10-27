# SENTRIX Operations Guide

## 1. System Overview

SENTRIX is a defensive prototype that detects DDoS attacks and simulates how to stop them. It uses machine learning (ML) together with fixed traffic thresholds.

### Operational Philosophy

- **Simulation by default:** All rate limiting runs in `simulation` mode. SENTRIX **never changes** host firewall rules, kernel tables, or OS networking.
- **Fail-closed, dual-signal rule:** One signal (ML only or threshold only) creates an alert. **Both signals together** are needed to request a mitigation.
- **Strict authorization:** Control endpoints (thresholds, cancel, simulate, emergency disable) need a valid bearer token (`API_AUTH_TOKEN`).

---

## 2. Environment & Service Startup

### Configuration Setup

Set these in `.env` (or as environment variables):

```ini
APP_ENV=development
MITIGATION_MODE=simulation
MODEL_PATH=models/approved_model.joblib
DATABASE_URL=postgresql://postgres.<db_reference>:<db_password>@<region>.pooler.supabase.com:5432/postgres
API_AUTH_REQUIRED=true
API_AUTH_TOKEN=<random_generates_hashstring/string>
CORS_ORIGIN=frontend_deployed_url
```

### Starting the Backend

From the project root, using the virtual environment:

```powershell
# Activate environment
.venv\Scripts\Activate.ps1

# Start FastAPI server on port 8000
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Check that it is running:

```powershell
curl -H "Authorization: Bearer dev-only-change-me" http://127.0.0.1:8000/api/v1/health
```

### Starting the Web Dashboard

In a separate terminal:

```powershell
cd frontend
npm run dev
```

Open the dashboard at `http://localhost:3000`.

---

## 3. Demonstration & Traffic Generation

You can generate fake flows or replay labeled CSV data. Both go through the same pipeline (`POST /api/v1/traffic/flows`) and carry demo source tags.

### Bounded Traffic Generator (`send_test_traffic.py`)

Creates flows for the test scenarios in PRD Section 10.2:

```powershell
# One scenario (normal, burst, syn_flood, threshold_only, ml_only)
python scripts/send_test_traffic.py --scenario syn_flood --count 5 --target-ip 192.168.1.150

# All scenarios in order
python scripts/send_test_traffic.py --scenario all
```

*Tag used:* `source_id: demo-generator:<scenario>:<index>`

### Dataset Replay Tool (`replay_dataset.py`)

Replays saved flow rows from the processed CIC-DDoS2019 data:

```powershell
# Replay 20 rows with 0.2s delay between flows
python scripts/replay_dataset.py --file data/fixtures/sample_test.csv --limit 20 --delay 0.2
```

*Tag used:* `source_id: demo-replay:<file>:<row_id>`

---

## 4. Policy & Threshold Management

SENTRIX mixes traffic volume limits with the ML threat score.

### Active Threshold Configuration

View and change thresholds with `GET` and `PATCH /api/v1/config/thresholds`, or in the **Settings** page of the web UI:

- `pps_threshold`: forward packets per second limit (default 5,000)
- `bps_threshold`: flow byte rate limit (default 10,000,000 bytes/s)
- `syn_pps_threshold`: SYN packet rate limit (default 500)
- `syn_ack_ratio_threshold`: SYN to ACK ratio limit (default 5.0)
- `rf_probability_threshold`: Random Forest attack cutoff (default 0.75)
- `iforest_score_threshold`: Isolation Forest anomaly cutoff (default 0.2664)

### The Dual-Signal Decision Matrix

| ML Signal | Traffic Threshold | Decision | What happens |
| :---: | :---: | :---: | :-- |
| **Normal** (< 0.75) | **Within limits** | `monitor` | Normal. Data is saved in the sliding window. |
| **Normal** (< 0.75) | **Exceeded** | `alert` | Alert only. Mitigation is **held back**. |
| **Suspicious** (≥ 0.75) | **Within limits** | `alert` | Alert only. Mitigation is **held back**. |
| **Suspicious** (≥ 0.75) | **Exceeded** | `request_mitigation` | Can go to the Safety Gate for bounded rate limiting. |

---

## 5. Mitigation Lifecycle & Safety Controls

### Safety Gate Rules

Before any mitigation is simulated, the Safety Gate checks:

1. **Protected targets:** Requests for loopback (`127.0.0.1`, `::1`), DNS servers (`8.8.8.8`, `1.1.1.1`), or gateways (`192.168.1.1`, `10.0.0.1`) are rejected right away.
2. **Limits:** Rate limit must be 100 to 50,000 pps. Duration must be 10 to 300 seconds.
3. **Concurrency cap:** At most 100 active mitigations.
4. **Flapping cooldown:** Alerts for the same target IP wait 30 seconds.

### Emergency Disable Switch

Stops all running mitigations and blocks new ones:

```powershell
# Turn Emergency Disable ON
curl -X POST -H "Authorization: Bearer dev-only-change-me" http://127.0.0.1:8000/api/v1/mitigations/disable

# Turn it OFF and resume normal operation
curl -X POST -H "Authorization: Bearer dev-only-change-me" "http://127.0.0.1:8000/api/v1/mitigations/disable?enable=true"
```

*You can also toggle it from the Mitigation Control Room in the UI.*

### Manual Mitigation Cancellation

Cancel any active simulated mitigation using its action ID:

```powershell
curl -X POST -H "Authorization: Bearer dev-only-change-me" http://127.0.0.1:8000/api/v1/mitigations/<ACTION_ID>/cancel
```

---

## 6. Audit Trail & Verification

Every operation, security decision, and state change is logged in the `audit_events` table.

- **View logs:** `GET /api/v1/audit?limit=50&offset=0`
- **Export CSV:** `GET /api/v1/audit?format=csv`, or click **Export CSV** in the History view.
- **Integrity:** Audit records are append-only. The API cannot edit or delete them.

---

## 7. Simulation Safety & Mitigation Operations

SENTRIX operates strictly as a synthetic, defensive DDoS simulator.

- **Pure Simulation Boundary:** All mitigation actions are executed in simulation mode only. SENTRIX makes zero host networking, firewall, or operating system changes.
- **Fail-Closed Safety Gate:** Even in simulation mode, the Safety Gate validates all IP addresses against a protected infrastructure allowlist (loopback, gateway, public DNS) and enforces strict rate limits (100–50,000 pps) and durations (10–300 seconds).
- **Emergency Disable:** In the event of anomalous behavior, the Emergency Disable switch halts all active and simulated mitigations immediately and prevents new actions from being accepted.
- **Audit Logging:** Every state transition (proposal, simulation, expiration, cancellation, and emergency disable) is immutably recorded in the audit ledger.