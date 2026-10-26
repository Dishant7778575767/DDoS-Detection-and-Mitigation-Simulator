"""Detection analysis endpoint."""

from __future__ import annotations

import time
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_auth
from app.detection.predictor import run_flow_inference
from app.features.definitions import FEATURE_SCHEMA_VERSION
from app.ingestion.validators import validate_flow_features
from app.policy.engine import evaluate_hybrid_policy
from app.storage.database import get_db_session
from app.storage.repositories import ThresholdConfigRepository

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
