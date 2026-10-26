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

## 2. API Endpoint Directory

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `GET` | `/api/v1/health` | Service health check | Optional/Configurable |
| `GET` | `/api/v1/models` | List available models & active approved model | Yes |
| `GET` | `/api/v1/models/metrics` | Model evaluation benchmarks & dataset metrics | Yes |
| `POST` | `/api/v1/traffic/flows` | Ingest flow observations through pipeline | Yes |
| `GET` | `/api/v1/traffic/summary` | Live sliding-window traffic rates and statistics | Yes |
| `POST` | `/api/v1/detection/analyze` | Direct ML inference & hybrid policy check | Yes |
| `GET` | `/api/v1/alerts` | Paginated & filtered alert event log | Yes |
| `GET` | `/api/v1/mitigations` | Paginated & filtered mitigation actions | Yes |
| `POST` | `/api/v1/mitigations/simulate` | Evaluate safety gate & record simulation rule | Yes |
| `POST` | `/api/v1/mitigations/{id}/cancel` | Cancel an active/simulated mitigation action | Yes |
| `POST` | `/api/v1/mitigations/disable` | Emergency disable switch (halts all actions) | Yes |
| `GET` | `/api/v1/audit` | Query immutable audit log (JSON / CSV) | Yes |
| `GET` | `/api/v1/config/thresholds` | Retrieve active traffic thresholds | Yes |
| `PATCH` | `/api/v1/config/thresholds` | Update operational thresholds | Yes |

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
  * **Response (200 OK)**:
    ```json
    {
      "emergency_disabled": true,
      "cancelled_actions_count": 3,
      "status": "All mitigation actions have been halted."
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
      "pps_threshold": 8000.0
    }
    ```

* **`GET /api/v1/audit?format=json&limit=50&offset=0`**
  * Returns list of structured audit events with `event_id`, `event_type`, `action`, `actor`, `details`, and `timestamp`. Supports `format=csv`.
