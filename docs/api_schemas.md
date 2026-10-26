# SENTRIX API Schemas Specification

This specification documents the 14 REST API endpoint contracts for SENTRIX v1.0.0 under the `/api/v1` prefix.

## 1. Authentication & Common Headers

* **Authentication Scheme**: HTTP Bearer Token (`Authorization: Bearer <API_AUTH_TOKEN>`).
* **Request Tracing**: All requests receive a unique `X-Request-ID` header (format: `req_<hex>`).
* **Content Types**: `application/json` (default), `text/csv` (for `/api/v1/audit?format=csv`).
* **Timestamps**: All timestamps use ISO 8601 UTC format (e.g. `2026-10-25T10:30:00Z`).

### Error Response Envelope

All error responses (4xx and 5xx) strictly follow the structured error envelope:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "request_id": "req_84f937d2a"
  }
}
```

Standard Error Codes:
- `400`: `INVALID_REQUEST` / `SAFETY_GATE_REJECTED`
- `401`: `UNAUTHORIZED`
- `403`: `FORBIDDEN`
- `404`: `NOT_FOUND`
- `409`: `CONFLICT` (e.g., illegal state machine transition)
- `413`: `REQUEST_TOO_LARGE`
- `422`: `VALIDATION_ERROR` (e.g., schema mismatch or non-finite numbers)
- `429`: `RATE_LIMITED`
- `500`: `INTERNAL_ERROR`

---

## 2. API Endpoint Directory (All 16 APIs)

| # | Method | Endpoint | Description | Auth Required |
| :-: | :--- | :--- | :--- | :---: |
| 1 | `GET` | `/api/v1/health` | Service health check & simulation mode confirmation | Optional/Configurable |
| 2 | `GET` | `/api/v1/models` | List candidate models and active approved model | Yes |
| 3 | `GET` | `/api/v1/models/metrics` | Model evaluation benchmarks, confusion matrices & metrics | Yes |
| 4 | `POST` | `/api/v1/traffic/flows` | Ingest flow observations through full runtime pipeline | Yes |
| 5 | `GET` | `/api/v1/traffic/summary` | Live sliding-window traffic rates, PPS/BPS, burst metrics | Yes |
| 6 | `POST` | `/api/v1/detection/analyze` | Direct ad-hoc ML inference & hybrid policy evaluation | Yes |
| 7 | `GET` | `/api/v1/alerts` | Paginated and filtered alert event log | Yes |
| 8 | `GET` | `/api/v1/mitigations` | Paginated and filtered mitigation lifecycle actions | Yes |
| 9 | `POST` | `/api/v1/mitigations/simulate` | Evaluate safety gate & execute simulation rate limit | Yes |
| 10 | `POST` | `/api/v1/mitigations/{action_id}/cancel` | Request cancellation of an active or simulated mitigation | Yes |
| 11 | `POST` | `/api/v1/mitigations/disable` | Emergency disable switch (halts all active mitigations) | Yes |
| 12 | `POST` | `/api/v1/mitigations/disable?enable=true` | Clear emergency disable switch & restore safety gate | Yes |
| 13 | `GET` | `/api/v1/config/thresholds` | Retrieve active versioned traffic thresholds | Yes |
| 14 | `PATCH` | `/api/v1/config/thresholds` | Partially update operational threshold parameters | Yes |
| 15 | `PUT` | `/api/v1/config/thresholds` | Idempotently update or replace threshold parameters | Yes |
| 16 | `GET` | `/api/v1/audit` | Query immutable audit log stream (`format=json` or `format=csv`) | Yes |

---

## 3. Detailed Endpoint Contracts

### 3.1 Health
* **`GET /api/v1/health`**
  * **Response (200 OK)**:
    ```json
    { "status": "ok" }
    ```

### 3.2 Models Metadata & Metrics
* **`GET /api/v1/models`**
  * **Response (200 OK)**:
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

* **`GET /api/v1/models/metrics`**
  * **Response (200 OK)**:
    ```json
    {
      "dataset": "CIC-DDoS2019",
      "schema_version": "1.0.0",
      "rf_metrics": {
        "accuracy": 0.9995,
        "precision": 0.9998,
        "recall": 0.9996,
        "f1": 0.9997,
        "false_positive_rate": 0.0173,
        "p95_latency_ms": 4.45
      },
      "iforest_metrics": {
        "accuracy": 0.9943,
        "precision": 0.9952,
        "recall": 0.9990,
        "f1": 0.9971,
        "false_positive_rate": 0.5476,
        "p95_latency_ms": 5.00
      }
    }
    ```

### 3.3 Traffic Ingestion & Summary
* **`POST /api/v1/traffic/flows`**
  * **Demonstration Data Provenance**: In accordance with PRD Section 10.2 / TC-14, demonstration flows MUST carry explicit provenance prefixes:
    * `demo-generator:<scenario>:<id>` for synthetically generated flows.
    * `demo-replay:<filename>:<row_id>` for CSV-replayed dataset flows.
  * **Request Body (201 Created)**:
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
  * **Response (201 Created)**:
    ```json
    {
      "status": "processed",
      "event_id": "evt_73a9f02b1",
      "policy_decision": "simulate_rate_limit",
      "alert_id": "alt_84b721e90",
      "mitigation_action_id": "act_91c432a10"
    }
    ```

* **`GET /api/v1/traffic/summary`**
  * **Response (200 OK)**:
    ```json
    {
      "window_duration_seconds": 10.0,
      "observation_count": 45,
      "packet_rate": 450.0,
      "byte_rate": 182000.0,
      "syn_rate": 12.0,
      "syn_ack_ratio": 1.1,
      "unique_sources": 8,
      "is_burst": false
    }
    ```

### 3.4 Direct Detection Analysis
* **`POST /api/v1/detection/analyze`**
  * **Request Body**:
    ```json
    {
      "feature_schema_version": "1.0.0",
      "features": { ... }
    }
    ```
  * **Response (200 OK)**:
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

### 3.5 Alerts & Mitigations
* **`GET /api/v1/alerts?severity=critical&status=active&limit=50&offset=0`**
  * **Response (200 OK)**:
    ```json
    {
      "total_count": 1,
      "limit": 50,
      "offset": 0,
      "alerts": [
        {
          "alert_id": "alt_84b721e90",
          "detection_id": 14,
          "severity": "critical",
          "title": "DDoS Attack Pattern Detected",
          "description": "Dual-signal consensus: both ML threat and traffic thresholds exceeded",
          "source_id": "sensor-01",
          "timestamp": "2026-10-25T10:30:00Z",
          "status": "active"
        }
      ]
    }
    ```

* **`POST /api/v1/mitigations/simulate`**
  * **Request Body**:
    ```json
    {
      "target_ip": "10.0.0.99",
      "target_port": 80,
      "rate_limit_pps": 1000,
      "duration_seconds": 60
    }
    ```
  * **Response (201 Created)**:
    ```json
    {
      "action_id": "act_827b10fa",
      "target_ip": "10.0.0.99",
      "rate_limit_pps": 1000,
      "duration_seconds": 60,
      "mode": "simulation",
      "host_networking_modified": false,
      "status": "simulated",
      "applied_at": "2026-10-25T10:30:00Z"
    }
    ```

* **`POST /api/v1/mitigations/{id}/cancel`**
  * **Response (200 OK)**:
    ```json
    {
      "action_id": "act_827b10fa",
      "target_ip": "10.0.0.99",
      "mode": "simulation",
      "host_networking_modified": false,
      "status": "cancelled",
      "cancelled_at": "2026-10-25T10:31:00Z"
    }
    ```

* **`POST /api/v1/mitigations/disable`**
  * **Query Parameters**:
    * `enable` (*optional, boolean, default: `false`*): When `true`, deactivates the emergency disable switch and allows new mitigation simulations to resume.
  * **Response (200 OK — Deactivating)**:
    ```json
    {
      "emergency_disabled": true,
      "cancelled_actions_count": 3,
      "status": "All mitigation actions have been halted."
    }
    ```
  * **Response (200 OK — Re-enabling)**:
    ```json
    {
      "emergency_disabled": false,
      "cancelled_actions_count": 0,
      "status": "Emergency disable cleared. Mitigation requests allowed."
    }
    ```

### 3.6 Configuration & Audit
* **`GET /api/v1/config/thresholds`**
  * **Response (200 OK)**:
    ```json
    {
      "version": "v1.0.0",
      "is_active": true,
      "pps_threshold": 5000.0,
      "bps_threshold": 10000000.0,
      "syn_pps_threshold": 500.0,
      "syn_ack_ratio_threshold": 5.0,
      "rf_probability_threshold": 0.75,
      "iforest_score_threshold": 0.2664,
      "updated_by": "system",
      "created_at": "2026-10-25T10:00:00Z"
    }
    ```

* **`PATCH /api/v1/config/thresholds`**
  * **Request Body**:
    ```json
    {
      "pps_threshold": 8000.0,
      "rf_probability_threshold": 0.80
    }
    ```
  * **Response (200 OK)**:
    ```json
    {
      "version": "v1.0.1",
      "is_active": true,
      "pps_threshold": 8000.0,
      "bps_threshold": 10000000.0,
      "syn_pps_threshold": 500.0,
      "syn_ack_ratio_threshold": 5.0,
      "rf_probability_threshold": 0.80,
      "iforest_score_threshold": 0.2664,
      "updated_by": "operator_api",
      "created_at": "2026-10-26T12:00:00Z"
    }
    ```

* **`PUT /api/v1/config/thresholds`**
  * Idempotent endpoint for updating or replacing active threshold configuration parameters. Accepts the same payload schema as `PATCH`.
  * **Response (200 OK)**: Returns the updated `ThresholdConfigResponse` object.

* **`GET /api/v1/audit` (JSON & CSV)**
  * **Query Parameters**:
    * `format`: `"json"` (default) or `"csv"`.
    * `event_type` (*optional*): Filter by event type (`alert_created`, `mitigation_simulated`, `mitigation_cancelled`, `emergency_disable_activated`, `emergency_disable_cleared`, `threshold_config_updated`, `pipeline_failure`).
    * `limit`: Integer (`1` to `500`, default `50`).
    * `offset`: Integer (`ge=0`, default `0`).
  * **Response (200 OK — `format=json`)**:
    ```json
    {
      "total_count": 42,
      "limit": 50,
      "offset": 0,
      "events": [
        {
          "event_id": "aud_7c2b04f1",
          "event_type": "mitigation_simulated",
          "action": "simulate_rate_limit",
          "actor": "operator_api",
          "details": {
            "action_id": "act_827b10fa",
            "target_ip": "10.0.0.99",
            "rate_limit_pps": 1000,
            "duration_seconds": 60,
            "mode": "simulation",
            "host_networking_modified": false
          },
          "timestamp": "2026-10-26T12:00:00Z"
        }
      ]
    }
    ```
  * **Response (200 OK — `format=csv`)**:
    * `Content-Type`: `text/csv`
    * Content Body:
      ```csv
      event_id,event_type,action,actor,timestamp,details
      aud_7c2b04f1,mitigation_simulated,simulate_rate_limit,operator_api,2026-10-26T12:00:00Z,"{""action_id"":""act_827b10fa"",""target_ip"":""10.0.0.99""}"
      ```
