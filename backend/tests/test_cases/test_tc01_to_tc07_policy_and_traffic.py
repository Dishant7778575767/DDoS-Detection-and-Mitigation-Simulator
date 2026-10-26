"""SENTRIX PRD Section 10.2 Integration Test Cases: TC-01 to TC-07.

Validates core traffic detection, dual-signal policy, allowlist protection,
schema sanitization, and alert cooldown behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.mitigations import (
    SimulateMitigationRequest,
    simulate_mitigation,
)
from app.api.v1.traffic import (
    FlowObservationRequest,
    ingest_flow_observation,
)
from app.features.definitions import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from app.policy.cooldown import AlertCooldownManager
from app.safety.gate import set_emergency_disabled
from app.storage.database import Base

FIXTURES_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "fixtures" / "test_flows.json"
)


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    db_file = tmp_path / "tc_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session


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


def test_tc01_normal_traffic(db_session: Session) -> None:
    """TC-01: Neither signal indicates a threat; monitoring continues and no mitigation is requested."""
    sc = load_fixture_scenario("tc01_normal")
    req = FlowObservationRequest(
        source_id=sc["source_id"],
        timestamp="2026-10-26T12:00:00Z",
        window_seconds=sc["window_seconds"],
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=sc["features"],
        target_ip=sc["target_ip"],
    )

    result = ingest_flow_observation(req, db_session)
    assert result["status"] == "processed"
    assert result["policy_decision"] == "monitor"
    assert result["alert_id"] is None
    assert result["mitigation_action_id"] is None


def test_tc02_abnormal_burst(db_session: Session) -> None:
    """TC-02: Abnormal burst: Threshold exceeded without ML attack payload. Single-signal alert only."""
    sc = load_fixture_scenario("tc02_abnormal_burst")
    req = FlowObservationRequest(
        source_id=sc["source_id"],
        timestamp="2026-10-26T12:00:10Z",
        window_seconds=sc["window_seconds"],
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=sc["features"],
        target_ip=sc["target_ip"],
    )

    result = ingest_flow_observation(req, db_session)
    assert result["status"] == "processed"
    assert result["policy_decision"] == "alert"
    assert result["alert_id"] is not None
    assert result["mitigation_action_id"] is None


def test_tc03_suspected_syn_flood(db_session: Session) -> None:
    """TC-03: Suspected SYN flood: Both signals trigger. Eligible to request mitigation."""
    sc = load_fixture_scenario("tc03_syn_flood")
    req = FlowObservationRequest(
        source_id=sc["source_id"],
        timestamp="2026-10-26T12:00:20Z",
        window_seconds=sc["window_seconds"],
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=sc["features"],
        target_ip=sc["target_ip"],
    )

    result = ingest_flow_observation(req, db_session)
    assert result["status"] == "processed"
    assert result["policy_decision"] == "request_mitigation"
    assert result["alert_id"] is not None
    assert result["mitigation_action_id"] is not None


def test_tc04_threshold_signal_only(db_session: Session) -> None:
    """TC-04: Threshold signal only: High PPS alone must NEVER request mitigation."""
    sc = load_fixture_scenario("tc04_threshold_only")
    req = FlowObservationRequest(
        source_id=sc["source_id"],
        timestamp="2026-10-26T12:00:30Z",
        window_seconds=sc["window_seconds"],
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=sc["features"],
        target_ip=sc["target_ip"],
    )

    result = ingest_flow_observation(req, db_session)
    assert result["status"] == "processed"
    assert result["policy_decision"] == "alert"
    # Critical architecture invariant: single signal can NEVER request mitigation
    assert result["mitigation_action_id"] is None


def test_tc05_invalid_feature_values_and_schema(db_session: Session) -> None:
    """TC-05: Invalid feature values or schema: Ingestion rejects malformed/out-of-bounds input."""
    # 1. Missing required features
    partial_features = {"Fwd Packets/s": 100.0}
    with pytest.raises((HTTPException, ValueError)):  # Schema validation rejection
        req_missing = FlowObservationRequest(
            source_id="sensor-bad",
            timestamp="2026-10-26T12:00:40Z",
            window_seconds=10.0,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            features=partial_features,
            target_ip="192.168.1.100",
        )
        ingest_flow_observation(req_missing, db_session)

    # 2. Unsupported feature schema version
    valid_features = {f: 10.0 for f in FEATURE_NAMES}
    with pytest.raises((HTTPException, ValueError)):
        req_bad_ver = FlowObservationRequest(
            source_id="sensor-bad",
            timestamp="2026-10-26T12:00:40Z",
            window_seconds=10.0,
            feature_schema_version="9.9.9",
            features=valid_features,
            target_ip="192.168.1.100",
        )
        ingest_flow_observation(req_bad_ver, db_session)


def test_tc06_protected_management_target(db_session: Session) -> None:
    """TC-06: Protected management target: Safety gate denies actions against protected IP ranges."""
    # 127.0.0.1 (Loopback), ::1 (IPv6 Loopback), 192.168.1.1 (Gateway/allowlisted) must be denied
    protected_ips = ["127.0.0.1", "::1", "192.168.1.1"]

    for prot_ip in protected_ips:
        req = SimulateMitigationRequest(
            target_ip=prot_ip,
            target_port=80,
            rate_limit_pps=1000,
            duration_seconds=60,
        )
        with pytest.raises(HTTPException) as exc_info:
            simulate_mitigation(req, db_session)

        assert exc_info.value.status_code == 400
        assert (
            "protected" in exc_info.value.detail.lower()
            or "allowlist" in exc_info.value.detail.lower()
        )


def test_tc07_repeated_alerts_and_cooldown() -> None:
    """TC-07: Repeated alerts: Cooldown and deduplication throttle duplicate triggers."""
    manager = AlertCooldownManager(cooldown_seconds=60.0)

    # First alert for target
    is_suppressed, _ = manager.check_and_update("192.168.1.200", 1000.0)
    assert is_suppressed is False  # Allowed to trigger

    # Immediate second alert for same target (within 60s cooldown)
    is_suppressed2, reason = manager.check_and_update("192.168.1.200", 1010.0)
    assert is_suppressed2 is True  # Suppressed by cooldown
    assert "cooldown" in reason.lower()

    # Different target is NOT suppressed
    is_suppressed_other, _ = manager.check_and_update("192.168.1.201", 1010.0)
    assert is_suppressed_other is False
