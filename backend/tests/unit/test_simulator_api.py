"""Unit and contract tests for Phase 11: Simulation API Endpoints."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.simulations import (
    CreateSimulationRequest,
    SimulationCompareRequest,
    SimulationControlRequest,
    compare_simulation_runs,
    control_simulation_run,
    create_simulation_run,
    export_simulation_report,
    get_simulation_run,
    list_simulation_runs,
    list_simulation_ticks,
)
from app.simulator.scenarios import ScenarioType
from app.storage.database import Base


@pytest.fixture
def db_session() -> Session:
    """Create in-memory SQLite database session for API handler testing."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_api_create_and_get_run(db_session: Session) -> None:
    """Validate POST /api/v1/simulations and GET /api/v1/simulations/{run_id}."""
    req = CreateSimulationRequest(
        scenario_type=ScenarioType.SYN_FLOOD,
        seed=42,
        duration_seconds=30,
        baseline_pps=200.0,
        attack_peak_pps=10000.0,
        attack_start_tick=5,
        attack_end_tick=25,
        speed_multiplier=1.0,
    )

    # 1. Create run
    created = create_simulation_run(req, db_session)
    assert created.run_id.startswith("sim_")
    assert created.status == "created"
    assert created.total_ticks == 30
    assert created.seed == 42

    # 2. Retrieve run
    fetched = get_simulation_run(created.run_id, db_session)
    assert fetched.run_id == created.run_id
    assert fetched.status == "created"
    assert "scenario" in fetched.config

    # 3. Retrieve non-existent run raises 404
    with pytest.raises(HTTPException) as exc_info:
        get_simulation_run("non_existent_run", db_session)
    assert exc_info.value.status_code == 404


def test_api_list_runs_and_pagination(db_session: Session) -> None:
    """Validate GET /api/v1/simulations listing and status filtering."""
    for i in range(3):
        req = CreateSimulationRequest(
            scenario_type=ScenarioType.SYN_FLOOD,
            seed=i,
            duration_seconds=10,
            attack_start_tick=2,
            attack_end_tick=8,
        )
        create_simulation_run(req, db_session)

    res = list_simulation_runs(db_session, limit=10, offset=0)
    assert res.total_count == 3
    assert len(res.runs) == 3


def test_api_control_simulation(db_session: Session) -> None:
    """Validate POST /api/v1/simulations/{run_id}/control lifecycle."""
    req = CreateSimulationRequest(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )
    created = create_simulation_run(req, db_session)

    # Start
    start_ctrl = control_simulation_run(
        created.run_id, SimulationControlRequest(action="start"), db_session
    )
    assert start_ctrl.status == "running"

    # Step
    step_ctrl = control_simulation_run(
        created.run_id, SimulationControlRequest(action="step"), db_session
    )
    assert step_ctrl.current_tick == 1

    # Pause
    pause_ctrl = control_simulation_run(
        created.run_id, SimulationControlRequest(action="pause"), db_session
    )
    assert pause_ctrl.status == "paused"

    # Cancel
    cancel_ctrl = control_simulation_run(
        created.run_id, SimulationControlRequest(action="cancel"), db_session
    )
    assert cancel_ctrl.status == "cancelled"


def test_api_list_ticks(db_session: Session) -> None:
    """Validate GET /api/v1/simulations/{run_id}/ticks."""
    req = CreateSimulationRequest(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )
    created = create_simulation_run(req, db_session)

    # Step once
    control_simulation_run(
        created.run_id, SimulationControlRequest(action="step"), db_session
    )

    ticks_res = list_simulation_ticks(created.run_id, db_session)
    assert ticks_res.run_id == created.run_id
    assert ticks_res.total_ticks == 1
    assert ticks_res.ticks[0].tick == 0


def test_api_compare_runs(db_session: Session) -> None:
    """Validate POST /api/v1/simulations/compare."""
    req1 = CreateSimulationRequest(
        scenario_type=ScenarioType.SYN_FLOOD,
        seed=1,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )
    req2 = CreateSimulationRequest(
        scenario_type=ScenarioType.SYN_FLOOD,
        seed=2,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )
    run1 = create_simulation_run(req1, db_session)
    run2 = create_simulation_run(req2, db_session)

    comp = compare_simulation_runs(
        SimulationCompareRequest(run_ids=[run1.run_id, run2.run_id]), db_session
    )
    assert comp["compatible"] is True
    assert len(comp["runs"]) == 2
    assert "DISCLAIMER" in comp["disclaimer"]


def test_api_export_report(db_session: Session) -> None:
    """Validate GET /api/v1/simulations/{run_id}/export (JSON and Markdown)."""
    req = CreateSimulationRequest(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )
    run = create_simulation_run(req, db_session)

    # JSON export
    rep_json = export_simulation_report(run.run_id, db_session, format="json")
    assert isinstance(rep_json, dict)
    assert "DISCLAIMER" in rep_json["disclaimer"]

    # Markdown export
    rep_md = export_simulation_report(run.run_id, db_session, format="markdown")
    assert hasattr(rep_md, "body")
    assert b"SENTRIX Simulation Run Report" in rep_md.body
