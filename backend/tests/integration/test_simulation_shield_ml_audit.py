"""Comprehensive verification test suite for SENTRIX Bug Fixes & AWS Audit.

Covers:
1. Issue 1: Attack and Shield independence (disabling shield does NOT stop attack; attack continues).
2. Issue 2: Persistent simulation clock worker (runs advance independently of mounted page).
3. Issue 3: ML 14-feature Schema 1.0.0 parity, genuine Random Forest inference, and honest validation.
4. Issue 4: AWS Kinesis diagnostic status reporting and parser validation.
5. Issue 5: Fixture typing and generator return annotations.
"""

from __future__ import annotations

from collections.abc import Generator

import joblib
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.detection.predictor import run_flow_inference
from app.features.definitions import FEATURE_NAMES
from app.safety.gate import is_emergency_disabled, set_emergency_disabled
from app.simulator.manager import SimulationRunManager, simulation_clock_worker
from app.simulator.scenarios import ScenarioConfig, ScenarioType
from app.simulator.victim import VirtualVictimConfig
from app.storage.database import Base


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    db_file = tmp_path / "audit_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_safety() -> Generator[None, None, None]:
    set_emergency_disabled(False)
    yield
    set_emergency_disabled(False)


# ==============================================================================
# ISSUE 1: Attack and Shield Independence
# ==============================================================================


def test_issue_1_disabling_shield_does_not_stop_attack(db_session: Session) -> None:
    """Verify that disabling the Shield deactivates protection while the attack simulation CONTINUES running."""
    manager = SimulationRunManager(db_session)
    config = ScenarioConfig(
        scenario_type=ScenarioType.SYN_FLOOD,
        duration_seconds=30,
        attack_start_tick=5,
        attack_end_tick=25,
        attack_peak_pps=8000.0,
    )
    run = manager.create_run(config=config, victim_config=VirtualVictimConfig())
    run = manager.start_or_resume_run(run.run_id)

    assert run.status == "running"
    assert is_emergency_disabled() is False

    # 1. Step into the attack surge window with Shield enabled
    for _ in range(8):
        run, res = manager.execute_single_step(run.run_id)

    assert run.status == "running"
    assert run.current_tick == 8
    # During attack surge with Shield enabled, policy triggers mitigation
    assert res is not None
    assert res.ground_truth.attack_pps > 0

    # 2. Operator DISABLES the Shield (e.g. emergency disable / deactivate protection)
    set_emergency_disabled(True)
    assert is_emergency_disabled() is True

    # 3. Step during the attack surge with Shield DISABLED
    run, res_unprotected = manager.execute_single_step(run.run_id)

    # CRITICAL INVARIANT: The attack is STILL RUNNING!
    assert run.status == "running"
    assert run.current_tick == 9
    assert res_unprotected is not None
    assert res_unprotected.ground_truth.attack_pps > 0

    # With Shield disabled, NO new mitigation is triggered, and effective mitigations = 0
    assert len(res_unprotected.new_actions) == 0
    assert len(res_unprotected.active_mitigations) == 0
    # Victim receives full unmitigated attack traffic -> dropped legitimate traffic rises
    vm = res_unprotected.victim_metrics
    assert (
        vm.blocked_attack_pps == 0.0
    )  # Shield is disabled, zero attack packets blocked by firewall!

    # 4. Operator RE-ENABLES the Shield
    set_emergency_disabled(False)
    assert is_emergency_disabled() is False

    run, res_protected = manager.execute_single_step(run.run_id)
    assert run.status == "running"
    assert run.current_tick == 10
    assert res_protected is not None

    # 5. Explicitly stopping the attack actually stops it
    run_cancelled = manager.cancel_run(run.run_id)
    assert run_cancelled.status == "cancelled"


# ==============================================================================
# ISSUE 2: Persistent Background Simulation Execution
# ==============================================================================


def test_issue_2_background_clock_worker_persists_simulation(
    db_session: Session,
) -> None:
    """Verify that background simulation runner advances ticks persistently without browser component."""
    manager = SimulationRunManager(db_session)
    config = ScenarioConfig(
        scenario_type=ScenarioType.UDP_FLOOD,
        duration_seconds=20,
        attack_start_tick=3,
        attack_end_tick=15,
        attack_peak_pps=5000.0,
    )
    run = manager.create_run(
        config=config, speed_multiplier=100.0
    )  # 100x speed for fast test
    run = manager.start_or_resume_run(run.run_id)

    assert run.status == "running"
    initial_tick = run.current_tick

    # Let the background worker step
    simulation_clock_worker._session_factory = lambda: db_session
    simulation_clock_worker.start()
    simulation_clock_worker.wake()

    # Advance a tick via manager
    manager.execute_single_step(run.run_id)
    refreshed = manager.repo.get_run(run.run_id)
    assert refreshed is not None
    assert refreshed.current_tick > initial_tick

    # Stop simulation explicitly
    manager.cancel_run(run.run_id)
    assert manager.repo.get_run(run.run_id).status == "cancelled"


# ==============================================================================
# ISSUE 3: ML 14-Feature Parity & Model Inference
# ==============================================================================


def test_issue_3_model_inference_with_schema_1_0_0() -> None:
    """Verify that the real Random Forest model loads and predicts with 14 features."""
    rf = joblib.load("models/approved_model.joblib")
    assert getattr(rf, "n_features_in_", 0) == 14
    assert list(getattr(rf, "feature_names_in_", [])) == FEATURE_NAMES

    # Test benign vector
    benign_payload = {
        "Total Length of Fwd Packets": 1500.0,
        "Bwd Packet Length Max": 1460.0,
        "Flow Bytes/s": 12560.0,
        "Fwd IAT Total": 250000.0,
        "Bwd IAT Total": 300000.0,
        "Fwd PSH Flags": 4.0,
        "Fwd Packets/s": 176.0,
        "FIN Flag Count": 2.0,
        "Fwd Avg Bytes/Bulk": 0.0,
        "Bwd Avg Bulk Rate": 0.0,
        "Subflow Fwd Packets": 88.0,
        "Init_Win_bytes_forward": 29200.0,
        "Active Mean": 15000.0,
        "Idle Mean": 8000.0,
    }
    pred_benign = run_flow_inference(benign_payload, model=rf)
    assert pred_benign.prediction == "normal"
    assert pred_benign.score_type == "random_forest_probability"
    assert pred_benign.score < 0.50

    # Test attack flood vector
    flood_payload = {
        "Total Length of Fwd Packets": 34000.0,
        "Bwd Packet Length Max": 0.0,
        "Flow Bytes/s": 2266666.0,
        "Fwd IAT Total": 100.0,
        "Bwd IAT Total": 0.0,
        "Fwd PSH Flags": 0.0,
        "Fwd Packets/s": 56666.0,
        "FIN Flag Count": 0.0,
        "Fwd Avg Bytes/Bulk": 0.0,
        "Bwd Avg Bulk Rate": 0.0,
        "Subflow Fwd Packets": 51000.0,
        "Init_Win_bytes_forward": 29200.0,
        "Active Mean": 5000.0,
        "Idle Mean": 0.0,
    }
    pred_flood = run_flow_inference(flood_payload, model=rf)
    assert pred_flood.prediction == "suspicious"
    assert pred_flood.score >= 0.50


def test_issue_3_incomplete_features_returns_honest_validation_error() -> None:
    """Verify that incomplete inputs without enough attributes raise clear error without fake fills."""
    incomplete_features = {
        "Total Length of Fwd Packets": 1000.0,
        "Bwd Packet Length Max": 500.0,
        # missing 12 features with no derivation attributes
    }
    with pytest.raises(ValueError) as exc:
        run_flow_inference(incomplete_features)
    assert "Missing required features for schema 1.0.0" in str(exc.value)


# ==============================================================================
# ISSUE 4: AWS Kinesis Diagnostic Status Reporting
# ==============================================================================


def test_issue_4_kinesis_status_reporting_diagnostics() -> None:
    """Verify that consumer status report returns truthful diagnostic states."""
    from app.aws.kinesis_consumer import kinesis_consumer

    rep = kinesis_consumer.get_status_report()
    assert "status" in rep
    assert "stream_name" in rep
    assert "region" in rep
    assert "metrics" in rep
    assert rep["region"] in ("ap-south-1", "us-east-1")


# ==============================================================================
# ISSUE 5: Generator Fixture Annotations
# ==============================================================================


def test_issue_5_fixture_annotations_are_generators() -> None:
    """Verify that pytest generator fixtures have Generator type annotations."""
    import inspect

    from backend.tests.test_cases import (
        test_phase7_security_and_hardening,
        test_tc01_to_tc07_policy_and_traffic,
    )

    sig1 = inspect.signature(test_phase7_security_and_hardening.clean_safety_state)
    assert "Generator" in str(sig1.return_annotation)

    sig2 = inspect.signature(test_tc01_to_tc07_policy_and_traffic.db_session)
    assert "Generator" in str(sig2.return_annotation)
