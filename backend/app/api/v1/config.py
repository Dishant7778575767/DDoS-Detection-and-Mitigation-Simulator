"""Threshold configuration management endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_auth
from app.storage.audit import record_audit_event
from app.storage.database import get_db_session
from app.storage.repositories import ThresholdConfigRepository

router = APIRouter(tags=["config"], dependencies=[Depends(require_api_auth)])


class ThresholdConfigResponse(BaseModel):
    version: str
    is_active: bool
    pps_threshold: float
    bps_threshold: float
    syn_pps_threshold: float
    syn_ack_ratio_threshold: float
    rf_probability_threshold: float
    iforest_score_threshold: float
    updated_by: str
    created_at: str


class UpdateThresholdConfigRequest(BaseModel):
    pps_threshold: float | None = Field(default=None, ge=10.0, le=1_000_000.0)
    bps_threshold: float | None = Field(default=None, ge=100.0, le=10_000_000_000.0)
    syn_pps_threshold: float | None = Field(default=None, ge=1.0, le=500_000.0)
    syn_ack_ratio_threshold: float | None = Field(default=None, ge=0.1, le=100.0)
    rf_probability_threshold: float | None = Field(default=None, ge=0.1, le=1.0)
    iforest_score_threshold: float | None = Field(default=None, ge=-1.0, le=1.0)


@router.get("/config/thresholds", response_model=ThresholdConfigResponse)
def get_threshold_configuration(
    session: Annotated[Session, Depends(get_db_session)],
) -> ThresholdConfigResponse:
    """Return the active threshold configuration."""
    repo = ThresholdConfigRepository(session)
    active = repo.get_active()
    return ThresholdConfigResponse(
        version=active.version,
        is_active=active.is_active,
        pps_threshold=active.pps_threshold,
        bps_threshold=active.bps_threshold,
        syn_pps_threshold=active.syn_pps_threshold,
        syn_ack_ratio_threshold=active.syn_ack_ratio_threshold,
        rf_probability_threshold=active.rf_probability_threshold,
        iforest_score_threshold=active.iforest_score_threshold,
        updated_by=active.updated_by,
        created_at=active.created_at,
    )


@router.patch("/config/thresholds", response_model=ThresholdConfigResponse)
def update_threshold_configuration(
    payload: UpdateThresholdConfigRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> ThresholdConfigResponse:
    """Update threshold configuration and record an audit log event."""
    repo = ThresholdConfigRepository(session)
    updates = payload.model_dump(exclude_unset=True)
    new_config = repo.update(updated_by="operator_api", updates=updates)

    record_audit_event(
        session=session,
        event_type="threshold_config_updated",
        action="update_thresholds",
        actor="operator_api",
        details={
            "new_version": new_config.version,
            "updates": updates,
        },
    )

    return ThresholdConfigResponse(
        version=new_config.version,
        is_active=new_config.is_active,
        pps_threshold=new_config.pps_threshold,
        bps_threshold=new_config.bps_threshold,
        syn_pps_threshold=new_config.syn_pps_threshold,
        syn_ack_ratio_threshold=new_config.syn_ack_ratio_threshold,
        rf_probability_threshold=new_config.rf_probability_threshold,
        iforest_score_threshold=new_config.iforest_score_threshold,
        updated_by=new_config.updated_by,
        created_at=new_config.created_at,
    )
