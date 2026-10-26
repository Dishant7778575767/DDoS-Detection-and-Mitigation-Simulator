"""Unit tests covering all 14 PRD Section 7 API endpoint contracts directly."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.v1.alerts import list_alerts
from app.api.v1.audit import get_audit_records
from app.api.v1.config import (
    UpdateThresholdConfigRequest,
    get_threshold_configuration,
    update_threshold_configuration,
)
from app.api.v1.detection import AnalyzeFlowRequest, analyze_flow_features
from app.api.v1.health import health_check
from app.api.v1.mitigations import (
    SimulateMitigationRequest,
    cancel_mitigation,
    emergency_disable_mitigations,
    list_mitigations,
    simulate_mitigation,
)
from app.api.v1.models import get_model_metrics, get_models
from app.api.v1.traffic import get_traffic_summary, ingest_flow_observation
from app.core.config import get_settings
from app.features.definitions import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from app.ingestion.schemas import FlowObservationRequest
from app.storage.database import Base


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    db_file = tmp_path / "test_api.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session


def test_1_health_endpoint() -> None:
    """Contract: GET /api/v1/health returns status ok."""
    settings = get_settings()
    res = health_check(settings)
    assert res.status == "ok"


def test_2_and_3_models_endpoints() -> None:
    """Contract: GET /api/v1/models and GET /api/v1/models/metrics."""
    models_res = get_models()
    assert models_res.approved_model == "rf-1.0.0"
    assert models_res.schema_version == FEATURE_SCHEMA_VERSION
    assert len(models_res.models) == 2

    metrics_res = get_model_metrics()
    assert metrics_res["schema_version"] == FEATURE_SCHEMA_VERSION
    assert "rf_metrics" in metrics_res
    assert "iforest_metrics" in metrics_res


def test_4_and_5_traffic_endpoints(db_session: Session) -> None:
    """Contract: POST /api/v1/traffic/flows and GET /api/v1/traffic/summary."""
    sample_features = {name: 100.0 for name in FEATURE_NAMES}
    req = FlowObservationRequest(
        source_id="sensor-01",
        timestamp="2026-10-25T10:00:00Z",
        window_seconds=10.0,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=sample_features,
        target_ip="192.168.1.150",
    )
    ingest_res = ingest_flow_observation(req, db_session)
    assert ingest_res["status"] == "processed"
    assert ingest_res["event_id"].startswith("evt_")

    summary_res = get_traffic_summary()
    assert summary_res.window_duration_seconds == 10.0
    assert summary_res.packet_rate >= 0.0


def test_6_detection_analyze_endpoint(db_session: Session) -> None:
    """Contract: POST /api/v1/detection/analyze."""
    sample_features = {name: 50.0 for name in FEATURE_NAMES}
    req = AnalyzeFlowRequest(
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        features=sample_features,
    )
    res = analyze_flow_features(req, db_session)
    assert res.model_version == "rf-1.0.0"
    assert res.prediction in ("normal", "suspicious")
    assert 0.0 <= res.score <= 1.0


def test_7_alerts_endpoint(db_session: Session) -> None:
    """Contract: GET /api/v1/alerts."""
    res = list_alerts(db_session, severity=None, status=None, limit=50, offset=0)
    assert res.total_count >= 0
    assert isinstance(res.alerts, list)


def test_8_to_11_mitigations_endpoints(db_session: Session) -> None:
    """Contract: GET /api/v1/mitigations, POST simulate, cancel, disable."""
    # 1. Simulate
    sim_req = SimulateMitigationRequest(
        target_ip="10.0.0.50",
        target_port=80,
        rate_limit_pps=1000,
        duration_seconds=60,
    )
    sim_res = simulate_mitigation(sim_req, db_session)
    assert sim_res["status"] == "simulated"
    action_id = sim_res["action_id"]

    # 2. List
    list_res = list_mitigations(db_session, status_filter=None, mode_filter=None, limit=50, offset=0)
    assert list_res.total_count >= 1

    # 3. Cancel
    cancel_res = cancel_mitigation(action_id, db_session)
    assert cancel_res["status"] == "cancelled"

    # 4. Emergency disable
    disable_res = emergency_disable_mitigations(db_session)
    assert disable_res["emergency_disabled"] is True


def test_12_audit_endpoint(db_session: Session) -> None:
    """Contract: GET /api/v1/audit (JSON and CSV formats)."""
    # JSON format
    json_res = get_audit_records(db_session, event_type=None, format_type="json", limit=50, offset=0)
    assert isinstance(json_res, dict)
    assert "events" in json_res

    # CSV format
    csv_res = get_audit_records(db_session, event_type=None, format_type="csv", limit=50, offset=0)
    assert hasattr(csv_res, "body") or hasattr(csv_res, "content")


def test_13_and_14_config_thresholds_endpoints(db_session: Session) -> None:
    """Contract: GET /api/v1/config/thresholds and PATCH /api/v1/config/thresholds."""
    get_res = get_threshold_configuration(db_session)
    assert get_res.pps_threshold > 0.0

    update_req = UpdateThresholdConfigRequest(pps_threshold=7500.0)
    patch_res = update_threshold_configuration(update_req, db_session)
    assert patch_res.pps_threshold == 7500.0
