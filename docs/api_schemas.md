# SENTRIX REST API Specification (v1.5.0)

The SENTRIX API provides a secure, token-authenticated DevSecOps control plane for real-time traffic monitoring, machine learning threat detection, automated mitigation lifecycle management, and discrete-event chaos simulations.

- **Base URL Prefix:** `/api/v1` (with `/internal` for platform keepalive)
- **Authentication Scheme:** HTTP Bearer Token (`Authorization: Bearer <API_AUTH_TOKEN>`)
- **Query Parameter Auth:** Supported for browser-initiated export streams (`?token=<API_AUTH_TOKEN>`)
- **Telemetry Format:** Strict JSON (`application/json`) with optional CSV format for audit trails (`format=csv`)
- **Timestamp Standard:** Strict UTC ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`)

---

## 1. Global Conventions & Error Envelopes

Every API response includes an immutable tracing identifier header:
```http
X-Request-ID: req_9f8c3d1b7a2e4f50
```

### Standard Error Envelope

All 4xx client and 5xx server responses adhere to a sanitized envelope without leaking internal stack traces:

```json
{
  "error": {
    "code": "SAFETY_GATE_REJECTED",
    "message": "Target IP 127.0.0.1 is protected by safety allowlist.",
    "request_id": "req_9f8c3d1b7a2e4f50"
  }
}
```

| HTTP Status | Error Code (`code`) | Trigger Condition |
| :---: | :--- | :--- |
| `400` | `INVALID_REQUEST` / `SAFETY_GATE_REJECTED` | Parameter bounds breach, protected allowlist target, or invalid state machine input. |
| `401` | `UNAUTHORIZED` | Missing, malformed, or invalid `Authorization: Bearer` token. |
| `403` | `FORBIDDEN` | Caller lacks permissions to toggle safety parameters. |
| `404` | `NOT_FOUND` | Specified simulation run, mitigation action, or alert resource does not exist. |
| `409` | `CONFLICT` | Invalid lifecycle transition (e.g. attempting to reset an actively running simulation). |
| `422` | `VALIDATION_ERROR` | Pydantic schema validation failure (e.g. non-numeric rates, missing required keys). |
| `500` | `INTERNAL_ERROR` | Unexpected backend runtime fault (sanitized for operator safety). |
| `503` | `SERVICE_UNAVAILABLE` | Database connectivity failure during keepalive ping. |

---

## 2. Master Endpoint Directory (24 Endpoints)

| # | HTTP Method | Path | Subsystem | Description |
| :-: | :--- | :--- | :--- | :--- |
| **1** | `GET` | `/health` | System | Healthcheck & runtime operational check. |
| **2** | `GET` | `/internal/keepalive` | System | Anti-pausing database connectivity ping (`SELECT 1`). |
| **3** | `GET` | `/models` | AI & Detection | List registered classifiers and runtime approved model. |
| **4** | `GET` | `/models/metrics` | AI & Detection | Retrieve verified model benchmark metrics (`rf-1.0.0` vs `iforest-1.0.0`). |
| **5** | `POST` | `/detection/analyze` | AI & Detection | Execute ad-hoc ML flow feature vector inference. |
| **6** | `POST` | `/traffic/flows` | Traffic | Ingest 1-second flow window records into the detection pipeline. |
| **7** | `GET` | `/traffic/summary` | Traffic | Fetch rolling 1-second and 10-second traffic PPS/BPS statistics. |
| **8** | `GET` | `/alerts` | Alerts | Paginated alert feed with severity filters (`low`, `medium`, `high`, `critical`). |
| **9** | `GET` | `/mitigations/status` | Mitigation | Real-time defense shield status, countdown timer, dynamic host IP, and DNS gateways. |
| **10** | `GET` | `/mitigations` | Mitigation | List active and historical mitigation actions with status filtering. |
| **11** | `POST` | `/mitigations/simulate` | Mitigation | Rapid manual operator defense shield activation. |
| **12** | `POST` | `/mitigations/{action_id}/cancel` | Mitigation | Early cancellation of an active mitigation rule. |
| **13** | `POST` | `/mitigations/disable` | Mitigation | Emergency kill switch to disengage or lock down all future mitigations. |
| **14** | `POST` | `/simulations` | Simulator | Initialize a new discrete-event chaos simulation run. |
| **15** | `GET` | `/simulations` | Simulator | List historical simulation sessions with pagination. |
| **16** | `GET` | `/simulations/compare` | Simulator | Side-by-side comparative analysis of 2 to 5 simulation runs. |
| **17** | `GET` | `/simulations/{run_id}` | Simulator | Fetch comprehensive simulation session state and final scorecard. |
| **18** | `POST` | `/simulations/{run_id}/control` | Simulator | Lifecycle controls: `start`, `pause`, `resume`, `step`, `cancel`, `reset`. |
| **19** | `GET` | `/simulations/{run_id}/ticks` | Simulator | Fetch chronological time-series ticks for live chart rendering. |
| **20** | `GET` | `/simulations/{run_id}/export` | Simulator | Export simulation run data as downloadable CSV or JSON. |
| **21** | `GET` | `/config/thresholds` | Config | Retrieve active versioned volumetric and ML sensitivity thresholds. |
| **22** | `PATCH` | `/config/thresholds` | Config | Incrementally calibrate specific threshold limits. |
| **23** | `PUT` | `/config/thresholds` | Config | Fully replace and activate a new semantic threshold version. |
| **24** | `GET` | `/audit` | Audit | Query immutable cryptographic audit trail (`json` or `csv`). |

---

## 3. Subsystem Specifications & Payloads

### 3.1 System & Health

#### `GET /health`
Returns minimal authenticated operational health status.
- **Auth:** Optional / Bearer Token.
- **Response (`200 OK`):**
```json
{
  "status": "ok"
}
```

#### `GET /internal/keepalive`
Lightweight query ensuring cloud databases (e.g. Supabase poolers) remain active.
- **Auth:** Bearer Token (`KEEPALIVE_SECRET` or `API_AUTH_TOKEN`).
- **Response (`200 OK`):**
```json
{
  "status": "ok",
  "database": "connected",
  "timestamp": "2026-10-27T19:35:00.123456Z"
}
```

---

### 3.2 AI Models & Threat Detection

#### `GET /models`
Lists all candidate and active classifiers registered in the system.
- **Response (`200 OK`):**
```json
{
  "approved_model": "rf-1.0.0",
  "schema_version": "1.0.0",
  "models": [
    {
      "model_version": "rf-1.0.0",
      "model_type": "RandomForestClassifier",
      "status": "approved",
      "schema_version": "1.0.0"
    },
    {
      "model_version": "iforest-1.0.0",
      "model_type": "IsolationForest",
      "status": "experimental_unapproved",
      "schema_version": "1.0.0"
    }
  ]
}
```

#### `GET /models/metrics`
Retrieves verified statistical test metrics from `models/rf-1.0.0/metrics.json` and `models/iforest-1.0.0/metrics.json`.
- **Response (`200 OK`):**
```json
{
  "dataset": "CIC-DDoS2019",
  "schema_version": "1.0.0",
  "rf_metrics": {
    "accuracy": 0.999775,
    "precision": 0.999949,
    "recall": 0.999823,
    "f1": 0.999886,
    "false_positive_rate": 0.005763,
    "p95_latency_ms": 6.564,
    "training_time_seconds": 2.808
  },
  "iforest_metrics": {
    "accuracy": 0.9943,
    "precision": 0.995351,
    "recall": 0.998915,
    "f1": 0.99713,
    "false_positive_rate": 0.533141,
    "p95_latency_ms": 4.811,
    "training_time_seconds": 0.088
  }
}
```

#### `POST /detection/analyze`
Executes an on-demand inference pass against a 14-dimensional flow feature vector.
- **Request Body:**
```json
{
  "features": {
    "Total Length of Fwd Packets": 150000.0,
    "Bwd Packet Length Max": 0.0,
    "Flow Bytes/s": 15000000.0,
    "Fwd IAT Total": 1000.0,
    "Bwd IAT Total": 0.0,
    "Fwd PSH Flags": 0.0,
    "Fwd Packets/s": 12000.0,
    "FIN Flag Count": 0.0,
    "Fwd Avg Bytes/Bulk": 0.0,
    "Bwd Avg Bulk Rate": 0.0,
    "Subflow Fwd Packets": 12000.0,
    "Init_Win_bytes_forward": 1024.0,
    "Active Mean": 0.0,
    "Idle Mean": 0.0
  },
  "target_ip": "192.168.1.100"
}
```
- **Response (`200 OK`):**
```json
{
  "event_id": "det_manual_01",
  "prediction": "suspicious",
  "score": 0.985,
  "score_type": "probability",
  "model_version": "rf-1.0.0",
  "feature_schema_version": "1.0.0",
  "policy_action": "request_mitigation",
  "policy_reasons": ["ML prediction is suspicious", "Flow rate exceeds 5,000 PPS"],
  "traffic_threshold_exceeded": true,
  "mitigation_mode": "simulation",
  "timestamp": "2026-10-27T19:35:00Z"
}
```

---

### 3.3 Mitigation & Defense Shield

#### `GET /mitigations/status`
Real-time shield telemetry polled by the frontend AppShell navigation bar and dashboards.
- **Response (`200 OK`):**
```json
{
  "emergency_disabled": false,
  "mode": "simulation",
  "shield_active": true,
  "active_simulated_count": 1,
  "max_concurrent_limit": 100,
  "status": "operational",
  "latest_mitigation": {
    "action_id": "sim_shield_4f98c5d2f1ab",
    "target_ip": "192.168.1.100",
    "target_port": 80,
    "rate_limit_pps": 5000,
    "duration_seconds": 60,
    "remaining_seconds": 38,
    "status": "active",
    "expires_at": null
  },
  "host_ip": "192.168.1.105",
  "hostname": "sentrix-node-01",
  "is_deployed": false,
  "environment": "local",
  "dns_gateways": ["8.8.8.8", "1.1.1.1"],
  "protected_gateways": ["192.168.1.1", "10.0.0.1"],
  "rate_limit_bounds": { "min_pps": 100, "max_pps": 50000 },
  "duration_bounds": { "min_seconds": 10, "max_seconds": 300 },
  "cooldown_ticks": 10
}
```

#### `POST /mitigations/simulate`
Manually initiates an isolated virtual rate-limiting rule.
- **Request Body:**
```json
{
  "target_ip": "192.168.1.100",
  "target_port": 80,
  "action_type": "rate_limit",
  "rate_limit_pps": 5000,
  "duration_seconds": 60,
  "reason": "Operator rapid defense activation from Overview dashboard"
}
```
- **Response (`201 Created`):**
```json
{
  "action_id": "act_8f7b2a1c0d",
  "target_ip": "192.168.1.100",
  "target_port": 80,
  "action_type": "rate_limit",
  "rate_limit_pps": 5000,
  "duration_seconds": 60,
  "status": "simulated",
  "mode": "simulation",
  "created_at": "2026-10-27T19:35:00Z",
  "expires_at": "2026-10-27T19:36:00Z"
}
```

#### `POST /mitigations/{action_id}/cancel`
Cancels an active mitigation rule before its natural expiration.
- **Response (`200 OK`):**
```json
{
  "action_id": "act_8f7b2a1c0d",
  "status": "cancelled",
  "cancelled_at": "2026-10-27T19:35:20Z"
}
```

#### `POST /mitigations/disable`
Toggles the global emergency kill switch.
- **Query Parameter:** `enable=true` (re-enable normal operation) or omit (engage lockdown).
- **Response (`200 OK`):**
```json
{
  "emergency_disabled": true,
  "status": "locked_down",
  "message": "All mitigation requests blocked globally."
}
```

---

### 3.4 Chaos Simulator Engine

#### `POST /simulations`
Initializes a new reproducible discrete-event simulation run.
- **Request Body:**
```json
{
  "scenario_type": "syn_flood",
  "seed": 42,
  "duration_seconds": 60,
  "baseline_pps": 250.0,
  "attack_peak_pps": 10000.0,
  "attack_start_tick": 9,
  "attack_end_tick": 51,
  "speed_multiplier": 1.0,
  "target_ip": "192.168.1.100",
  "target_port": 80,
  "victim": {
    "bandwidth_mbps": 100.0,
    "cpu_capacity_pps": 5000.0,
    "max_active_connections": 10000,
    "max_latency_ms": 5000.0,
    "baseline_latency_ms": 15.0
  }
}
```
- **Response (`201 Created`):**
```json
{
  "run_id": "sim_4f98c5d2f1ab",
  "scenario_type": "syn_flood",
  "status": "created",
  "seed": 42,
  "total_ticks": 60,
  "current_tick": 0,
  "speed_multiplier": 1.0,
  "config": { ... },
  "scorecard": null,
  "created_at": "2026-10-27T19:30:00Z",
  "updated_at": "2026-10-27T19:30:00Z",
  "completed_at": null
}
```

#### `POST /simulations/{run_id}/control`
Dispatches lifecycle control commands to the simulation run.
- **Request Body:**
```json
{
  "action": "step"
}
```
*(Valid actions: `start`, `pause`, `resume`, `step`, `cancel`, `reset`)*
- **Response (`200 OK`):**
```json
{
  "run_id": "sim_4f98c5d2f1ab",
  "status": "running",
  "current_tick": 1,
  "message": "Advanced virtual clock to tick 1."
}
```

#### `GET /simulations/{run_id}/ticks`
Fetches chronological time-series points recorded during the simulation.
- **Query Parameter:** `limit=150`
- **Response (`200 OK`):**
```json
{
  "run_id": "sim_4f98c5d2f1ab",
  "total_ticks": 60,
  "ticks": [
    {
      "tick": 9,
      "offered_legit_pps": 250.0,
      "offered_attack_pps": 9500.0,
      "served_legit_pps": 245.0,
      "dropped_legit_pps": 5.0,
      "dropped_attack_pps": 9025.0,
      "latency_ms": 17.5,
      "availability_pct": 98.0,
      "prediction": "suspicious",
      "policy_action": "request_mitigation",
      "active_mitigations_count": 1,
      "timestamp": "2026-10-27T19:30:09Z"
    }
  ]
}
```

#### `GET /simulations/{run_id}`
Returns simulation run metadata and the final computed scorecard when completed.
- **Response (`200 OK`):**
```json
{
  "run_id": "sim_4f98c5d2f1ab",
  "scenario_type": "syn_flood",
  "status": "completed",
  "seed": 42,
  "total_ticks": 60,
  "current_tick": 60,
  "speed_multiplier": 1.0,
  "scorecard": {
    "time_to_detect_seconds": 0,
    "time_to_mitigate_seconds": 3,
    "attack_traffic_blocked_pct": 93.18,
    "collateral_legitimate_pct": 2.0,
    "downtime_seconds": 0,
    "average_availability_pct": 98.0,
    "average_latency_ms": 17.78,
    "max_latency_ms": 102.5,
    "total_ticks": 60,
    "attack_ticks": 43,
    "benign_ticks": 17,
    "true_positives": 43,
    "false_positives": 0,
    "true_negatives": 17,
    "false_negatives": 0,
    "precision": 1.0,
    "recall": 1.0,
    "false_positive_rate": 0.0,
    "total_offered_attack_packets": 369282.39,
    "total_blocked_attack_packets": 344096.93,
    "total_offered_legitimate_packets": 15009.36,
    "total_dropped_legitimate_packets": 300.82
  },
  "created_at": "2026-10-27T19:30:00Z",
  "completed_at": "2026-10-27T19:31:00Z"
}
```

#### `GET /simulations/compare`
Performs parameter, threshold, and metric comparison between runs.
- **Query Parameter:** `run_ids=sim_run_01,sim_run_02`
- **Response (`200 OK`):**
```json
{
  "runs": [ ... ],
  "comparison_matrix": {
    "attack_blocked_pct": { "sim_run_01": 93.18, "sim_run_02": 89.4 },
    "collateral_drop_pct": { "sim_run_01": 2.0, "sim_run_02": 4.1 },
    "time_to_detect_sec": { "sim_run_01": 0, "sim_run_02": 1 }
  }
}
```

---

### 3.5 Dynamic Configuration & Thresholds

#### `GET /config/thresholds`
Fetches the active threshold configuration governing the policy engine.
- **Response (`200 OK`):**
```json
{
  "id": 1,
  "version": "v1.0.0",
  "is_active": true,
  "pps_threshold": 5000.0,
  "bps_threshold": 10000000.0,
  "syn_pps_threshold": 500.0,
  "syn_ack_ratio_threshold": 5.0,
  "rf_probability_threshold": 0.75,
  "iforest_score_threshold": 0.2664,
  "updated_by": "system",
  "created_at": "2026-10-25T12:00:00Z"
}
```

#### `PATCH /config/thresholds`
Calibrates specific threshold values while preserving remaining limits.
- **Request Body:**
```json
{
  "pps_threshold": 7500.0,
  "rf_probability_threshold": 0.80
}
```
- **Response (`200 OK`):** Updated threshold model.

---

### 3.6 Audit Trail & Compliance

#### `GET /audit`
Queries the tamper-evident audit trail tracking every mitigation state transition, simulation completion, and operator action.
- **Query Parameters:** `limit=50`, `offset=0`, `event_type=mitigation_triggered`, `format=json|csv`
- **Response (`200 OK`):**
```json
{
  "total_count": 142,
  "limit": 50,
  "offset": 0,
  "events": [
    {
      "event_id": "aud_7a9c3d1b8f",
      "event_type": "mitigation_triggered",
      "action": "simulate_rate_limit",
      "actor": "hybrid_policy",
      "details": {
        "action_id": "sim-act-9-b4f1",
        "target_ip": "192.168.1.100",
        "rate_limit_pps": 5000
      },
      "timestamp": "2026-10-27T19:30:09Z"
    }
  ]
}
```
*(When `format=csv`, returns downloadable `text/csv` with `Content-Disposition: attachment; filename=audit_export.csv`)*
