# Project Requirements Document (PRD)

## Machine Learning-Based DDoS Detection and Mitigation Platform

**Project name:** SENTRIX DDoS Defense Platform\
**Document version:** 1.3\
**Tagline:** Detect. Defend. Stay Resilient.\
**Status:** Planning baseline; implementation status is tracked by phase\
**Date:** October 2026

**Version 1.3 changes:** Aligns the hybrid-policy outcomes, mitigation
lifecycle, and implementation phases with `SYSTEM_ARCHITECTURE.md`.
These are requirements, not claims of implementation or test completion.

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

- **Frontend:** Next.js, React, TypeScript, Tailwind CSS, and Recharts
- **Backend API:** Python and FastAPI
- **Input validation:** Pydantic
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
- Support both generated flow records and prepared flow records replayed
  from a file through the same runtime pipeline. These are demonstration
  records, not live network telemetry.
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

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-01 | Import supported public labeled datasets; validate their schema, labels, and provenance; clean records; and produce reproducible training, validation, and held-out test splits with a recorded manifest. | Must |
| FR-02 | Use the same versioned feature names, units, ordering, window definitions, and preprocessing in training and runtime inference; reject an incompatible feature-schema version. | Must |
| FR-03 | Train Random Forest and Isolation Forest candidates, evaluate and compare both, and document the evidence and rationale for any candidate approved for runtime use. Do not presume a candidate is selected. | Must |
| FR-04 | Report precision, recall, F1-score, confusion matrix, false-positive rate, p95 inference latency, CPU, and memory on identified datasets and documented test environments. | Must |
| FR-05 | Accept flow records through a Pydantic-validated API and/or controlled collector; reject invalid records without producing a mitigation action. | Must |
| FR-06 | Analyze observations and return a model-specific prediction or score, score type/interpretation, model version, feature-schema version, and timestamp. Do not represent Isolation Forest anomaly scores as probabilities without a separately defined and validated calibration method. | Must |
| FR-07 | Evaluate ML evidence and configured traffic thresholds as distinct policy signals. If neither indicates a threat, continue monitoring; if only one does, alert and gather evidence without automatic mitigation; if both do, consider a bounded request subject to the safety gate. | Must |
| FR-08 | Present traffic observations or summaries, alerts, detection results, model information, and mitigation lifecycle states in the React dashboard using backend data. | Must |
| FR-09 | Record simulated mitigation actions without changing host firewall rules, routing, traffic-control settings, or other host networking configuration, and without invoking privileged or networking-modification operations. | Must |
| FR-10 | Assign each mitigation request a unique identifier and record its decision, trigger, target, bounded parameters, duration, state transitions, and outcome in the audit history. | Must |
| FR-11 | Enforce configured action bounds, maximum duration, cooldowns, and concurrency limits; allow authorized operators to cancel eligible actions and activate an emergency-disable control; expose expiry and cleanup outcomes. | Must |
| FR-12 | Only in a separately approved, isolated Linux lab, apply rate limits through a restricted enforcement component after all simulation, safety, lab, recovery, and release gates in section 10.3 pass. | Must for lab phase |
| FR-13 | Verify expiry and cleanup of SENTRIX-owned temporary resources, reconcile persisted actions with actual lab state after restart before enforcement resumes, and provide a documented recovery procedure for failures or uncertainty. | Must for lab phase |
| FR-14 | Provide time, severity, and status filters for alerts and mitigation history; define pagination in the API contract. | Should |
| FR-15 | Track dataset and model versions, feature-schema versions, evaluation information, score interpretation, and threshold configuration. | Must |
| FR-16 | Provide a bounded generator and prepared-file replay for the initial end-to-end demonstration. Route both record sources through the same runtime ingestion, validation, feature aggregation, inference, policy, persistence, and reporting path. Identify their records as demonstration data, not live telemetry. | Must |
| FR-17 | Require authentication and backend authorization for protected administrative operations, including threshold updates, cancellation, emergency disable, audit access, and approval to enable lab enforcement. Record protected actions and their outcomes in the audit history. | Must |

---

---

## 4. Non-Functional Requirements

---

| ID | Requirement | Initial target / verification |
| --- | --- | --- |
| NFR-01 | Measure inference latency under a documented test environment and workload. | Target p95 below 100 ms per observation; report measured results and deviations rather than assuming the target is met. |
| NFR-02 | Evaluate detection quality on a held-out set that is separate from training and threshold tuning. | Initial goal: precision and recall each at least 90%. Report all FR-04 metrics and explicitly document any unmet goal; do not use accuracy alone for imbalanced data. |
| NFR-03 | Invalid input must be rejected without crashing the service or creating a mitigation action. | Automated API and integration tests cover malformed, out-of-range, incompatible-schema, and oversized requests. |
| NFR-04 | Protect administrative operations through authentication and authorization; keep the API process unprivileged and limit future enforcement privilege to the separate lab component. | Authorization tests cover each protected operation; inspect process/component permissions and lab boundary configuration before enabling enforcement. |
| NFR-05 | Simulation must not change host networking or invoke privileged enforcement/network-modification operations. | Automated tests assert the simulation adapter does not invoke subprocesses or enforcement operations; compare host firewall, routing, and traffic-control state before and after an isolated end-to-end test. |
| NFR-06 | Audit detections, policy decisions, protected operator actions, configuration changes, mitigation state transitions, and enforcement/cleanup outcomes, including failures. | Tests verify required events are recorded and observable through authorized audit retrieval. |
| NFR-07 | Keep ingestion, features, inference, policy, safety, adapters, persistence, API, and presentation as distinct responsibilities. | Verify the planned module boundaries in implementation and test that only the safety gate can route an action to an adapter. |
| NFR-08 | Distinguish normal and suspicious detections and every mitigation lifecycle state (`proposed`, `simulated`, `applied`, `failed`, `cancelled`, `expired`, `recovered`) in the dashboard. | UI/API integration tests verify displayed state and score interpretation match backend responses. |
| NFR-09 | Make dataset preparation and evaluation reproducible and record dataset versions, split manifest, feature configuration, model version, thresholds, and metrics. | Re-run preparation and evaluation with the recorded inputs/configuration and compare output manifests and reports. |
| NFR-10 | Document repeatable local development and isolated Linux lab setup, operation, troubleshooting, and recovery. | A reviewer follows the documented procedures in the corresponding environment; lab instructions include isolation and recovery evidence. |

---

NFR-01 and NFR-02 are proposed targets, not achieved results or automatic
release claims. Review them after the baseline evaluation. Record accepted
deviations and their rationale; accuracy alone is not sufficient for
imbalanced traffic data.

---

## 5. System Architecture

### 5.1 Logical Components

1. **Offline training:** Supported public datasets are validated,
   prepared, cleaned, split reproducibly, used to train and compare both
   candidate models, and exported as versioned artifacts only after
   documented selection and approval.
2. **Demonstration inputs:** A bounded generator and prepared-file replay
   provide flow records for the initial end-to-end demonstration. These
   are demonstration records, not live network telemetry.
3. **Ingestion and feature pipeline:** Pydantic validates API input;
   both demonstration inputs then use the same versioned feature
   processing and time-window aggregation.
4. **ML detection engine:** Loads only an approved, versioned model
   artifact with a compatible feature schema and returns a
   model-specific prediction or score.
5. **Policy decision engine:** Evaluates the model signal and configured
   traffic-threshold signal separately, subject to the outcomes in
   section 8, cooldowns, protected targets, and action limits.
6. **Safety gate:** The backend verifies authorization, target validity,
   action bounds, current mode, and disable/reconciliation state before
   any adapter can receive an action.
7. **Mitigation adapters:** Simulation is the default. A separate,
   restricted Linux enforcement component is deferred to the isolated
   lab phase and remains disabled until all required gates and explicit
   approval are satisfied.
8. **Persistence and audit:** SQLite (`sentrix.db`) is planned to store
   traffic observations or summaries, detection results, alerts,
   model/schema versions, threshold configuration, mitigation lifecycle
   outcomes, and audit events.
9. **FastAPI backend and dashboard:** The backend exposes the planned
   API contracts. The Next.js/React/TypeScript dashboard uses Tailwind
   CSS and Recharts to report backend state; it is not an enforcement
   authority.

The initial implementation may be a single FastAPI application with
separated modules; each component does not need to run as an independent
service.

### 5.2 End-to-End Data Flow

1. Prepare and evaluate public datasets in the separate offline training
   workflow. Only a documented and approved versioned artifact is
   eligible for runtime inference.
2. A generator or prepared-file replay submits demonstration flow
   records. Both sources enter the same API ingestion, validation,
   feature/window aggregation, inference, hybrid policy, safety,
   persistence, and reporting path.
3. Invalid input is rejected without creating a detection-driven
   mitigation action. Valid input produces a model-specific detection
   result and timestamp.
4. The hybrid policy evaluates ML and threshold signals separately and
   records its decision according to section 8. A single signal creates
   an alert and gathers evidence; it does not initiate mitigation.
5. A permitted request is recorded by the simulation adapter by
   default. Simulation causes no host network changes and invokes no
   privileged enforcement operation. Linux lab execution is a separate
   gated path, never an automatic fallback.
6. Persist results and audit outcomes in the backend store; the
   dashboard reads backend data and clearly identifies demonstration
   records rather than presenting them as live telemetry.
7. In lab mode only, expire and clean up SENTRIX-owned temporary
   resources, verify the outcome, and record failures or recovery.

### 5.3 Architecture Constraints

- `MITIGATION_MODE=simulation` is the default. Simulation must not
  modify host firewall rules, routing, traffic-control settings, or
  other host networking configuration; it must not invoke privileged
  enforcement commands or networking-modification operations.
- The model must never execute shell commands or directly control
  networking. Any lab enforcement component is separate from the
  unprivileged API and accepts validated, bounded policy objects only.
- Runtime actions require the backend safety gate, authentication and
  authorization where protected, target validation, bounded
  parameters, and an enabled mode. The dashboard is not authoritative.
- Persisted lab actions must be reconciled with actual lab state after
  restart before enforcement is permitted. Unknown or unreconciled state
  blocks enforcement.
- Training, validation, and test data must be split to reduce leakage,
  preferably by capture, source, or time period.
- A prediction is evidence of suspicious behavior, not proof of
  malicious intent.

---

## 6. Machine Learning Pipeline

### 6.1 Dataset Strategy

- **Primary dataset candidate:** CIC-DDoS2019 for labeled DDoS-related flow
  data.
- **Optional dataset candidate:** CIC-IDS2017 for broader intrusion
  and traffic patterns.
- **Integration validation:** Controlled benign and bounded
  attack-like traffic in an isolated lab.
- Record dataset source, version, license/provenance, schema, and label
  meanings before use; exclude a dataset when its license, labels, or
  feature availability cannot be established.
- Keep lab validation separate from data used to tune model
  thresholds.

### 6.2 Feature Engineering

Initial candidate features include:

- Packets per second and bytes per second
- Total packets and bytes per flow
- SYN packet rate and SYN-to-ACK ratio where available
- New flows per second
- Flow duration
- Unique source count per time window
- Rate changes, rolling averages, and burst statistics

Features must be available at inference time. Do not use target labels,
future observations, or post-event information. Training and inference
must use the same versioned feature names, units, order, window
definitions, and preprocessing; record that schema version in model
artifacts and detection results. The final feature schema is an
implementation decision subject to validation against the available data
and runtime inputs.

### 6.3 Candidate Models

**Random Forest:** Train as a supervised candidate using labeled normal
and attack-related traffic. Tune tree count, depth, and class weighting
using training/validation procedures only. Treat any class probability
as a model output, not guaranteed calibrated confidence.

**Isolation Forest:** Train as an unsupervised anomaly-detection
candidate, preferably fitted on representative benign training data.
Tune its decision threshold on a separate labeled validation set.
Document the score convention and interpretation. Do not represent an
anomaly score as a probability unless a calibration method is separately
defined and validated.

Neither candidate is the runtime model until comparison, selection, and
approval are documented. If neither meets the reviewed targets, do not
enable enforcement on the basis of the model comparison.

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
using Pydantic. Timestamps use UTC ISO 8601. `API_AUTH_REQUIRED=true` is
the default; requests are authenticated by default. Protected
administrative operations additionally require backend authorization.
The exact roles and read-access policy for non-administrative routes are
open decisions; they must not be delegated to the dashboard.

| Method | Endpoint | Purpose and intended response | Authentication / authorization |
| --- | --- | --- | --- |
| `GET` | `/api/v1/health` | Return service health without exposing secrets or internal details. | Authenticated by default; whether a deployment may expose a minimal health response is an operational decision. |
| `GET` | `/api/v1/models` | Return available model versions and identify the approved active model, if one is configured. | Authenticated by default; read permission policy remains to be defined. |
| `GET` | `/api/v1/models/metrics` | Return documented evaluation metrics and their dataset/environment context. | Authenticated by default; read permission policy remains to be defined. |
| `POST` | `/api/v1/traffic/flows` | Validate submitted flow observations; on success, return/identify processing results; reject invalid input without creating a mitigation action. | Authenticated by default; sender permission policy remains to be defined. |
| `GET` | `/api/v1/traffic/summary` | Return traffic and time-window summaries. | Authenticated by default; read permission policy remains to be defined. |
| `POST` | `/api/v1/detection/analyze` | Analyze supplied flow/window features and return a model-specific result with model/schema versions and timestamp. | Authenticated by default; sender permission policy remains to be defined. |
| `GET` | `/api/v1/alerts` | Return filtered, paginated alerts. | Authenticated by default; read permission policy remains to be defined. |
| `GET` | `/api/v1/mitigations` | Return filtered, paginated mitigation history and lifecycle status. | Authenticated by default; read permission policy remains to be defined. |
| `POST` | `/api/v1/mitigations/simulate` | Evaluate and record a simulation-only action; must not alter host networking or invoke privileged enforcement. | Authentication and backend authorization required; specific permission remains to be defined. |
| `POST` | `/api/v1/mitigations/{id}/cancel` | Request cancellation of an eligible action and return its observable lifecycle outcome; an applied action is not marked cancelled until owned-resource cleanup is verified. | Authentication and backend authorization required. |
| `POST` | `/api/v1/mitigations/disable` | Activate emergency disable, block new mitigation/enforcement requests, and report disable and active-action handling outcomes. | Authentication and backend authorization required. |
| `GET` | `/api/v1/audit` | Return authorized audit records; optional `format=json\|csv`, default `json`. | Authentication and explicit audit-read authorization required. |
| `GET` | `/api/v1/config/thresholds` | Return current threshold configuration and version/status information. | Authenticated by default; read permission policy remains to be defined. |
| `PATCH` | `/api/v1/config/thresholds` | Validate and update threshold configuration, returning the accepted configuration/version or a defined error. | Authentication and threshold-administration authorization required. |

These are planned contracts, not claims that the routes exist. Response
schemas, query parameter details, pagination fields, and exact status
codes beyond the error contract below must be specified in the API schema
deliverable before endpoint implementation. Requests must have documented
maximum body and collection sizes and field/range validation; those limits
are implementation decisions and must be tested at and beyond each limit.

---

### 7.1 Example Flow Request

```json
{
  "source_id": "lab-sensor-01",
  "timestamp": "2026-10-25T10:30:00Z",
  "window_seconds": 5,
  "feature_schema_version": "features-v1",
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

The exact feature schema must be versioned and validated. The schema
version shown is illustrative and must match the approved artifact and
runtime definitions. Example values are illustrative, not recommended
thresholds.

### 7.2 Example Detection Response

```json
{
  "event_id": "evt_000123",
  "model_version": "rf-1.0.0",
  "feature_schema_version": "features-v1",
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
interchangeable. The example score is illustrative, not measured
performance or an acceptance threshold.

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
failures, 413 for requests exceeding documented size limits, 429 for
rate limits, and 500 for unexpected errors. Avoid returning secrets or
internal stack traces. Error responses use the documented `code`,
`message`, and `request_id` fields.

---

## 8. Mitigation Policy Engine

### 8.1 Hybrid Policy

The policy engine evaluates these as distinct signals:

- ML evidence from the approved Random Forest or Isolation Forest model.
- Flow-level and time-window traffic thresholds.

It also applies configured persistence rules, cooldowns and
duplicate-action prevention, protected management targets/allowlists,
and action limits. Any persistence interval or threshold value must be
configured and documented; this PRD does not prescribe numeric values.

### 8.2 Policy Outcomes

- **Neither signal indicates a threat:** Continue monitoring; do not
  create a mitigation request.
- **ML signal only:** Create an alert and gather evidence; do not
  automatically mitigate.
- **Threshold signal only:** Create an alert and gather evidence; do
  not initiate mitigation.
- **Both signals indicate a threat:** Consider a bounded
  rate-limiting request after safety validation. This is a request for
  the configured adapter, not proof that an action was applied.
- **Protected target, unauthorized request, disabled mode, or invalid
  bounds:** Deny the request and record the decision where applicable.
- **Policy, adapter, expiry, cleanup, or reconciliation failure:** Make
  the failure observable and auditable. Block further lab enforcement
  while state is uncertain; notify the operator.

Model scores must be interpreted according to the approved model's
documented score type. Isolation Forest anomaly scores are not
probabilities unless a calibration method is explicitly defined and
validated.

### 8.3 Mitigation Requirements

- `MITIGATION_MODE=simulation` is the default. Simulation may record
  policy outcomes and simulated actions but must never change host
  firewall rules, routes, traffic-control settings, or other host
  networking configuration; invoke privileged enforcement commands; or
  call networking-modification operations.
- Every mitigation request must have a unique ID and validated target,
  rate, burst, duration, and concurrency bounded by configured limits,
  including a defined maximum duration. Final limit values are open
  configuration decisions; absence of a valid limit must fail closed.
- Route every action through the backend safety gate. The gate checks
  authentication/authorization, protected targets, parameter bounds,
  mode, emergency-disable status, and enforcement reconciliation
  status before adapter execution.
- Audit each policy decision, state transition, operator control,
  configuration change, adapter outcome, expiry, cleanup result, and
  failure. Audit records must be retrievable only through authorized
  access.
- Provide authorized operator controls for cancellation of eligible
  actions and emergency disable.
- Distinguish and enforce the lifecycle states and transitions below.
  A simulated action must never be represented as an applied network
  change.
- Cancellation, expiry, cleanup, and recovery are separate outcomes.
  Cancellation of an action does not assert that a prior network state
  was restored. Cleanup may remove only resources created and tracked
  by SENTRIX; it must not remove unrelated firewall or traffic-control
  configuration.
- Emergency disable must immediately prevent new mitigation/enforcement
  requests. For already-applied lab actions, it must request cleanup of
  eligible SENTRIX-owned changes and report whether cleanup was
  verified. If cleanup fails or state is uncertain, enforcement remains
  disabled and the operator is alerted. The exact handling of
  non-cancellable/in-progress actions and the permission to release the
  disable remain implementation decisions and must be tested.

#### Mitigation lifecycle

The implementation must persist and validate lifecycle states. At
minimum, the state meanings are:

| State | Required meaning |
| --- | --- |
| `proposed` | Policy requested an action; no adapter outcome has been recorded. |
| `simulated` | Simulation adapter recorded the request only; no host networking change or privileged enforcement operation occurred. It is a terminal simulation outcome, never an applied network change. |
| `applied` | A lab action was applied and verified on the designated lab resource. This state is impossible in simulation mode. |
| `failed` | An operation or its required verification failed; expose the failure and block further enforcement when state is uncertain. |
| `cancelled` | An eligible action was cancelled. For an applied action, use this state only after removal of its SENTRIX-owned change is verified. |
| `expired` | An applied lab action reached its defined duration and removal of its SENTRIX-owned change was verified. |
| `recovered` | A previously failed or uncertain lab state was reconciled and safely resolved, with the recovery result audited. |

At minimum, enforce these transition constraints: `proposed` may become
`simulated`, `applied`, `failed`, or `cancelled`; `applied` may become
`cancelled`, `expired`, or `failed`; and `failed` may become `recovered`
only after resolution is verified. `simulated`, `cancelled`, `expired`,
and `recovered` are terminal outcomes. Do not report cancellation or
applied-action expiry as successful if
SENTRIX-owned resource cleanup was not verified. Exact handling of
concurrent state changes, pending cleanup representation, and any
additional transitions must be documented before implementation.

For cancellation or emergency disable of an already-applied lab action,
attempt cleanup only for the action's tracked SENTRIX-owned resource;
verify removal before recording `cancelled` or `expired`. If cleanup
cannot be confirmed, record `failed`, alert the operator, preserve
evidence needed for recovery, and keep lab enforcement disabled. Cleanup
does not restore an unrelated prior network configuration. A restart
must reconcile persisted actions against actual lab state before any
enforcement resumes; unknown or mismatched state fails closed.

### 8.4 Linux Enforcement Safeguards

- Keep the FastAPI process unprivileged and use a separate,
  narrowly-scoped privileged component only in the isolated lab.
- Accept validated, bounded policy objects only; never accept arbitrary
  shell commands or user-supplied rule expressions.
- Restrict all changes to a designated lab interface and test network.
- Tag and track each SENTRIX-owned rule/resource so cleanup cannot
  remove unrelated administrator rules or settings.
- Verify application, expiry, and cleanup; surface failures and
  document and test recovery.
- Keep enforcement disabled by default. It may be enabled only after
  the simulation safety tests pass, authorization/bounds/cancellation/
  emergency-disable tests pass, isolated lab application/expiry/
  cleanup/restart-reconciliation/recovery tests pass, the release gates
  pass, and explicit lab approval is recorded.
- Do not fall back automatically from simulation to lab enforcement.

---

## 9. React Dashboard Requirements

### 9.1 Visual Direction

- Dark cybersecurity operations interface
- Deep navy backgrounds with restrained cyan and green accents
- Amber for suspicious events and red for critical alerts
- Readable typography, accessible contrast, and clear status labels

### 9.2 Navigation

Use a fixed left sidebar on desktop, collapsing on smaller screens:
Overview; Detection and Alerts; Mitigation; History and Analytics; and
Settings and Model Evaluation.

### 9.3 Pages

**Overview:** Packet and byte rates, threat status and model health,
open alerts and mitigation status, recent events, and traffic trends.
Label demonstration records distinctly from live telemetry.

**Detection and Alerts:** Flow-level features and window statistics,
prediction and documented score interpretation, model and feature
schema versions, and alert filtering by severity, time, and status.

**Mitigation:** Current mode; visibly distinct simulated and applied
actions; action reason, duration, expiry and cleanup status; and
authorized cancellation and emergency-disable controls.

**History and Analytics:** Historical backend traffic trends; alert
and mitigation timelines; and audit records/export only where
authorized.

**Settings and Model Evaluation:** Threshold configuration, model
version and evaluation metrics, and protected settings with role checks.

### 9.4 UI Requirements

- Clearly display simulation versus Linux enforcement mode.
- Refresh metrics through polling initially; add WebSockets only if
  justified by requirements.
- Display last update time and connection status.
- Show loading, empty, stale, disconnected, and error states.
- Require authorization and confirmation for sensitive changes.
- Never present generated, replayed, sample, stale, or otherwise
  non-live data as live measurements; show source and last-update state.
- Provide keyboard navigation and text labels in addition to colors.

---

## 10. Testing and Validation

### 10.1 Test Levels

- Unit tests for feature definitions, model-specific score
  interpretation, thresholds, lifecycle transitions, and cooldowns.
- Reproducible ML evaluation on a held-out set with recorded data/split
  manifests, metrics, model versions, and environment.
- API schema, request-size/range validation, authentication,
  authorization, pagination, and error-contract tests.
- Integration tests for both generator and prepared-file replay through
  the shared ingestion-to-reporting path.
- Security tests for unauthorized actions, protected targets,
  unbounded requests, unsafe configuration, and secret/error leakage.
- Simulation safety tests that verify no host firewall, route,
  traffic-control, or other networking changes and no privileged or
  network-modification operation is invoked.
- Isolated Linux lab tests for application, expiry, cleanup,
  restart reconciliation, failure handling, and recovery.
- Performance tests for latency, throughput, CPU, and memory under
  documented workloads and environments.

### 10.2 Essential Test Cases

---

| ID | Test | Expected result |
| --- | --- | --- |
| TC-01 | Normal traffic | Neither signal indicates a threat; monitoring continues and no mitigation is requested. |
| TC-02 | Abnormal burst | Detection and alert behavior matches the documented model and policy signals; action is not inferred from an unmeasured score. |
| TC-03 | Suspected SYN flood | Flow/window features, model-specific result, threshold signal, and policy outcome are recorded and traceable. |
| TC-04 | Threshold signal only | Alert and gather evidence; no mitigation request is made from the threshold signal alone. |
| TC-05 | Invalid feature values/schema | Request is rejected; no detection-driven mitigation action is created. |
| TC-06 | Protected management target | Unsafe action is denied or constrained by the backend safety gate and recorded. |
| TC-07 | Repeated alerts | Configured cooldown/deduplication prevents actions exceeding configured bounds. |
| TC-08 | Simulation safety | End-to-end simulation changes no host firewall, route, traffic-control, or other networking state and invokes no privileged/network-modification operation. |
| TC-09 | Rule expiration | In the isolated lab, the SENTRIX-owned rule is removed and removal is verified at expiry; unrelated rules remain unchanged. |
| TC-10 | Cleanup failure | Failure is visible and audited, the operator is notified, recovery is documented, and new enforcement remains disabled while state is uncertain. |
| TC-11 | Unauthorized operator | Protected threshold, cancellation, disable, audit, and enforcement operations are denied and audited as applicable. |
| TC-12 | Service restart | Persisted actions are reconciled with lab state before enforcement resumes; mismatch or unknown state keeps enforcement disabled. |
| TC-13 | Hybrid decision matrix | Tests cover neither signal, each single signal, and both signals; either single signal alone produces an alert/evidence outcome and no mitigation request. |
| TC-14 | Generated and file replay | Both input sources traverse the same runtime stages; results are persisted/reported with a visible demonstration-data source designation. |
| TC-15 | Cancellation and emergency disable | Cancellation of eligible simulation actions is recorded without network effects. Disable blocks new requests; active lab actions are cleaned up only if SENTRIX-owned, with verified outcomes or a failed/disabled recovery state. |
| TC-16 | Lifecycle and audit | Invalid transitions are rejected; every required transition, protected control, configuration change, expiry, cleanup, and failure is auditable. Simulated actions are never reported as applied. |

---

### 10.3 Release Gates

1. **ML gate:** Reproducible preparation and held-out evaluation
   evidence, candidate comparison, model selection rationale, and
   limitations are documented. Proposed quality targets are met or
   deviations are explicitly accepted.
2. **Simulation gate:** End-to-end generator and file-replay tests,
   hybrid-policy outcomes, authorization, cancellation, emergency
   disable, lifecycle/audit, and no-network-change tests pass.
3. **Linux lab gate:** Only after the simulation gate passes, isolated
   tests verify enforcement bounds, expiry, SENTRIX-owned cleanup,
   restart reconciliation, failure blocking, and recovery. Explicit
   lab approval is recorded before enabling lab enforcement.
4. **Release gate:** No unresolved critical security issues; release
   evidence is recorded; emergency disable, operations, troubleshooting,
   and recovery documentation is complete.

Passing the simulation gate does not enable Linux enforcement. Lab
enforcement remains disabled until all four applicable prerequisites
(simulation/safety tests, isolated lab verification, recovery
verification, and required release gates) pass and explicit approval
is given.

---

## 11. Deployment Requirements

### Environment A --- Local Development

- Run React and FastAPI locally.
- Use public datasets for offline training.
- Use SQLite for initial persistence.
- Keep mitigation in simulation mode.
- Use only the documented development placeholder token locally; never
  reuse it in a shared or deployed environment.

### Environment B --- Web Deployment

- Deploy frontend and API on compatible hosting.
- Keep secrets server-side and protect administrative endpoints.
- Use appropriate persistent storage.
- Keep Linux enforcement disabled.
- Do not commit real credentials or expose them in logs or API errors.
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
implementation must validate configuration, reject unsupported
mitigation modes, and refuse to enable Linux lab mode without the
required explicit approval/configuration. Request-size and action-bound
configuration must have documented values before the corresponding
operations are enabled.

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

### 13.1 Demonstration and release acceptance

The normal demonstration/release candidate is acceptable only when the
following evidence is recorded:

1. Dataset preparation is reproducible from documented versions,
   cleaning rules, and split manifests; evaluation reports held-out
   results for both candidate models using the required metrics.
2. Model comparison, limitations, score conventions, and the selection
   decision are documented. No candidate is treated as approved until
   this evidence is reviewed.
3. Training and inference use the same feature-schema version and
   preprocessing; incompatible artifact/schema combinations are
   rejected.
4. API schemas, input/range/request-size validation, authentication,
   authorization, and error responses pass automated tests.
5. The hybrid decision matrix passes tests for neither signal, each
   single signal, and both signals; either single signal alone does not
   initiate mitigation; protected-target checks are covered.
6. Generated and prepared-file replay records traverse the same
   end-to-end runtime path through reporting. The dashboard identifies
   both as demonstration data, not live network telemetry, and matches
   persisted backend state.
7. Simulation tests demonstrate no host firewall, route,
   traffic-control, or other networking changes and no privileged or
   networking-modification operation.
8. Automated tests cover cancellation, emergency disable, lifecycle
   transitions, audit events, and applicable expiry/cleanup failure
   handling; lab-rule expiry and cleanup must pass the separate lab gate.
9. Operations, setup, troubleshooting, audit, and recovery
   documentation is complete and its procedures are reviewed.

### 13.2 Additional acceptance required before Linux lab enforcement

Lab enforcement must remain disabled unless all of the following
evidence is recorded:

1. The simulation and safety gates in section 10.3 have passed.
2. Enforcement is tested only in an isolated lab restricted to its
   designated interface and test network.
3. Action bounds, authorization, cancellation, emergency disable,
   expiry, cleanup ownership, and failure behavior pass lab tests.
4. Persisted actions are reconciled against actual lab state after
   restart; unknown or unreconciled state blocks enforcement.
5. Cleanup affects only SENTRIX-owned resources; expiry and cleanup
   verification and recovery from failure are demonstrated and
   documented.
6. Required release gates pass and explicit lab approval is recorded.

These criteria define required evidence, not a statement that any test
has passed or that enforcement is enabled.

---

## 14. Implementation Phases

---

| Phase | Scope | Exit condition |
| --- | --- | --- |
| 1 | Foundation and skeleton | Health endpoint works, five dashboard routes load, and CI is green; fresh-environment setup is reproducible. |
| 2 | Data and ML baseline | Reproducible training and evaluation report; candidate comparison and model selection are documented (ML gate). |
| 3 | Backend, detection and policy | Every PRD section 7 endpoint is validated and tested; a traffic-flow request produces a stored detection, alert, and simulated action where policy requests one. |
| 4 | Dashboard | Live and historical views run on real API data and accurately show backend state. |
| 5 | Simulation and integration testing | Critical detection, policy, authorization, lifecycle, audit, and no-network-change tests pass (simulation gate). |
| 6 | Isolated Linux lab | Enforcement, expiry, restart reconciliation, cleanup, and recovery are verified in isolation; explicit lab approval is recorded before enforcement is enabled. |
| 7 | Release hardening | Release gates are recorded; operating, troubleshooting, and recovery documentation is complete; no unresolved critical security issues remain. |

---

---

## 15. Risks and Assumptions

- Public datasets may not reflect a deployment network's traffic
  distribution; separately evaluate controlled lab traffic and document
  this limitation.
- Dataset leakage can inflate reported metrics; split by capture,
  source, or time period where feasible and retain split manifests.
- False positives may disrupt legitimate traffic if enforcement is too
  aggressive; require policy evidence, bounds, allowlists, cooldowns,
  operator controls, and default simulation.
- Isolation Forest scores require their own thresholding and must not
  be treated as probabilities without defined and validated
  calibration.
- A web-hosted API may not be suitable for packet capture or
  privileged network operations.
- Linux enforcement requires a separate threat model, least-privilege
  design, isolation, reconciliation, and recovery testing.
- Exact request limits, action bounds, maximum duration, role
  permissions, persistence schema/retention, and lab approval procedure
  require implementation decisions and documented tests; do not infer
  values or guarantees.
- The initial system is a research and defensive prototype, not a
  guarantee of production-grade DDoS protection.

**Document status:** Version 1.3 planning baseline. Requirements and
targets do not indicate implementation or test completion. Technical
thresholds, data schema, model selection, request/action limits, and
deployment details must be validated during development.
