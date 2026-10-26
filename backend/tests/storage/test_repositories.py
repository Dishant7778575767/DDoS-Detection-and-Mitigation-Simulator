"""Unit tests for database storage repositories."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.storage.database import Base
from app.storage.repositories import (
    AlertRepository,
    AuditRepository,
    DetectionRepository,
    MitigationRepository,
    ObservationRepository,
    ThresholdConfigRepository,
)


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session


def test_observation_repository(db_session: Session) -> None:
    repo = ObservationRepository(db_session)
    obs = repo.create(
        source_id="sensor-01",
        timestamp="2026-10-25T10:00:00Z",
        window_seconds=10.0,
        feature_schema_version="1.0.0",
        features={"Flow Bytes/s": 5000.0},
    )
    assert obs.id is not None
    assert obs.source_id == "sensor-01"

    fetched = repo.get_by_id(obs.id)
    assert fetched is not None
    assert fetched.feature_schema_version == "1.0.0"

    recent = repo.list_recent(limit=10)
    assert len(recent) == 1


def test_detection_and_alert_repositories(db_session: Session) -> None:
    det_repo = DetectionRepository(db_session)
    alert_repo = AlertRepository(db_session)

    detection = det_repo.create(
        event_id="evt_test_01",
        observation_id=None,
        model_version="rf-1.0.0",
        feature_schema_version="1.0.0",
        prediction="suspicious",
        score_type="random_forest_probability",
        score=0.95,
        traffic_threshold_exceeded=True,
        policy_decision="simulate_rate_limit",
        mitigation_mode="simulation",
        timestamp="2026-10-25T10:00:00Z",
    )
    assert detection.id is not None
    assert detection.prediction == "suspicious"

    alert = alert_repo.create(
        detection_id=detection.id,
        severity="critical",
        title="DDoS attack detected",
        description="High packet rate and RF probability",
        source_id="sensor-01",
        timestamp="2026-10-25T10:00:00Z",
    )
    assert alert.id is not None
    assert alert.status == "active"

    alerts = alert_repo.list_filtered(severity="critical")
    assert len(alerts) == 1
    assert alert_repo.count_filtered(severity="critical") == 1


def test_mitigation_and_audit_repositories(db_session: Session) -> None:
    mit_repo = MitigationRepository(db_session)
    audit_repo = AuditRepository(db_session)

    mitigation = mit_repo.create(
        detection_id=None,
        target_ip="192.168.1.100",
        target_port=80,
        action_type="rate_limit",
        rate_limit_pps=1000,
        duration_seconds=60,
        status="proposed",
        mode="simulation",
    )
    assert mitigation.action_id.startswith("act_")
    assert mitigation.status == "proposed"

    updated = mit_repo.update_status(mitigation.action_id, "simulated")
    assert updated is not None
    assert updated.status == "simulated"

    active = mit_repo.get_active_or_simulated()
    assert len(active) == 1

    audit_entry = audit_repo.log(
        event_type="mitigation_state_transition",
        action="simulate",
        actor="safety_gate",
        details={"action_id": mitigation.action_id, "target": "192.168.1.100"},
    )
    assert audit_entry.id is not None
    assert audit_entry.action == "simulate"

    logs = audit_repo.list_filtered(event_type="mitigation_state_transition")
    assert len(logs) == 1


def test_threshold_config_repository(db_session: Session) -> None:
    repo = ThresholdConfigRepository(db_session)
    active = repo.get_active()
    assert active.is_active is True
    assert active.pps_threshold == 5000.0

    updated = repo.update(
        updated_by="admin",
        updates={"pps_threshold": 8000.0},
    )
    assert updated.pps_threshold == 8000.0
    assert updated.is_active is True

    # Check previous was marked inactive
    current = repo.get_active()
    assert current.id == updated.id
    assert current.pps_threshold == 8000.0

