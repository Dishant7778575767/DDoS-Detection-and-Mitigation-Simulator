# Project Requirements Document (PRD)

## Machine Learning-Based DDoS Detection and Mitigation Platform

**Project name:** SENTRIX DDoS Defense Platform\
**Document version:** 1.1\
**Tagline:** Detect. Defend. Stay Resilient.\
**Status:** Implementation baseline\
**Date:** October 2026

**Version 1.1 changes:** Standardized the database name as `sentrix.db`,
made API authentication required by default with a local-development
token example, and added mitigation cancellation, emergency disable, and
audit retrieval endpoints.

---

## 1. Project Overview

### 1.1 Problem Statement

Distributed Denial-of-Service (DDoS) attacks can disrupt network
services by generating excessive traffic or connection requests. SYN
floods are one example: high volumes of TCP connection attempts can
consume connection-tracking or server resources. Static thresholds alone
can struggle with normal traffic fluctuations.

This project will build a lightweight machine-learning-based system that
analyzes network-flow features and short time-window statistics, detects
suspicious traffic patterns, displays results in a React dashboard, and
requests bounded rate-limiting actions through a policy engine.

### 1.2 Objectives

- Detect suspicious traffic bursts and SYN-flood-like patterns.
- Evaluate Random Forest and Isolation Forest as candidate models.
- Combine flow-level features with time-window aggregation.
- Display traffic metrics, alerts, model results, and mitigation
  status.
- Begin with simulation-only mitigation; add controlled Linux
  enforcement only after validation.
- Measure precision, recall, F1-score, false-positive rate, inference
  latency, and resource use.
- Provide auditable decisions, bounded actions, expiration, and
  recovery.

### 1.3 Intended Users

- Network and system administrators
- Cybersecurity students and researchers
- Security operations personnel
- Developers evaluating ML-based traffic monitoring

### 1.4 Technology Stack

- **Frontend:** Next.js
- **Backend API:** Python and FastAPI
- **ML:** scikit-learn
- **Initial persistence:** SQLite
- **Data:** Public labeled datasets and controlled lab traffic
- **Mitigation:** Simulation adapter first; restricted Linux adapter
  in an isolated lab later

---

## 2. Scope

### 2.1 In Scope

- Import and validate public labeled network-flow datasets.
- Clean records and create reproducible training, validation, and test
  splits.
- Extract flow-level and time-window traffic features.
- Train and compare Random Forest and Isolation Forest.
- Ingest validated traffic metrics from controlled test sources.
- Generate detections and alerts.
- Visualize live metrics and historical trends.
- Evaluate hybrid ML-and-threshold mitigation policies.
- Record simulated mitigation actions and audit history.
- Add restricted Linux rate-limiting integration in an isolated test
  environment after simulation passes.

### 2.2 Out of Scope for Initial Release

- Production-scale DDoS scrubbing across distributed networks.
- Guaranteed detection of every unknown attack.
- Autonomous modification of production firewall rules.
- Deep inspection of encrypted application payloads.
- Testing against public or third-party systems.
- Claims of real-time performance before measurement.

---

## 3. Functional Requirements

---

ID Requirement Priority

---

FR-01 Load supported public Must
datasets and validate  
 their schema.

FR-02 Use consistent, Must
versioned feature  
 definitions and  
 preprocessing during  
 training and inference.

FR-03 Train Random Forest and Must
Isolation Forest  
 candidate models.

FR-04 Evaluate precision, Must
recall, F1-score,  
 confusion matrix,  
 false-positive rate,  
 latency, and resource  
 use.

FR-05 Receive traffic metrics Must
through a validated API
or controlled  
 collector.

FR-06 Analyze observations Must
and return a prediction
or anomaly score with  
 model version and  
 timestamp.

FR-07 Generate alerts from Must
model evidence and  
 configured traffic  
 thresholds.

FR-08 Show traffic metrics, Must
alerts, detections, and
mitigation history in  
 React.

FR-09 Simulate mitigation Must
without modifying host  
 networking.

FR-10 Record each mitigation Must
decision, trigger,  
 target, duration, and  
 outcome.

FR-11 Support cooldowns, Must
expiration, manual  
 disable, and bounded  
 action limits.

FR-12 Apply rate limits in an Must for lab phase
isolated Linux lab  
 through a restricted  
 enforcement component.

FR-13 Verify temporary-rule Must for lab phase
expiration and cleanup,
and document recovery.

FR-14 Filter alerts and Should
history by time,  
 severity, and status.

FR-15 Track model versions, Must
feature schema  
 versions, and threshold
configuration.

---

---

## 4. Non-Functional Requirements

---

ID Requirement Initial target

---

NFR-01 Inference latency Target p95 below 100 ms
per observation in the
documented test
environment; measure
rather than assume.

NFR-02 Detection quality Initial goal of at
least 90% precision and
90% recall on a
held-out evaluation
set.

NFR-03 Reliability Invalid input must be
rejected safely without
crashing the service.

NFR-04 Security Validate inputs,
authenticate
administrative actions,
and avoid unrestricted
firewall privileges in
the API.

NFR-05 Safety Simulation mode must
not invoke firewall or
traffic-control
changes.

NFR-06 Auditability Log detections, policy
decisions, operator
actions, and
enforcement outcomes.

NFR-07 Maintainability Separate ingestion,
features, inference,
policy, enforcement,
and presentation
modules.

NFR-08 Usability Clearly distinguish
normal, suspicious,
simulated, and actually
enforced states.

NFR-09 Reproducibility Record dataset
versions, feature
configuration, model
version, thresholds,
and metrics.

NFR-10 Portability Document local
development and
repeatable deployment
to an isolated Linux
lab.

---

Targets are proposed acceptance goals and must be reviewed after
baseline evaluation. Accuracy alone is not sufficient for imbalanced
traffic data.

---

## 5. System Architecture

### 5.1 Logical Components

1.  **Traffic sources:** Public datasets for offline training and
    controlled lab traffic for integration testing.
2.  **Ingestion and feature pipeline:** Validates input, aggregates time
    windows, and computes consistent features.
3.  **ML detection engine:** Runs the selected model and produces
    predictions or anomaly scores.
4.  **Policy decision engine:** Combines ML evidence with traffic
    thresholds, cooldowns, allowlists, and action limits.
5.  **Safety gate:** Verifies authorization, target validity, action
    bounds, and current mode.
6.  **Mitigation adapters:** Simulation adapter by default; restricted
    Linux enforcement adapter only in the lab phase.
7.  **Persistence and audit:** Stores alerts, model versions,
    configuration, mitigation actions, and audit events.
8.  **FastAPI backend:** Exposes validated endpoints and dashboard data.
9.  **React dashboard:** Presents live monitoring, alerts, historical
    analytics, and authorized controls.

The initial implementation may be a single FastAPI application with
separated modules; each component does not need to run as an independent
service.

### 5.2 End-to-End Data Flow

1.  Load public datasets for offline model training; collect metrics
    from controlled lab traffic for integration tests.
2.  Validate records and calculate flow-level and time-window features.
3.  Run model inference and create a detection event.
4.  Evaluate the event against traffic thresholds and policy safeguards.
5.  Record a simulated action, or---only after approval and lab
    validation---request a permitted Linux rate limit.
6.  Store the event and update the dashboard through API polling
    initially; WebSockets may be added if justified.
7.  Expire temporary rules, verify cleanup, and record the final
    outcome.

### 5.3 Architecture Constraints

- Simulation-only mode is the default.
- The model must never execute shell commands or directly control
  firewall rules.
- The enforcement adapter must be isolated behind explicit
  authorization and least-privilege controls.
- Training and test data must be split to reduce leakage, preferably
  by capture, source, or time period.
- A prediction is evidence of suspicious behavior, not proof of
  malicious intent.

---

## 6. Machine Learning Pipeline

### 6.1 Dataset Strategy

- **Primary candidate:** CIC-DDoS2019 for labeled DDoS-related flow
  data.
- **Optional secondary dataset:** CIC-IDS2017 for broader intrusion
  and traffic patterns.
- **Integration validation:** Controlled benign and bounded
  attack-like traffic in an isolated lab.
- Confirm dataset license, provenance, feature availability, and label
  meanings before use.
- Keep lab validation separate from data used to tune model
  thresholds.

### 6.2 Feature Engineering

Initial candidate features include: - Packets per second and bytes per
second - Total packets and bytes per flow - SYN packet rate and
SYN-to-ACK ratio where available - New flows per second - Flow
duration - Unique source count per time window - Rate changes, rolling
averages, and burst statistics

Features must be available at inference time. Do not use target labels,
future observations, or post-event information. Training and inference
must use the same feature names, units, order, and preprocessing.

### 6.3 Candidate Models

**Random Forest** - Supervised model trained on labeled normal and
attack-related traffic. - Tune tree count, depth, and class weighting on
validation data. - Treat class probabilities as model outputs, not
guaranteed calibrated confidence.

**Isolation Forest** - Unsupervised anomaly-detection baseline,
preferably fitted on representative benign training data. - Tune its
decision threshold on a separate labeled validation set. - Treat anomaly
scores according to the documented score convention; do not equate them
directly with Random Forest probabilities.

### 6.4 Evaluation Method

- Use training, validation, and held-out test sets with leakage-aware
  splitting.
- Compare precision, recall, F1-score, confusion matrix,
  false-positive rate, inference latency, CPU, and memory.
- Inspect false positives and false negatives, especially for
  SYN-flood-like patterns.
- Test the chosen model against controlled lab traffic not used to
  tune it.
- If neither model meets the goals, improve data, features, or policy
  rather than enabling enforcement prematurely.

### 6.5 Initial Targets

- Precision: at least 90%
- Recall: at least 90%
- p95 inference latency: target below 100 ms per observation in the
  documented environment
- Report F1-score, false-positive rate, and resource usage
- Document model limitations and dataset-specific performance

### 6.6 ML Deliverables

- Reproducible dataset preparation pipeline
- Versioned feature definitions and preprocessing
- Random Forest and Isolation Forest artifacts
- Comparison report and confusion matrices
- Documented model selection and thresholds
- Versioned model interface for FastAPI integration

---

## 7. FastAPI Endpoint Contracts

All endpoints use the `/api/v1` prefix. Request bodies must be validated
using Pydantic. Timestamps use UTC ISO 8601. Administrative endpoints
require authentication and appropriate authorization.

---

Method Endpoint Purpose

---

GET `/api/v1/health` API and service health

GET `/api/v1/models` Model versions and
active model

GET `/api/v1/models/metrics` Evaluation metrics

POST `/api/v1/traffic/flows` Submit validated flow
observations

GET `/api/v1/traffic/summary` Traffic and time-window
summary

POST `/api/v1/detection/analyze` Analyze flow and window
features

GET `/api/v1/alerts` Filtered, paginated
alerts

GET `/api/v1/mitigations` Mitigation history and
status

POST `/api/v1/mitigations/simulate` Evaluate and record
simulated mitigation

POST `/api/v1/mitigations/{id}/cancel` Cancel an authorized
mitigation action

POST `/api/v1/mitigations/disable` Disable mitigation actions
through an authorized operator control

GET `/api/v1/audit` Retrieve authorized audit records;
optional `format=json|csv` export (default `json`)

GET `/api/v1/config/thresholds` Read threshold
configuration

PATCH `/api/v1/config/thresholds` Update authorized
threshold settings

---

### 7.1 Example Flow Request

```json
{
  "source_id": "lab-sensor-01",
  "timestamp": "2026-10-25T10:30:00Z",
  "window_seconds": 5,
  "features": {
    "packets_per_second": 1250.0,
    "bytes_per_second": 820000.0,
    "syn_packets_per_second": 980.0,
    "syn_ack_ratio": 8.5,
    "new_flows_per_second": 450.0,
    "unique_sources": 35
  }
}
```

The exact feature schema must be versioned and validated. Example values
are illustrative, not recommended thresholds.

### 7.2 Example Detection Response

```json
{
  "event_id": "evt_000123",
  "model_version": "rf-1.0.0",
  "prediction": "suspicious",
  "score_type": "documented_model_specific_score",
  "score": 0.91,
  "traffic_threshold_exceeded": true,
  "policy_decision": "simulate_rate_limit",
  "mitigation_mode": "simulation",
  "timestamp": "2026-10-25T10:30:00Z"
}
```

The score and its interpretation must be model-specific. Random Forest
probabilities and Isolation Forest anomaly scores are not
interchangeable.

### 7.3 Error Contract

```json
{
  "error": {
    "code": "INVALID_FEATURE_VALUE",
    "message": "A feature value failed validation.",
    "request_id": "req_000045"
  }
}
```

Use appropriate HTTP status codes: 400 for invalid operations, 401 for
unauthenticated requests, 403 for forbidden actions, 404 for missing
resources, 409 for conflicting state, 422 for schema validation
failures, 429 for rate limits, and 500 for unexpected errors. Avoid
returning secrets or internal stack traces.

---

## 8. Mitigation Policy Engine

### 8.1 Hybrid Policy

The policy engine considers: - ML evidence from Random Forest or
Isolation Forest - Flow-level and time-window traffic thresholds -
Persistence of suspicious behavior - Cooldowns and duplicate-action
prevention - Protected management traffic and allowlists - Explicit
action duration, rate, and concurrency limits

### 8.2 Policy Outcomes

- **No signal:** Continue monitoring.
- **ML signal only:** Raise an alert and gather additional evidence.
- **Traffic threshold only:** Raise an alert; an emergency action is
  allowed only if the configured emergency criteria and safety checks
  pass.
- **Both signals:** Request a bounded rate-limiting action after
  safety validation.
- **Protected target or unauthorized request:** Deny or constrain the
  action.
- **Policy or enforcement failure:** Stop new enforcement requests and
  alert the operator.

An emergency threshold must not authorize an unrestricted block. It
remains subject to action limits and protected-target checks.

### 8.3 Mitigation Requirements

- Default to simulation mode.
- Support configurable rate limits, burst allowances, maximum
  duration, cooldown, and maximum concurrent actions.
- Validate target and action parameters before enforcement.
- Assign unique IDs and audit each state transition.
- Provide operator disable and cancellation controls.
- Distinguish proposed, simulated, applied, expired, failed, and
  recovered actions.

### 8.4 Linux Enforcement Safeguards

- Keep the FastAPI process unprivileged.
- Use a separate, narrowly scoped enforcement component.
- Accept validated policy objects only---not arbitrary shell commands
  or user-supplied rule expressions.
- Restrict changes to a designated lab interface and test network.
- Track application-owned rules so cleanup does not remove unrelated
  administrator rules.
- Verify applied rules and expiration; document recovery if cleanup
  fails.
- Require explicit configuration and authorization to leave simulation
  mode.

---

## 9. React Dashboard Requirements

### 9.1 Visual Direction

- Dark cybersecurity operations interface
- Deep navy backgrounds with restrained cyan and green accents
- Amber for suspicious events and red for critical alerts
- Readable typography, accessible contrast, and clear status labels

### 9.2 Navigation

Use a fixed left sidebar on desktop, collapsing on smaller screens: 1.
Overview 2. Detection and Alerts 3. Mitigation 4. History and Analytics 5. Settings and Model Evaluation

### 9.3 Pages

**Overview** - Packet and byte rates - Threat status and model health -
Open alerts and mitigation status - Recent events and traffic trends

**Detection and Alerts** - Flow-level features and window statistics -
Prediction, documented score, and model version - Alert filtering by
severity, time, and status

**Mitigation** - Current mode and simulated or applied actions - Action
reason, duration, expiration, and cleanup status - Authorized controls
and emergency disable

**History and Analytics** - Historical traffic trends - Alert and
mitigation timeline - Audit records and export where authorized

**Settings and Model Evaluation** - Threshold configuration - Model
version and evaluation metrics - Administrative settings with role
checks

### 9.4 UI Requirements

- Clearly display simulation versus Linux enforcement mode.
- Refresh metrics through polling initially; add WebSockets if
  required.
- Display last update time and connection status.
- Show loading, empty, stale, disconnected, and error states.
- Require authorization and confirmation for sensitive changes.
- Never present sample or stale data as live measurements.
- Provide keyboard navigation and text labels in addition to colors.

---

## 10. Testing and Validation

### 10.1 Test Levels

- Unit tests for features, model outputs, thresholds, and cooldowns
- ML evaluation on held-out data
- API schema, authorization, and error tests
- Integration tests for ingestion through simulated mitigation
- Security tests for unauthorized actions and invalid targets
- Isolated Linux tests for enforcement, expiration, cleanup, and
  recovery
- Performance tests for latency, throughput, CPU, and memory

### 10.2 Essential Test Cases

---

ID Test Expected result

---

TC-01 Normal traffic No mitigation;
monitoring continues

TC-02 Abnormal burst Detection or alert
according to policy

TC-03 Suspected SYN flood Expected flow/window
detection and policy
result

TC-04 Emergency threshold Only bounded,
preconfigured emergency
action is requested

TC-05 Invalid feature values Request rejected; no
mitigation action

TC-06 Protected management Unsafe action denied or
traffic constrained

TC-07 Repeated alerts Cooldown and
deduplication prevent
unbounded actions

TC-08 Simulation safety No host firewall or
traffic-control changes

TC-09 Rule expiration Rule removal is
verified in the lab

TC-10 Cleanup failure Alert and documented
recovery path

TC-11 Unauthorized operator Administrative and
enforcement requests
denied

TC-12 Service restart Stored action states
reconciled with lab
rule states before
enforcement resumes

---

### 10.3 Release Gates

1.  **ML gate:** Quality metrics and limitations documented; goals met
    or deviations explicitly accepted.
2.  **Simulation gate:** Critical detection, policy, authorization, and
    no-network-change tests pass.
3.  **Linux lab gate:** Enforcement, expiration, restart reconciliation,
    and recovery verified in isolation.
4.  **Release gate:** No unresolved critical security issues; emergency
    disable and operations documentation complete.

---

## 11. Deployment Requirements

### Environment A --- Local Development

- Run React and FastAPI locally.
- Use public datasets for offline training.
- Use SQLite for initial persistence.
- Keep mitigation in simulation mode.

### Environment B --- Web Deployment

- Deploy frontend and API on compatible hosting.
- Keep secrets server-side and protect administrative endpoints.
- Use appropriate persistent storage.
- Keep Linux enforcement disabled.
- Do not assume serverless hosting supports packet capture, privileged
  networking, or long-running collectors.

### Environment C --- Isolated Linux Lab

- Run the collector and restricted enforcement adapter in a controlled
  Linux environment.
- Restrict enforcement to the designated lab interface and test
  network.
- Verify rate limits, expiration, cleanup, restart behavior, and
  recovery before authorizing real rule changes.

### Example Development Configuration

```dotenv
APP_ENV=development
MITIGATION_MODE=simulation
MODEL_PATH=models/approved_model.joblib
DATABASE_URL=sqlite:///./sentrix.db
API_AUTH_REQUIRED=true
API_AUTH_TOKEN=dev-only-change-me
```

Use `sentrix.db` as the local SQLite database filename. The token shown
is a local-development placeholder only; replace it outside local
development and never commit real secrets to version control. The
implementation must validate configuration.

---

## 12. Project Deliverables

1.  Approved PRD and acceptance criteria
2.  Dataset preparation and feature extraction pipeline
3.  Versioned Random Forest and Isolation Forest artifacts
4.  Model comparison and evaluation report
5.  FastAPI backend and documented API schemas
6.  React dashboard with live and historical views
7.  Hybrid policy engine and simulation adapter
8.  Restricted Linux enforcement integration and recovery procedure
9.  Automated unit, API, integration, and security tests
10. Deployment, setup, troubleshooting, and operations documentation

---

## 13. Acceptance Criteria

The project is ready for release when: - Both candidate models have been
evaluated and selection is documented. - Feature processing is
consistent between training and inference. - API validation and
authorization tests pass. - The dashboard accurately represents live and
historical backend data. - Hybrid policy tests pass in simulation
mode. - Simulation has been verified not to modify host networking. -
Linux enforcement and recovery pass isolated lab tests before
enforcement is enabled. - Installation, operating, audit, and recovery
instructions are complete.

---

## 14. Implementation Phases

---

| Phase | Scope | Exit condition |
| --- | --- | --- |
| 1 | Requirements, project skeleton, repository structure | Baseline requirements approved and development setup works |
| 2 | Dataset preparation and ML baseline | Reproducible training and evaluation report |
| 3 | FastAPI, detection engine, and policy integration | Validated and tested API endpoints and policy integration |
| 4 | React dashboard | Live and historical views connected to API |
| 5 | Simulation and integration testing | Critical simulation and safety tests pass |
| 6 | Isolated Linux enforcement integration | Expiration, cleanup, and recovery verified in the lab |
| 7 | Release hardening and documentation | Release gates recorded; docs complete and no unresolved critical security issues |

---

---

## 15. Risks and Assumptions

- Public datasets may not reflect the deployment network's traffic
  distribution.
- Dataset leakage can inflate reported metrics; split by capture,
  source, or time period where feasible.
- False positives may disrupt legitimate traffic if enforcement is too
  aggressive.
- Isolation Forest scores require their own thresholding and must not
  be treated as probabilities.
- A web-hosted API may not be suitable for packet capture or
  privileged network operations.
- Linux enforcement requires a separate threat model, least-privilege
  design, and recovery testing.
- The initial system is a research and defensive prototype, not a
  guarantee of production-grade DDoS protection.

**Document status:** Version 1.1 implementation baseline. Technical
thresholds, data schema, model selection, and deployment details must be
validated during development.
