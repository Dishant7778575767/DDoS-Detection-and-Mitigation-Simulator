"""Unit tests for mitigation cancellation logic and virtual shield handling."""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.mitigations import cancel_mitigation
from app.storage.database import Base
from app.storage.repositories import MitigationRepository


@pytest.fixture
def test_db_session(tmp_path):
    db_file = tmp_path / "test_cancel.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session


def test_cancel_virtual_simulation_action_succeeds_without_404(test_db_session):
    """Virtual simulation mitigations synthesized during runs should cancel cleanly."""
    virtual_id = "sim_sim_4f98c5d2f1ab_t15"
    res = cancel_mitigation(action_id=virtual_id, session=test_db_session)
    assert res["status"] == "cancelled"
    assert res["action_id"] == virtual_id
    assert res["mode"] == "simulation"

    sim_act_id = "sim-act-42-a1b2c3"
    res2 = cancel_mitigation(action_id=sim_act_id, session=test_db_session)
    assert res2["status"] == "cancelled"
    assert res2["action_id"] == sim_act_id


def test_cancel_non_existent_real_action_raises_404(test_db_session):
    """Non-existent real action IDs must still return 404 NOT FOUND for security hardening."""
    with pytest.raises(HTTPException) as exc_info:
        cancel_mitigation(action_id="non_existent_act_999", session=test_db_session)
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_cancel_persisted_mitigation_and_idempotent_cancel(test_db_session):
    """Persisted mitigations transition to cancelled and repeated cancellation is idempotent."""
    repo = MitigationRepository(test_db_session)
    mit = repo.create(
        detection_id=None,
        target_ip="192.168.1.100",
        target_port=80,
        action_type="rate_limit",
        rate_limit_pps=5000,
        duration_seconds=60,
        status="simulated",
        mode="simulation",
    )

    # 1. First cancellation
    res = cancel_mitigation(action_id=mit.action_id, session=test_db_session)
    assert res["status"] == "cancelled"

    # Verify status in database
    refreshed = repo.get_by_action_id(mit.action_id)
    assert refreshed is not None
    assert refreshed.status == "cancelled"

    # 2. Second cancellation should succeed idempotently
    res2 = cancel_mitigation(action_id=mit.action_id, session=test_db_session)
    assert res2["status"] == "cancelled"
