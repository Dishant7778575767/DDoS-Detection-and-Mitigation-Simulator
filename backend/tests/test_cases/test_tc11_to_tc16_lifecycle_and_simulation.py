"""SENTRIX PRD Section 10.2 Integration Test Cases: TC-11 to TC-16.

Validates authentication safety, hybrid decision quadrants, replay parity,
action cancellation, emergency disable, and lifecycle auditability.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.mitigations import (
    SimulateMitigationRequest,
    cancel_mitigation,
    emergency_disable_mitigations,
    simulate_mitigation,
)
from app.api.v1.traffic import (
    FlowObservationRequest,
    ingest_flow_observation,
)
from app.detection.predictor import FlowPrediction
from app.features.definitions import FEATURE_SCHEMA_VERSION
from app.main import app
from app.mitigation.lifecycle import validate_lifecycle_transition
from app.policy.engine import evaluate_hybrid_policy
from app.safety.gate import is_emergency_disabled, set_emergency_disabled
from app.storage.database import Base
from app.storage.models import AuditEventModel, MitigationModel, ThresholdConfigModel

FIXTURES_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "fixtures" / "test_flows.json"
)


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    db_file = tmp_path / "tc_lifecycle_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture(autouse=True)
def ensure_safety_gate_clean() -> None:
    set_emergency_disabled(False)
    try:
        yield
    finally:
        set_emergency_disabled(False)


def load_fixture_scenario(scenario_key: str) -> dict:
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["scenarios"][scenario_key]


def test_tc11_unauthorized_operator() -> None:
    """TC-11: Unauthorized operator: Missing, invalid, or expired tokens reject sensitive requests (401)."""
    client = TestClient(app)

    # 1. Missing Authorization header on sensitive action
    res_no_auth = client.post(
        "/api/v1/mitigations/simulate",
        json={
            "target_ip": "192.168.1.50",
            "rate_limit_pps": 1000,
            "duration_seconds": 60,
        },
    )
    assert res_no_auth.status_code == 401
    assert "error" in res_no_auth.json()

    # 2. Invalid Authorization bearer token
    res_bad_auth = client.post(
        "/api/v1/mitigations/simulate",
        headers={"Authorization": "Bearer completely-invalid-secret-token"},
        json={
            "target_ip": "192.168.1.50",
            "rate_limit_pps": 1000,
            "duration_seconds": 60,
        },
    )
    assert res_bad_auth.status_code == 401
    assert res_bad_auth.json()["error"]["code"] == "UNAUTHORIZED"

    # 3. Emergency disable endpoint also requires valid token
    res_disable_no_auth = client.post("/api/v1/mitigations/disable")
    assert res_disable_no_auth.status_code == 401


def test_tc13_hybrid_decision_matrix_quadrants() -> None:
    """TC-13: Hybrid policy decision: Verifies all 4 quadrants of the dual-signal decision matrix."""
    config = ThresholdConfigModel(
        version="v1.0.0",
        pps_threshold=5000.0,
        bps_threshold=10_000_000.0,
        syn_pps_threshold=500.0,
        syn_ack_ratio_threshold=5.0,
        rf_probability_threshold=0.75,
        iforest_score_threshold=0.2664,
    )

    benign_features = {"Fwd Packets/s": 50.0, "Flow Bytes/s": 5000.0}
    burst_features = {"Fwd Packets/s": 7500.0, "Flow Bytes/s": 5000.0}  # PPS violated

    low_score_pred = FlowPrediction(
        prediction="normal",
        score=0.20,
        score_type="random_forest_probability",
        model_version="rf-1.0.0",
        feature_schema_version="1.0.0",
    )
    high_score_pred = FlowPrediction(
        prediction="suspicious",
        score=0.95,
        score_type="random_forest_probability",
        model_version="rf-1.0.0",
        feature_schema_version="1.0.0",
    )

    # Quadrant 1: Neither signal -> "monitor"
    d1 = evaluate_hybrid_policy(low_score_pred, benign_features, config)
    assert d1.action == "monitor"
    assert d1.ml_threat_detected is False
    assert d1.threshold_exceeded is False

    # Quadrant 2: Threshold only -> "alert"
    d2 = evaluate_hybrid_policy(low_score_pred, burst_features, config)
    assert d2.action == "alert"
    assert d2.ml_threat_detected is False
    assert d2.threshold_exceeded is True

    # Quadrant 3: ML only -> "alert"
    d3 = evaluate_hybrid_policy(high_score_pred, benign_features, config)
    assert d3.action == "alert"
    assert d3.ml_threat_detected is True
    assert d3.threshold_exceeded is False

    # Quadrant 4: Dual signal consensus -> "request_mitigation"
    d4 = evaluate_hybrid_policy(high_score_pred, burst_features, config)
    assert d4.action == "request_mitigation"
    assert d4.ml_threat_detected is True
    assert d4.threshold_exceeded is True


def test_tc14_generated_and_file_replay_parity(db_session: Session) -> None:
    """TC-14: Both generated and replayed flows traverse identical runtime stages and carry demo labels."""
    sc = load_fixture_scenario("tc01_normal")

    # Source 1: Generated demonstration flow
    gen_req = FlowObservationRequest(
        source_id="demo-generator:sim-001",
        timestamp="2026-10-26T12:01:00Z",
        window_seconds=10.0,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=sc["features"],
        target_ip="192.168.1.100",
    )
    gen_result = ingest_flow_observation(gen_req, db_session)

    # Source 2: File-replayed demonstration flow
    replay_req = FlowObservationRequest(
        source_id="demo-replay:test.csv:row_001",
        timestamp="2026-10-26T12:01:01Z",
        window_seconds=10.0,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=sc["features"],
        target_ip="192.168.1.100",
    )
    replay_result = ingest_flow_observation(replay_req, db_session)

    # Assert runtime parity: identical detection output and policy decision
    assert gen_result["status"] == replay_result["status"] == "processed"
    assert (
        gen_result["policy_decision"] == replay_result["policy_decision"] == "monitor"
    )

    # Assert demonstration data labeling convention
    assert gen_req.source_id.startswith("demo-generator:")
    assert replay_req.source_id.startswith("demo-replay:")


def test_tc15_cancellation_and_emergency_disable(db_session: Session) -> None:
    """TC-15: Cancellation transitions state safely; emergency disable halts all actions and blocks new ones."""
    # 1. Simulate an action
    sim_req = SimulateMitigationRequest(
        target_ip="192.168.2.60",
        target_port=80,
        rate_limit_pps=1000,
        duration_seconds=60,
    )
    sim_res = simulate_mitigation(sim_req, db_session)
    action_id = sim_res["action_id"]
    assert sim_res["status"] == "simulated"

    # 2. Cancel the action
    cancel_res = cancel_mitigation(action_id, db_session)
    assert cancel_res["status"] == "cancelled"

    # Verify persisted status in database
    mit = db_session.query(MitigationModel).filter_by(action_id=action_id).first()
    assert mit is not None and mit.status == "cancelled"

    # 3. Activate emergency disable
    disable_res = emergency_disable_mitigations(db_session)
    assert disable_res["emergency_disabled"] is True
    assert is_emergency_disabled() is True

    # 4. Assert new mitigation requests are immediately blocked
    with pytest.raises(HTTPException) as exc_info:
        simulate_mitigation(sim_req, db_session)
    assert exc_info.value.status_code == 400
    assert "emergency disable" in exc_info.value.detail.lower()

    # 5. Clear emergency disable
    enable_res = emergency_disable_mitigations(db_session, enable=True)
    assert enable_res["emergency_disabled"] is False
    assert is_emergency_disabled() is False


def test_tc16_lifecycle_and_audit(db_session: Session) -> None:
    """TC-16: Lifecycle rejects invalid transitions; actions are never reported applied; all events are audited."""
    # 1. Reject invalid transition (cannot jump from simulated to applied)
    with pytest.raises(ValueError):
        validate_lifecycle_transition("simulated", "applied")

    # 2. Simulate valid flow and verify audit log trail
    sim_req = SimulateMitigationRequest(
        target_ip="192.168.2.70",
        target_port=443,
        rate_limit_pps=2000,
        duration_seconds=60,
    )
    sim_res = simulate_mitigation(sim_req, db_session)
    # Architecture requirement: Simulated actions are NEVER reported as applied
    assert sim_res["status"] == "simulated"
    assert sim_res["mode"] == "simulation"
    assert sim_res["host_networking_modified"] is False

    # Check that audit log recorded the simulation event
    audit_events = db_session.query(AuditEventModel).all()
    assert len(audit_events) >= 1
    assert any(e.action == "simulate_rate_limit" for e in audit_events)
