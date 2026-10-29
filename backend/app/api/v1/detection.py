"""Detection analysis and threat evaluation endpoints for SENTRIX."""

from __future__ import annotations

import time
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_auth
from app.detection.baselines import telemetry_baseline
from app.detection.predictor import run_flow_inference
from app.detection.threat_classifier import (
    ThreatClassificationResult,
    classify_telemetry_snapshot,
)
from app.features.definitions import FEATURE_SCHEMA_VERSION
from app.features.telemetry_aggregator import telemetry_aggregator
from app.ingestion.telemetry_schemas import LiveTelemetrySummaryResponse
from app.ingestion.validators import validate_flow_features
from app.policy.engine import evaluate_hybrid_policy
from app.storage.audit import record_audit_event
from app.storage.database import get_db_session
from app.storage.repositories import AlertRepository, ThresholdConfigRepository

router = APIRouter(tags=["detection"], dependencies=[Depends(require_api_auth)])


class AnalyzeFlowRequest(BaseModel):
    feature_schema_version: str = Field(default=FEATURE_SCHEMA_VERSION)
    features: dict[str, float]


class AnalyzeFlowResponse(BaseModel):
    event_id: str
    model_version: str
    feature_schema_version: str
    prediction: str
    score_type: str
    score: float
    traffic_threshold_exceeded: bool
    policy_decision: str
    mitigation_mode: str
    timestamp: str


@router.post("/detection/analyze", response_model=AnalyzeFlowResponse)
def analyze_flow_features(
    payload: AnalyzeFlowRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> AnalyzeFlowResponse:
    """Analyze provided feature dictionary directly and return detection assessment."""
    try:
        validate_flow_features(payload.features, payload.feature_schema_version)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    prediction = run_flow_inference(payload.features)
    thresh_repo = ThresholdConfigRepository(session)
    active_config = thresh_repo.get_active()
    policy = evaluate_hybrid_policy(prediction, payload.features, active_config)

    return AnalyzeFlowResponse(
        event_id=f"evt_{uuid4().hex[:12]}",
        model_version=prediction.model_version,
        feature_schema_version=prediction.feature_schema_version,
        prediction=prediction.prediction,
        score_type=prediction.score_type,
        score=prediction.score,
        traffic_threshold_exceeded=policy.threshold_exceeded,
        policy_decision=policy.action,
        mitigation_mode="simulation",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


@router.get(
    "/detection/live",
    response_model=ThreatClassificationResult,
    summary="Evaluate active HTTP telemetry sliding window for DDoS signatures",
)
def evaluate_live_detection(
    session: Annotated[Session, Depends(get_db_session)],
    window_seconds: Annotated[
        float,
        Query(
            description="Sliding window duration to analyze in seconds",
            ge=1.0,
            le=300.0,
        ),
    ] = 10.0,
    persist_alert: Annotated[
        bool,
        Query(description="Persist active alerts to database when threat is confirmed"),
    ] = True,
) -> ThreatClassificationResult:
    """Run multi-tier threat classification over live aggregated web telemetry."""
    summary = telemetry_aggregator.get_summary(window_duration=window_seconds)
    result = classify_telemetry_snapshot(summary, baseline=telemetry_baseline)

    if persist_alert and result.is_threat:
        alert_repo = AlertRepository(session)
        recent_alerts = alert_repo.list_filtered(status="active", limit=10)
        already_alerted = any(
            a.source_id == "live_telemetry" and result.threat_type.value in a.title
            for a in recent_alerts
        )
        if not already_alerted:
            severity_str = (
                "critical"
                if result.severity.value in ("HIGH", "CRITICAL")
                else "warning"
            )
            alert = alert_repo.create(
                detection_id=None,
                severity=severity_str,
                title=f"Live Threat: {result.threat_type.value}",
                description="; ".join(result.reasons[:3]),
                source_id="live_telemetry",
                timestamp=result.timestamp,
            )
            record_audit_event(
                session=session,
                event_type="live_threat_detected",
                action="threat_classified",
                actor="sentrix_detection_engine",
                details={
                    "alert_id": alert.alert_id,
                    "threat_type": result.threat_type.value,
                    "severity": result.severity.value,
                    "confidence": result.confidence,
                    "target_candidates": result.candidate_target_ips,
                    "z_scores": result.z_scores,
                    "reasons": result.reasons,
                },
            )

    return result


@router.post(
    "/detection/evaluate-telemetry",
    response_model=ThreatClassificationResult,
    summary="Evaluate custom telemetry snapshot against baseline and signatures",
)
def evaluate_telemetry_snapshot(
    payload: LiveTelemetrySummaryResponse,
) -> ThreatClassificationResult:
    """Evaluate an explicit telemetry summary snapshot without auto-updating baseline."""
    return classify_telemetry_snapshot(
        payload, baseline=telemetry_baseline, update_baseline_if_normal=False
    )


@router.get(
    "/detection/baseline",
    summary="Retrieve current adaptive EWMA baseline statistics",
)
def get_adaptive_baseline() -> dict[str, Any]:
    """Return the current moving mean and variance for traffic baselines."""
    return telemetry_baseline.get_summary()


@router.post(
    "/detection/baseline/reset",
    summary="Reset and re-calibrate adaptive telemetry baselines",
)
def reset_adaptive_baseline() -> dict[str, str]:
    """Re-seed baseline with default healthy web parameters."""
    telemetry_baseline.calibrate()
    return {
        "status": "reset",
        "message": "Adaptive EWMA baselines re-calibrated successfully.",
    }
