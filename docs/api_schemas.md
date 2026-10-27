# SENTRIX API Schemas (v1.0.0)

Base path: `/api/v1`. Total endpoints: 16.

## 1. Basics

- **Auth:** `Authorization: Bearer <API_AUTH_TOKEN>`
- **Request ID:** Every response has `X-Request-ID` (`req_<hex>`).
- **Content type:** JSON by default. CSV only for `/audit?format=csv`.
- **Time format:** ISO 8601 UTC, e.g. `2026-10-25T10:30:00Z`.

**Error format (all 4xx/5xx):**

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "Request validation failed.", "request_id": "req_84f937d2a" } }
```

| Status | Code |
| :-: | :-- |
| 400 | `INVALID_REQUEST` / `SAFETY_GATE_REJECTED` |
| 401 | `UNAUTHORIZED` |
| 403 | `FORBIDDEN` |
| 404 | `NOT_FOUND` |
| 409 | `CONFLICT` (bad state change) |
| 413 | `REQUEST_TOO_LARGE` |
| 422 | `VALIDATION_ERROR` |
| 429 | `RATE_LIMITED` |
| 500 | `INTERNAL_ERROR` |

## 2. Endpoint List

| # | Method | Endpoint | What it does |
| :-: | :-- | :-- | :-- |
| 1 | GET | `/health` | Health check (auth optional) |
| 2 | GET | `/models` | List models and approved model |
| 3 | GET | `/models/metrics` | Model accuracy and other metrics |
| 4 | POST | `/traffic/flows` | Send flow data into the pipeline |
| 5 | GET | `/traffic/summary` | Live traffic rates |
| 6 | POST | `/detection/analyze` | Run one-off detection |
| 7 | GET | `/alerts` | List alerts (filters, pages) |
| 8 | GET | `/mitigations` | List mitigation actions |
| 9 | POST | `/mitigations/simulate` | Run a simulated rate limit |
| 10 | POST | `/mitigations/{action_id}/cancel` | Cancel a mitigation |
| 11 | POST | `/mitigations/disable` | Emergency stop for all mitigations |
| 12 | POST | `/mitigations/disable?enable=true` | Turn emergency stop off |
| 13 | GET | `/config/thresholds` | Get current thresholds |
| 14 | PATCH | `/config/thresholds` | Change some thresholds |
| 15 | PUT | `/config/thresholds` | Replace thresholds (idempotent) |
| 16 | GET | `/audit` | Audit log (`json` or `csv`) |

All endpoints need auth except `/health` (optional).

## 3. Endpoint Details

### Health

`GET /health` → `200`

```json
{ "status": "ok" }
```

### Models

`GET /models` → `200`

```json
{
  "approved_model": "rf-1.0.0",
  "schema_version": "1.0.0",
  "models": [
    { "model_version": "rf-1.0.0", "model_type": "RandomForestClassifier", "status": "approved", "schema_version": "1.0.0" },
    { "model_version": "iforest-1.0.0", "model_type": "IsolationForest", "status": "experimental_unapproved", "schema_version": "1.0.0" }
  ]
}
```

`GET /models/metrics` → `200`

```json
{
  "dataset": "CIC-DDoS2019",
  "schema_version": "1.0.0",
  "rf_metrics": { "accuracy": 0.9995, "precision": 0.9998, "recall": 0.9996, "f1": 0.9997, "false_positive_rate": 0.0173, "p95_latency_ms": 4.45 },
  "iforest_metrics": { "accuracy": 0.9943, "precision": 0.9952, "recall": 0.9990, "f1": 0.9971, "false_positive_rate": 0.5476, "p95_latency_ms": 5.00 }
}
```

### Traffic

`POST /traffic/flows`

Demo flows must have a source tag:

- `demo-generator:<scenario>:<id>` for generated data
- `demo-replay:<filename>:<row_id>` for CSV replay

Request:

```json
{
  "source_id": "sensor-01",
  "timestamp": "2026-10-25T10:30:00Z",
  "window_seconds": 10.0,
  "feature_schema_version": "1.0.0",
  "features": {
    "Total Length of Fwd Packets": 2944.0,
    "Bwd Packet Length Max": 0.0,
    "Flow Bytes/s": 294400.0,
    "Fwd IAT Total": 1.0,
    "Bwd IAT Total": 0.0,
    "Fwd PSH Flags": 0,
    "Fwd Packets/s": 2000.0,
    "FIN Flag Count": 0,
    "Fwd Avg Bytes/Bulk": 0,
    "Bwd Avg Bulk Rate": 0,
    "Subflow Fwd Packets": 2,
    "Init_Win_bytes_forward": -1,
    "Active Mean": 0.0,
    "Idle Mean": 0.0
  },
  "target_ip": "192.168.1.100"
}
```

Response `201`:

```json
{ "status": "processed", "event_id": "evt_73a9f02b1", "policy_decision": "simulate_rate_limit", "alert_id": "alt_84b721e90", "mitigation_action_id": "act_91c432a10" }
```

`GET /traffic/summary` → `200`

```json
{
  "window_duration_seconds": 10.0, "observation_count": 45,
  "packet_rate": 450.0, "byte_rate": 182000.0,
  "syn_rate": 12.0, "syn_ack_ratio": 1.1,
  "unique_sources": 8, "is_burst": false
}
```

### Detection

`POST /detection/analyze`

Request: `{ "feature_schema_version": "1.0.0", "features": { ... } }` (same features as above)

Response `200`:

```json
{
  "event_id": "evt_42b89f10a",
  "model_version": "rf-1.0.0",
  "feature_schema_version": "1.0.0",
  "prediction": "suspicious",
  "score_type": "random_forest_probability",
  "score": 0.94,
  "traffic_threshold_exceeded": true,
  "policy_decision": "request_mitigation",
  "mitigation_mode": "simulation",
  "timestamp": "2026-10-25T10:30:00Z"
}
```

### Alerts

`GET /alerts?severity=critical&status=active&limit=50&offset=0` → `200`

```json
{
  "total_count": 1, "limit": 50, "offset": 0,
  "alerts": [{
    "alert_id": "alt_84b721e90", "detection_id": 14, "severity": "critical",
    "title": "DDoS Attack Pattern Detected",
    "description": "Both ML and traffic thresholds exceeded",
    "source_id": "sensor-01", "timestamp": "2026-10-25T10:30:00Z", "status": "active"
  }]
}
```

### Mitigations

`POST /mitigations/simulate`

Request:

```json
{ "target_ip": "10.0.0.99", "target_port": 80, "rate_limit_pps": 1000, "duration_seconds": 60 }
```

Response `201`:

```json
{
  "action_id": "act_827b10fa", "target_ip": "10.0.0.99",
  "rate_limit_pps": 1000, "duration_seconds": 60,
  "mode": "simulation", "host_networking_modified": false,
  "status": "simulated", "applied_at": "2026-10-25T10:30:00Z"
}
```

`POST /mitigations/{action_id}/cancel` → `200`

```json
{
  "action_id": "act_827b10fa", "target_ip": "10.0.0.99",
  "mode": "simulation", "host_networking_modified": false,
  "status": "cancelled", "cancelled_at": "2026-10-25T10:31:00Z"
}
```

`POST /mitigations/disable`

- Query: `enable` (optional, boolean, default `false`). Use `true` to turn the emergency stop off.

Stop all (default) → `200`:

```json
{ "emergency_disabled": true, "cancelled_actions_count": 3, "status": "All mitigation actions have been halted." }
```

Re-enable (`enable=true`) → `200`:

```json
{ "emergency_disabled": false, "cancelled_actions_count": 0, "status": "Emergency disable cleared. Mitigation requests allowed." }
```

### Thresholds

`GET /config/thresholds` → `200`

```json
{
  "version": "v1.0.0", "is_active": true,
  "pps_threshold": 5000.0, "bps_threshold": 10000000.0,
  "syn_pps_threshold": 500.0, "syn_ack_ratio_threshold": 5.0,
  "rf_probability_threshold": 0.75, "iforest_score_threshold": 0.2664,
  "updated_by": "system", "created_at": "2026-10-25T10:00:00Z"
}
```

`PATCH /config/thresholds` (send only fields to change)

```json
{ "pps_threshold": 8000.0, "rf_probability_threshold": 0.80 }
```

Response `200`: full threshold object with new version (e.g. `v1.0.1`) and `updated_by: "operator_api"`.

`PUT /config/thresholds`: same body as PATCH. Returns the updated threshold object (`200`).

### Audit

`GET /audit`

- `format`: `json` (default) or `csv`
- `event_type` (optional): `alert_created`, `mitigation_simulated`, `mitigation_cancelled`, `emergency_disable_activated`, `emergency_disable_cleared`, `threshold_config_updated`, `pipeline_failure`
- `limit`: 1–500 (default 50)
- `offset`: 0 or more (default 0)

JSON response `200`:

```json
{
  "total_count": 42, "limit": 50, "offset": 0,
  "events": [{
    "event_id": "aud_7c2b04f1", "event_type": "mitigation_simulated",
    "action": "simulate_rate_limit", "actor": "operator_api",
    "details": { "action_id": "act_827b10fa", "target_ip": "10.0.0.99", "rate_limit_pps": 1000, "duration_seconds": 60, "mode": "simulation", "host_networking_modified": false },
    "timestamp": "2026-10-26T12:00:00Z"
  }]
}
```

CSV response `200` (`Content-Type: text/csv`):

```csv
event_id,event_type,action,actor,timestamp,details
aud_7c2b04f1,mitigation_simulated,simulate_rate_limit,operator_api,2026-10-26T12:00:00Z,"{""action_id"":""act_827b10fa"",""target_ip"":""10.0.0.99""}"
```

### Simulations (DDoS Simulator v1.5.0)

#### 1. Create Simulation Run
`POST /api/v1/simulations`

Request body:
```json
{
  "scenario_type": "syn_flood",
  "seed": 42,
  "duration_seconds": 60,
  "baseline_pps": 200.0,
  "attack_peak_pps": 10000.0,
  "attack_start_tick": 10,
  "attack_end_tick": 50,
  "victim": {
    "bandwidth_mbps": 100.0,
    "cpu_capacity_pps": 5000.0,
    "max_active_connections": 10000,
    "baseline_latency_ms": 15.0
  },
  "speed_multiplier": 1.0
}
```

Response `201 Created`:
```json
{
  "run_id": "sim_7c4b01da89e2",
  "scenario_type": "syn_flood",
  "status": "created",
  "seed": 42,
  "total_ticks": 60,
  "current_tick": 0,
  "speed_multiplier": 1.0,
  "created_at": "2026-10-27T08:00:00Z"
}
```

#### 2. List Simulation Runs
`GET /api/v1/simulations?status=running&limit=20&offset=0`

Response `200 OK`:
```json
{
  "total_count": 5,
  "limit": 20,
  "offset": 0,
  "runs": [
    {
      "run_id": "sim_7c4b01da89e2",
      "scenario_type": "syn_flood",
      "status": "running",
      "seed": 42,
      "total_ticks": 60,
      "current_tick": 24,
      "speed_multiplier": 1.0,
      "created_at": "2026-10-27T08:00:00Z",
      "updated_at": "2026-10-27T08:00:24Z"
    }
  ]
}
```

#### 3. Get Simulation Run Detail & Scorecard
`GET /api/v1/simulations/{run_id}`

Response `200 OK`:
```json
{
  "run_id": "sim_7c4b01da89e2",
  "scenario_type": "syn_flood",
  "status": "completed",
  "seed": 42,
  "total_ticks": 60,
  "current_tick": 61,
  "speed_multiplier": 1.0,
  "config": { ... },
  "scorecard": {
    "time_to_detect_seconds": 2.0,
    "time_to_mitigate_seconds": 3.0,
    "attack_traffic_blocked_pct": 94.2,
    "collateral_legitimate_pct": 2.1,
    "downtime_seconds": 4,
    "average_availability_pct": 96.5,
    "precision": 0.95,
    "recall": 0.98,
    "false_positive_rate": 0.02
  },
  "created_at": "2026-10-27T08:00:00Z",
  "completed_at": "2026-10-27T08:01:00Z"
}
```

#### 4. Control Simulation Run
`POST /api/v1/simulations/{run_id}/control`

Request body:
```json
{
  "action": "start"
}
```
*Allowed actions:* `"start"`, `"pause"`, `"resume"`, `"step"`, `"cancel"`, `"reset"`.

Response `200 OK`:
```json
{
  "run_id": "sim_7c4b01da89e2",
  "status": "running",
  "current_tick": 24,
  "message": "Simulation run transitioned to running"
}
```

#### 5. List Simulation Ticks
`GET /api/v1/simulations/{run_id}/ticks?limit=100&offset=0`

Response `200 OK`:
```json
{
  "run_id": "sim_7c4b01da89e2",
  "ticks": [
    {
      "tick": 10,
      "offered_legit_pps": 204.1,
      "offered_attack_pps": 8420.0,
      "served_legit_pps": 199.8,
      "dropped_legit_pps": 4.3,
      "dropped_attack_pps": 7999.0,
      "latency_ms": 16.2,
      "availability_pct": 97.9,
      "prediction": "suspicious",
      "policy_action": "request_mitigation"
    }
  ]
}
```

#### 6. Compare Simulation Runs
`POST /api/v1/simulations/compare`

Request body:
```json
{
  "run_ids": ["sim_1", "sim_2"]
}
```

Response `200 OK`: Returns side-by-side run configurations, scorecards, and synthetic disclaimer.

#### 7. Export Simulation Run Report
`GET /api/v1/simulations/{run_id}/export?format=json` or `?format=markdown`

Response `200 OK`: Full run audit report with prominent educational disclaimer.