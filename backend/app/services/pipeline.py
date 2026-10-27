"""End-to-end processing pipeline coordinating ingestion, detection, policy, and simulation."""

from __future__ import annotations

import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.detection.predictor import run_flow_inference
from app.features.windows import SlidingWindowAggregator
from app.mitigation.lifecycle import validate_lifecycle_transition
from app.mitigation.simulation import SimulationAdapter
from app.policy.engine import evaluate_hybrid_policy
from app.safety.gate import validate_safety_gate
from app.storage.audit import record_audit_event
from app.storage.repositories import (
    AlertRepository,
    DetectionRepository,
    MitigationRepository,
    ObservationRepository,
    ThresholdConfigRepository,
)

# Global sliding window aggregator instance
window_aggregator = SlidingWindowAggregator(window_duration_seconds=10.0)
simulation_adapter = SimulationAdapter()


def process_flow_pipeline(
    session: Session,
    source_id: str,
    timestamp: str,
    window_seconds: float,
    feature_schema_version: str,
    features: dict[str, Any],
    target_ip: str | None = None,
    target_port: int | None = None,
) -> dict[str, Any]:
    """Execute full ingestion, detection, policy, safety gate, and simulation lifecycle."""
    obs_repo = ObservationRepository(session)
    det_repo = DetectionRepository(session)
    alert_repo = AlertRepository(session)
    mit_repo = MitigationRepository(session)
    thresh_repo = ThresholdConfigRepository(session)

    # 1. Persist observation
    obs = obs_repo.create(
        source_id=source_id,
        timestamp=timestamp,
        window_seconds=window_seconds,
        feature_schema_version=feature_schema_version,
        features=features,
        target_ip=target_ip,
    )

    # 2. Update window metrics
    packet_rate = float(features.get("Fwd Packets/s", 1.0))
    byte_rate = float(features.get("Flow Bytes/s", 100.0))
    window_aggregator.add_observation(
        timestamp=datetime.datetime.now(datetime.timezone.utc).timestamp(),
        packet_count=int(packet_rate * window_seconds),
        byte_count=int(byte_rate * window_seconds),
        syn_flags=int(features.get("Fwd PSH Flags", 0)),
        source_ip=target_ip,
    )

    # 3. Detection inference
    try:
        prediction = run_flow_inference(features)
    except Exception as exc:
        record_audit_event(
            session=session,
            event_type="pipeline_failure",
            action="inference_failed",
            actor="pipeline",
            details={
                "observation_id": obs.id,
                "error": str(exc),
                "source_id": source_id,
            },
        )
        raise

    # 4. Policy evaluation
    try:
        active_config = thresh_repo.get_active()
        policy_decision = evaluate_hybrid_policy(prediction, features, active_config)
    except Exception as exc:
        record_audit_event(
            session=session,
            event_type="pipeline_failure",
            action="policy_evaluation_failed",
            actor="pipeline",
            details={
                "observation_id": obs.id,
                "error": str(exc),
                "source_id": source_id,
            },
        )
        raise

    event_id = f"evt_{uuid4().hex[:12]}"
    detection = det_repo.create(
        event_id=event_id,
        observation_id=obs.id,
        model_version=prediction.model_version,
        feature_schema_version=prediction.feature_schema_version,
        prediction=prediction.prediction,
        score_type=prediction.score_type,
        score=prediction.score,
        traffic_threshold_exceeded=policy_decision.threshold_exceeded,
        policy_decision=policy_decision.action,
        mitigation_mode="simulation",
        timestamp=timestamp,
    )

    alert_obj = None
    mitigation_obj = None

    # 5. Alert generation if single or dual signal
    if policy_decision.action in ("alert", "request_mitigation"):
        score = prediction.score or 0.0
        if policy_decision.action == "request_mitigation" or score >= 0.85 or packet_rate > 20000:
            severity = "critical"
        elif score >= 0.65 or packet_rate > 8000:
            severity = "high"
        elif score >= 0.40 or packet_rate > 2000:
            severity = "medium"
        else:
            severity = "low"

        title = (
            f"DDoS Attack Pattern Detected ({severity.upper()})"
            if policy_decision.action == "request_mitigation"
            else f"Anomalous Traffic Signal ({severity.upper()})"
        )
        description = "; ".join(policy_decision.reasons)
        alert_obj = alert_repo.create(
            detection_id=detection.id,
            severity=severity,
            title=title,
            description=description,
            source_id=source_id,
            timestamp=timestamp,
        )
        record_audit_event(
            session=session,
            event_type="alert_created",
            action="create_alert",
            actor="policy_engine",
            details={
                "alert_id": alert_obj.alert_id,
                "event_id": event_id,
                "severity": severity,
                "reasons": policy_decision.reasons,
            },
        )

    # 6. Safety Gate and Simulation if mitigation requested
    effective_target = target_ip or "192.168.1.100"
    if policy_decision.action == "request_mitigation":
        active_count = mit_repo.count_filtered(status="simulated")
        safety_check = validate_safety_gate(
            target_ip=effective_target,
            rate_limit_pps=1000,
            duration_seconds=60,
            current_active_count=active_count,
            mitigation_mode="simulation",
        )

        if safety_check.allowed:
            validate_lifecycle_transition("proposed", "simulated")
            mitigation_obj = mit_repo.create(
                detection_id=detection.id,
                target_ip=effective_target,
                target_port=target_port,
                action_type="rate_limit",
                rate_limit_pps=1000,
                duration_seconds=60,
                status="proposed",
                mode="simulation",
            )
            sim_res = simulation_adapter.apply_rate_limit(
                action_id=mitigation_obj.action_id,
                target_ip=effective_target,
                rate_limit_pps=1000,
                duration_seconds=60,
            )
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            exp_dt = now_dt + datetime.timedelta(seconds=60)
            mit_repo.update_status(
                action_id=mitigation_obj.action_id,
                new_status="simulated",
                expires_at=exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            record_audit_event(
                session=session,
                event_type="mitigation_simulated",
                action="simulate_rate_limit",
                actor="safety_gate",
                details=sim_res,
            )

    return {
        "event_id": event_id,
        "observation_id": obs.id,
        "model_version": prediction.model_version,
        "feature_schema_version": prediction.feature_schema_version,
        "prediction": prediction.prediction,
        "score_type": prediction.score_type,
        "score": prediction.score,
        "traffic_threshold_exceeded": policy_decision.threshold_exceeded,
        "policy_decision": policy_decision.action,
        "mitigation_mode": "simulation",
        "timestamp": timestamp,
        "alert_id": alert_obj.alert_id if alert_obj else None,
        "mitigation_action_id": mitigation_obj.action_id if mitigation_obj else None,
    }
