"""Mitigation lifecycle and simulation endpoints."""

from __future__ import annotations

import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_auth
from app.mitigation.lifecycle import validate_lifecycle_transition
from app.mitigation.simulation import SimulationAdapter
from app.safety.gate import (
    set_emergency_disabled,
    validate_safety_gate,
)
from app.storage.audit import record_audit_event
from app.storage.database import get_db_session
from app.storage.repositories import MitigationRepository

router = APIRouter(tags=["mitigations"], dependencies=[Depends(require_api_auth)])
simulation_adapter = SimulationAdapter()


class MitigationItem(BaseModel):
    action_id: str
    detection_id: int | None
    target_ip: str
    target_port: int | None
    action_type: str
    rate_limit_pps: int
    duration_seconds: int
    status: str
    mode: str
    created_at: str
    updated_at: str
    expires_at: str | None
    cancelled_at: str | None


class MitigationsListResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    mitigations: list[MitigationItem]


class SimulateMitigationRequest(BaseModel):
    target_ip: str = Field(..., description="Target IPv4/IPv6 address to rate-limit")
    target_port: int | None = Field(default=None, ge=0, le=65535)
    rate_limit_pps: int = Field(default=1000, ge=100, le=50000)
    duration_seconds: int = Field(default=60, ge=10, le=300)


@router.get("/mitigations", response_model=MitigationsListResponse)
def list_mitigations(
    session: Annotated[Session, Depends(get_db_session)],
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="Filter by status (e.g., 'simulated', 'cancelled')",
    ),
    mode_filter: str | None = Query(
        default=None, alias="mode", description="Filter by mode ('simulation', 'lab')"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> MitigationsListResponse:
    """Return filtered and paginated mitigations."""
    repo = MitigationRepository(session)
    items = repo.list_filtered(
        status=status_filter, mode=mode_filter, limit=limit, offset=offset
    )
    total = repo.count_filtered(status=status_filter, mode=mode_filter)

    return MitigationsListResponse(
        total_count=total,
        limit=limit,
        offset=offset,
        mitigations=[
            MitigationItem(
                action_id=m.action_id,
                detection_id=m.detection_id,
                target_ip=m.target_ip,
                target_port=m.target_port,
                action_type=m.action_type,
                rate_limit_pps=m.rate_limit_pps,
                duration_seconds=m.duration_seconds,
                status=m.status,
                mode=m.mode,
                created_at=m.created_at,
                updated_at=m.updated_at,
                expires_at=m.expires_at,
                cancelled_at=m.cancelled_at,
            )
            for m in items
        ],
    )


@router.post("/mitigations/simulate", status_code=status.HTTP_201_CREATED)
def simulate_mitigation(
    payload: SimulateMitigationRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Evaluate safety gate and execute a simulation-only rate-limiting action."""
    repo = MitigationRepository(session)
    active_count = repo.count_filtered(status="simulated")

    # Pass through safety gate
    safety_result = validate_safety_gate(
        target_ip=payload.target_ip,
        rate_limit_pps=payload.rate_limit_pps,
        duration_seconds=payload.duration_seconds,
        current_active_count=active_count,
        mitigation_mode="simulation",
    )
    if not safety_result.allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=safety_result.rejection_reason
            or "Safety gate rejected the request.",
        )

    # State transition: proposed -> simulated
    validate_lifecycle_transition("proposed", "simulated")
    mitigation = repo.create(
        detection_id=None,
        target_ip=payload.target_ip,
        target_port=payload.target_port,
        action_type="rate_limit",
        rate_limit_pps=payload.rate_limit_pps,
        duration_seconds=payload.duration_seconds,
        status="proposed",
        mode="simulation",
    )

    sim_outcome = simulation_adapter.apply_rate_limit(
        action_id=mitigation.action_id,
        target_ip=payload.target_ip,
        rate_limit_pps=payload.rate_limit_pps,
        duration_seconds=payload.duration_seconds,
    )

    exp_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        seconds=payload.duration_seconds
    )
    repo.update_status(
        action_id=mitigation.action_id,
        new_status="simulated",
        expires_at=exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )

    record_audit_event(
        session=session,
        event_type="mitigation_simulated",
        action="simulate_rate_limit",
        actor="operator_api",
        details=sim_outcome,
    )

    return sim_outcome


@router.post("/mitigations/{action_id}/cancel")
def cancel_mitigation(
    action_id: Annotated[str, Path(description="The unique action ID to cancel")],
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Request cancellation of an active or simulated mitigation action."""
    repo = MitigationRepository(session)
    mitigation = repo.get_by_action_id(action_id)
    if not mitigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mitigation action '{action_id}' not found.",
        )

    # Validate lifecycle transition
    try:
        validate_lifecycle_transition(mitigation.status, "cancelled")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    cancel_outcome = simulation_adapter.cancel_rate_limit(
        action_id=action_id,
        target_ip=mitigation.target_ip,
    )

    cancelled_timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    repo.update_status(
        action_id=action_id,
        new_status="cancelled",
        cancelled_at=cancelled_timestamp,
    )

    record_audit_event(
        session=session,
        event_type="mitigation_cancelled",
        action="cancel_mitigation",
        actor="operator_api",
        details={
            "action_id": action_id,
            "target_ip": mitigation.target_ip,
            "previous_state": mitigation.status,
            "cancelled_at": cancelled_timestamp,
        },
    )

    return cancel_outcome


@router.post("/mitigations/disable")
def emergency_disable_mitigations(
    session: Annotated[Session, Depends(get_db_session)],
    enable: Annotated[
        bool, Query(description="Set to true to re-enable mitigations")
    ] = False,
) -> dict[str, Any]:
    """Activate or deactivate emergency disable switch to halt or restore mitigations."""
    if enable:
        set_emergency_disabled(False)
        record_audit_event(
            session=session,
            event_type="emergency_disable_cleared",
            action="clear_emergency_disable",
            actor="operator_api",
            details={
                "emergency_disabled": False,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            },
        )
        return {
            "emergency_disabled": False,
            "status": "Mitigation safety gate re-enabled.",
        }

    set_emergency_disabled(True)
    repo = MitigationRepository(session)
    active = repo.get_active_or_simulated()

    cancelled_count = len(active)
    now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if active:
        # Perform single batch update instead of sequential loop commits
        from sqlalchemy import update

        from app.storage.models import MitigationModel

        action_ids = [act.action_id for act in active]
        session.execute(
            update(MitigationModel)
            .where(MitigationModel.action_id.in_(action_ids))
            .values(
                status="cancelled",
                cancelled_at=now_ts,
                updated_at=now_ts,
            )
        )
        session.commit()

    record_audit_event(
        session=session,
        event_type="emergency_disable_activated",
        action="emergency_disable",
        actor="operator_api",
        details={
            "cancelled_actions_count": cancelled_count,
            "emergency_disabled": True,
            "timestamp": now_ts,
        },
    )

    return {
        "emergency_disabled": True,
        "cancelled_actions_count": cancelled_count,
        "status": "All mitigation actions have been halted.",
    }
