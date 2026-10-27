"""Simulation management endpoints for SENTRIX DDoS Simulator."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_auth
from app.simulator.manager import (
    ConcurrencyLimitExceededError,
    IncompatibleRunComparisonError,
    InvalidControlTransitionError,
    SimulationRunManager,
)
from app.simulator.scenarios import ScenarioConfig, ScenarioType
from app.simulator.victim import VirtualVictimConfig
from app.storage.database import get_db_session

router = APIRouter(
    prefix="/simulations",
    tags=["simulations"],
    dependencies=[Depends(require_api_auth)],
)


# ==============================================================================
# Request / Response Schemas
# ==============================================================================


class CreateSimulationRequest(BaseModel):
    scenario_type: ScenarioType = Field(
        default=ScenarioType.SYN_FLOOD, description="Type of DDoS scenario"
    )
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    duration_seconds: int = Field(default=60, ge=10, le=300)
    baseline_pps: float = Field(default=200.0, ge=10.0, le=50000.0)
    attack_peak_pps: float = Field(default=10000.0, ge=100.0, le=500000.0)
    attack_start_tick: int = Field(default=10, ge=0)
    attack_end_tick: int = Field(default=50, ge=0)
    target_ip: str = Field(default="192.168.1.100")
    target_port: int = Field(default=80, ge=1, le=65535)
    victim: VirtualVictimConfig = Field(default_factory=VirtualVictimConfig)
    speed_multiplier: float = Field(default=1.0)


class SimulationRunSummary(BaseModel):
    run_id: str
    scenario_type: str
    status: str
    seed: int
    total_ticks: int
    current_tick: int
    speed_multiplier: float
    created_at: str
    updated_at: str


class SimulationRunResponse(BaseModel):
    run_id: str
    scenario_type: str
    status: str
    seed: int
    total_ticks: int
    current_tick: int
    speed_multiplier: float
    config: dict[str, Any]
    scorecard: dict[str, Any] | None
    created_at: str
    updated_at: str
    completed_at: str | None


class SimulationListResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    runs: list[SimulationRunSummary]


class SimulationControlRequest(BaseModel):
    action: Literal["start", "pause", "resume", "step", "cancel", "reset"]


class SimulationControlResponse(BaseModel):
    run_id: str
    status: str
    current_tick: int
    message: str


class SimulationTickItem(BaseModel):
    tick: int
    offered_legit_pps: float
    offered_attack_pps: float
    served_legit_pps: float
    dropped_legit_pps: float
    dropped_attack_pps: float
    latency_ms: float
    availability_pct: float
    prediction: str
    policy_action: str
    active_mitigations_count: int
    timestamp: str


class SimulationTicksResponse(BaseModel):
    run_id: str
    total_ticks: int
    ticks: list[SimulationTickItem]


class SimulationCompareRequest(BaseModel):
    run_ids: list[str] = Field(..., min_length=2, max_length=5)


# ==============================================================================
# Endpoints
# ==============================================================================


@router.post(
    "", response_model=SimulationRunResponse, status_code=status.HTTP_201_CREATED
)
def create_simulation_run(
    req: CreateSimulationRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> SimulationRunResponse:
    """Create and persist a new synthetic DDoS simulation run."""
    manager = SimulationRunManager(session)
    try:
        scenario_cfg = ScenarioConfig(
            scenario_type=req.scenario_type,
            seed=req.seed,
            duration_seconds=req.duration_seconds,
            baseline_pps=req.baseline_pps,
            attack_peak_pps=req.attack_peak_pps,
            attack_start_tick=req.attack_start_tick,
            attack_end_tick=req.attack_end_tick,
            target_ip=req.target_ip,
            target_port=req.target_port,
        )
        run = manager.create_run(
            config=scenario_cfg,
            victim_config=req.victim,
            speed_multiplier=req.speed_multiplier,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    cfg_dict = json.loads(run.config_json)
    sc_dict = json.loads(run.scorecard_json) if run.scorecard_json else None

    return SimulationRunResponse(
        run_id=run.run_id,
        scenario_type=run.scenario_type,
        status=run.status,
        seed=run.seed,
        total_ticks=run.total_ticks,
        current_tick=run.current_tick,
        speed_multiplier=run.speed_multiplier,
        config=cfg_dict,
        scorecard=sc_dict,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


@router.get("", response_model=SimulationListResponse)
def list_simulation_runs(
    session: Annotated[Session, Depends(get_db_session)],
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SimulationListResponse:
    """List simulation runs with optional status filtering and pagination."""
    manager = SimulationRunManager(session)
    runs = manager.repo.list_runs(status=status, limit=limit, offset=offset)
    total_count = manager.repo.count_runs(status=status)

    summaries = [
        SimulationRunSummary(
            run_id=r.run_id,
            scenario_type=r.scenario_type,
            status=r.status,
            seed=r.seed,
            total_ticks=r.total_ticks,
            current_tick=r.current_tick,
            speed_multiplier=r.speed_multiplier,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in runs
    ]

    return SimulationListResponse(
        total_count=total_count,
        limit=limit,
        offset=offset,
        runs=summaries,
    )


@router.get("/{run_id}", response_model=SimulationRunResponse)
def get_simulation_run(
    run_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> SimulationRunResponse:
    """Retrieve detailed state, configuration, and scorecard of a simulation run."""
    manager = SimulationRunManager(session)
    run = manager.repo.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation run '{run_id}' not found",
        )

    cfg_dict = json.loads(run.config_json)
    sc_dict = json.loads(run.scorecard_json) if run.scorecard_json else None

    return SimulationRunResponse(
        run_id=run.run_id,
        scenario_type=run.scenario_type,
        status=run.status,
        seed=run.seed,
        total_ticks=run.total_ticks,
        current_tick=run.current_tick,
        speed_multiplier=run.speed_multiplier,
        config=cfg_dict,
        scorecard=sc_dict,
        created_at=run.created_at,
        updated_at=run.updated_at,
        completed_at=run.completed_at,
    )


@router.post("/{run_id}/control", response_model=SimulationControlResponse)
def control_simulation_run(
    run_id: str,
    req: SimulationControlRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> SimulationControlResponse:
    """Execute virtual-clock lifecycle controls (start, pause, resume, step, cancel, reset)."""
    manager = SimulationRunManager(session)
    try:
        if req.action in ("start", "resume"):
            run = manager.start_or_resume_run(run_id)
            msg = f"Simulation transitioned to {run.status}"
        elif req.action == "pause":
            run = manager.pause_run(run_id)
            msg = "Simulation paused"
        elif req.action == "cancel":
            run = manager.cancel_run(run_id)
            msg = "Simulation cancelled"
        elif req.action == "reset":
            run = manager.reset_run(run_id)
            msg = "Simulation reset to tick 0"
        elif req.action == "step":
            run, _ = manager.execute_single_step(run_id)
            msg = f"Simulation stepped to tick {run.current_tick}"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action '{req.action}'",
            )
    except ConcurrencyLimitExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)
        )
    except (InvalidControlTransitionError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return SimulationControlResponse(
        run_id=run.run_id,
        status=run.status,
        current_tick=run.current_tick,
        message=msg,
    )


@router.get("/{run_id}/ticks", response_model=SimulationTicksResponse)
def list_simulation_ticks(
    run_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 300,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SimulationTicksResponse:
    """Retrieve chronologically ordered committed ticks for a run."""
    manager = SimulationRunManager(session)
    run = manager.repo.get_run(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation run '{run_id}' not found",
        )

    ticks = manager.repo.list_ticks(run_id, limit=limit, offset=offset)
    items = [
        SimulationTickItem(
            tick=t.tick,
            offered_legit_pps=t.offered_legit_pps,
            offered_attack_pps=t.offered_attack_pps,
            served_legit_pps=t.served_legit_pps,
            dropped_legit_pps=t.dropped_legit_pps,
            dropped_attack_pps=t.dropped_attack_pps,
            latency_ms=t.latency_ms,
            availability_pct=t.availability_pct,
            prediction=t.prediction,
            policy_action=t.policy_action,
            active_mitigations_count=t.active_mitigations_count,
            timestamp=t.timestamp,
        )
        for t in ticks
    ]

    return SimulationTicksResponse(
        run_id=run.run_id,
        total_ticks=len(items),
        ticks=items,
    )


@router.post("/compare")
def compare_simulation_runs(
    req: SimulationCompareRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """Compare multiple simulation runs side-by-side with compatibility checks."""
    manager = SimulationRunManager(session)
    try:
        return manager.compare_runs(req.run_ids)
    except IncompatibleRunComparisonError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{run_id}/export")
def export_simulation_report(
    run_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    format: Annotated[str, Query(pattern="^(json|markdown|csv)$")] = "json",
    token: Annotated[str | None, Query(alias="token")] = None,
) -> Any:
    """Export complete simulation report with prominent synthetic-only disclaimer."""
    manager = SimulationRunManager(session)
    try:
        report = manager.export_run_report(run_id, export_format=format)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    if format.lower() == "markdown":
        return Response(content=report, media_type="text/markdown")
    if format.lower() == "csv":
        return Response(
            content=report,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="simulation_{run_id}.csv"'
            },
        )
    return report
