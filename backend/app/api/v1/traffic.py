"""Traffic ingestion and summary endpoints."""

from __future__ import annotations

import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import require_api_auth
from app.ingestion.schemas import (
    FlowObservationRequest,
    TrafficSummaryResponse,
)
from app.ingestion.validators import (
    validate_flow_features,
    validate_iso8601_timestamp,
)
from app.services.pipeline import process_flow_pipeline, window_aggregator
from app.storage.database import get_db_session

router = APIRouter(tags=["traffic"], dependencies=[Depends(require_api_auth)])


@router.post("/traffic/flows", status_code=status.HTTP_201_CREATED)
def ingest_flow_observation(
    payload: FlowObservationRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Ingest, validate, and analyze a single flow observation."""
    # 1. Validate timestamp
    try:
        validated_timestamp = validate_iso8601_timestamp(payload.timestamp)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    # 2. Validate features and schema version
    try:
        validate_flow_features(payload.features, payload.feature_schema_version)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    # 3. Process through pipeline
    result = process_flow_pipeline(
        session=session,
        source_id=payload.source_id,
        timestamp=validated_timestamp,
        window_seconds=payload.window_seconds,
        feature_schema_version=payload.feature_schema_version,
        features=payload.features,
        target_ip=payload.target_ip,
        target_port=payload.target_port,
    )

    return {
        "status": "processed",
        "event_id": result["event_id"],
        "policy_decision": result["policy_decision"],
        "alert_id": result["alert_id"],
        "mitigation_action_id": result["mitigation_action_id"],
    }


@router.get("/traffic/summary", response_model=TrafficSummaryResponse)
def get_traffic_summary() -> TrafficSummaryResponse:
    """Return aggregated metrics over the active sliding window."""
    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
    summary = window_aggregator.get_summary(now_ts)
    return TrafficSummaryResponse(
        window_duration_seconds=summary.window_duration_seconds,
        observation_count=summary.observation_count,
        packet_rate=summary.packet_rate,
        byte_rate=summary.byte_rate,
        syn_rate=summary.syn_rate,
        syn_ack_ratio=summary.syn_ack_ratio,
        unique_sources=summary.unique_sources,
        is_burst=summary.is_burst,
    )
