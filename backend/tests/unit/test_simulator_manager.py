"""Unit tests for Phase 10: Virtual Clock, Resumable Run Manager, Resource Bounds, Comparison, and Export."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.simulator.manager import (
    ConcurrencyLimitExceededError,
    IncompatibleRunComparisonError,
    InvalidControlTransitionError,
    SimulationRunManager,
)
from app.simulator.scenarios import ScenarioConfig, ScenarioType
from app.storage.database import Base
from app.storage.repositories import ObservationRepository


@pytest.fixture
def db_session() -> Session:
    """Create a temporary in-memory SQLite database session for unit testing."""
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


# ==============================================================================
# 10.1 & 10.2: Run Creation, Virtual Clock Controls, and Single Step
# ==============================================================================


def test_create_run_and_speed_validation(db_session: Session) -> None:
    """Validate run creation, speed multiplier checks, and duration limits."""
    manager = SimulationRunManager(db_session)
    cfg = ScenarioConfig(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=30,
        attack_start_tick=5,
        attack_end_tick=20,
    )

    # Valid run creation
    run = manager.create_run(cfg, speed_multiplier=10.0)
    assert run.run_id.startswith("sim_")
    assert run.status == "created"
    assert run.speed_multiplier == 10.0
    assert run.current_tick == 0
    assert run.total_ticks == 30

    # Invalid speed multiplier
    with pytest.raises(ValueError, match="Invalid speed multiplier"):
        manager.create_run(cfg, speed_multiplier=5.0)

    # Exceeding max duration ticks (300)
    with pytest.raises(ValidationError):
        ScenarioConfig(
            scenario_type=ScenarioType.SYN_FLOOD,
            duration_seconds=500,
            attack_end_tick=400,
        )


def test_run_lifecycle_transitions(db_session: Session) -> None:
    """Test start, pause, resume, cancel, and reset transitions."""
    manager = SimulationRunManager(db_session)
    cfg = ScenarioConfig(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )
    run = manager.create_run(cfg)

    # 1. Start run
    started = manager.start_or_resume_run(run.run_id)
    assert started.status == "running"

    # 2. Pause run
    paused = manager.pause_run(run.run_id)
    assert paused.status == "paused"

    # Pausing a non-running run must fail
    with pytest.raises(InvalidControlTransitionError):
        manager.pause_run(run.run_id)

    # 3. Resume run
    resumed = manager.start_or_resume_run(run.run_id)
    assert resumed.status == "running"

    # 4. Cancel run
    cancelled = manager.cancel_run(run.run_id)
    assert cancelled.status == "cancelled"

    # Resuming a cancelled run must fail
    with pytest.raises(InvalidControlTransitionError):
        manager.start_or_resume_run(run.run_id)

    # 5. Reset run back to tick 0 / created
    reset_run = manager.reset_run(run.run_id)
    assert reset_run.status == "created"
    assert reset_run.current_tick == 0


def test_single_step_execution_and_auto_completion(db_session: Session) -> None:
    """Executing single steps advances ticks, persists metrics, and computes scorecard at end."""
    manager = SimulationRunManager(db_session)
    cfg = ScenarioConfig(
        scenario_type=ScenarioType.SYN_FLOOD,
        target_ip="192.168.10.50",
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )
    run = manager.create_run(cfg)

    for t in range(9):
        run, res = manager.execute_single_step(run.run_id)
        assert res is not None
        assert res.tick == t
        assert run.current_tick == t + 1
        assert run.status == "created"
        observation = ObservationRepository(db_session).list_recent(limit=1)[0]
        assert observation.target_ip == "192.168.10.50"

    run, res9 = manager.execute_single_step(run.run_id)
    assert res9 is not None
    assert res9.tick == 9
    assert run.current_tick == 10
    assert run.status == "completed"
    assert run.scorecard_json is not None

    scorecard_dict = json.loads(run.scorecard_json)
    assert scorecard_dict["total_ticks"] == 10


# ==============================================================================
# 10.3 & 10.4: Recovery, Concurrency Limits, and Retention
# ==============================================================================


def test_interruption_recovery(db_session: Session) -> None:
    """Unfinished runs left in running/created state are marked interrupted on startup."""
    manager = SimulationRunManager(db_session)
    cfg = ScenarioConfig(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )

    run1 = manager.create_run(cfg)
    manager.start_or_resume_run(run1.run_id)

    # Simulate process crash / backend reboot
    interrupted_count = manager.repo.mark_interrupted_runs()
    assert interrupted_count >= 1

    reloaded = manager.repo.get_run(run1.run_id)
    assert reloaded.status == "interrupted"


def test_concurrency_limit_enforcement(db_session: Session) -> None:
    """Enforce MAX_CONCURRENT_RUNS = 2."""
    manager = SimulationRunManager(db_session)
    cfg = ScenarioConfig(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )

    run1 = manager.create_run(cfg)
    run2 = manager.create_run(cfg)
    run3 = manager.create_run(cfg)

    # Start 1 and 2 (permitted)
    manager.start_or_resume_run(run1.run_id)
    manager.start_or_resume_run(run2.run_id)

    # Starting 3 must raise ConcurrencyLimitExceededError
    with pytest.raises(ConcurrencyLimitExceededError):
        manager.start_or_resume_run(run3.run_id)

    # Pausing run1 frees up capacity
    manager.pause_run(run1.run_id)
    started3 = manager.start_or_resume_run(run3.run_id)
    assert started3.status == "running"


def test_retention_pruning(db_session: Session) -> None:
    """Old terminal runs are pruned when exceeding max retention."""
    manager = SimulationRunManager(db_session)
    cfg = ScenarioConfig(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )

    # Create 5 runs and mark them completed
    for _ in range(5):
        r = manager.create_run(cfg)
        manager.repo.update_run_status(r.run_id, "completed")

    assert manager.repo.count_runs() == 5

    # Enforce retention keep_max=3
    pruned = manager.repo.cleanup_old_runs(keep_max=3)
    assert pruned == 2
    assert manager.repo.count_runs() == 3


# ==============================================================================
# 10.5: Comparison and Export
# ==============================================================================


def test_run_comparison_and_incompatibility_check(db_session: Session) -> None:
    """Validate comparison of compatible runs and rejection of incompatible ones."""
    manager = SimulationRunManager(db_session)
    cfg = ScenarioConfig(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )

    run1 = manager.create_run(cfg)
    run2 = manager.create_run(cfg)

    comparison = manager.compare_runs([run1.run_id, run2.run_id])
    assert comparison["compatible"] is True
    assert len(comparison["runs"]) == 2
    assert "DISCLAIMER" in comparison["disclaimer"]

    # Incompatibility test
    run2.schema_version = "2.0.0"  # mismatch
    db_session.commit()

    with pytest.raises(IncompatibleRunComparisonError):
        manager.compare_runs([run1.run_id, run2.run_id])


def test_export_report_formats(db_session: Session) -> None:
    """Ensure JSON and Markdown exports include mandatory synthetic disclaimer and metadata."""
    manager = SimulationRunManager(db_session)
    cfg = ScenarioConfig(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=10,
        attack_start_tick=2,
        attack_end_tick=8,
    )
    run = manager.create_run(cfg)

    # JSON export
    json_rep = manager.export_run_report(run.run_id, export_format="json")
    assert isinstance(json_rep, dict)
    assert "DISCLAIMER" in json_rep["disclaimer"]
    assert json_rep["run_metadata"]["run_id"] == run.run_id

    # Markdown export
    md_rep = manager.export_run_report(run.run_id, export_format="markdown")
    assert isinstance(md_rep, str)
    assert "# SENTRIX Simulation Run Report" in md_rep
    assert "DISCLAIMER" in md_rep
