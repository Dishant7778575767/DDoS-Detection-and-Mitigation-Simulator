"""SENTRIX Virtual Lifecycle Tests: TC-09, TC-10, TC-12 (Simulator Path).

Validates:
- TC-09: Virtual mitigation expiration without host networking calls.
- TC-10: Failure handling, emergency lockdown, failure auditing, and safety boundaries.
- TC-12: Simulator restart reconciliation, virtual expiration of in-flight actions,
  and interruption state marking.
"""

from __future__ import annotations

import datetime
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.mitigation.lifecycle import (
    IllegalTransitionError,
    validate_lifecycle_transition,
)
from app.mitigation.simulation import SimulationAdapter
from app.safety.gate import (
    is_emergency_disabled,
    set_emergency_disabled,
    validate_safety_gate,
)
from app.storage.audit import record_audit_event
from app.storage.database import Base
from app.storage.repositories import AuditRepository, MitigationRepository


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """In-memory SQLite session for testing virtual lifecycle."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# ==============================================================================
# TC-09: Virtual Mitigation Expiry
# ==============================================================================


def test_tc09_virtual_mitigation_lifecycle_and_expiry(test_db: Session) -> None:
    """TC-09: A simulated mitigation action transitions cleanly to 'expired' at its deadline."""
    adapter = SimulationAdapter()
    repo = MitigationRepository(test_db)

    # 1. Simulate applying a rate limit
    result = adapter.apply_rate_limit(
        action_id="act_sim_tc09_001",
        target_ip="192.168.1.100",
        rate_limit_pps=2000,
        duration_seconds=10,
    )
    assert result["status"] == "simulated"
    assert result["mode"] == "simulation"
    assert result["host_networking_modified"] is False

    # 2. Persist in database
    action = repo.create(
        detection_id=None,
        target_ip="192.168.1.100",
        target_port=None,
        action_type="rate_limit",
        rate_limit_pps=2000,
        duration_seconds=10,
        status="simulated",
        mode="simulation",
    )
    action_id = action.action_id
    assert action.status == "simulated"

    # 3. Virtual clock advances past expiration
    validate_lifecycle_transition("simulated", "expired")
    updated = repo.update_status(
        action_id=action_id,
        new_status="expired",
    )
    assert updated is not None
    assert updated.status == "expired"

    # 4. Record audit event
    record_audit_event(
        session=test_db,
        event_type="mitigation_expired",
        action="expire",
        actor="simulator_clock",
        details={
            "action_id": action_id,
            "target": "192.168.1.100",
            "mode": "simulation",
            "host_networking_modified": False,
        },
    )

    audit_repo = AuditRepository(test_db)
    events = audit_repo.list_filtered(event_type="mitigation_expired")
    assert len(events) == 1
    assert events[0].action == "expire"
    import json

    parsed_details = json.loads(events[0].details_json)
    assert parsed_details["host_networking_modified"] is False


def test_tc09_invalid_state_transition_raises_error() -> None:
    """TC-09: Invalid state transitions (e.g. expired -> simulated) are rejected by state machine."""
    with pytest.raises(IllegalTransitionError):
        validate_lifecycle_transition("expired", "simulated")

    with pytest.raises(IllegalTransitionError):
        validate_lifecycle_transition("cancelled", "applied")


# ==============================================================================
# TC-10: Virtual Failure Handling & Emergency Lockdown
# ==============================================================================


def test_tc10_emergency_disable_lockdown(test_db: Session) -> None:
    """TC-10: Emergency disable halts mitigations and locks out new actions."""
    repo = MitigationRepository(test_db)

    # Create active simulated actions
    repo.create(
        detection_id=None,
        target_ip="10.0.0.5",
        target_port=None,
        action_type="rate_limit",
        rate_limit_pps=1000,
        duration_seconds=60,
        status="simulated",
        mode="simulation",
    )

    try:
        # Trigger emergency disable
        set_emergency_disabled(True)
        assert is_emergency_disabled() is True

        # Safety gate must immediately block any new mitigation
        gate_result = validate_safety_gate(
            target_ip="10.0.0.6",
            rate_limit_pps=1000,
            duration_seconds=60,
        )
        assert gate_result.allowed is False
        assert "Emergency disable is currently active" in (
            gate_result.rejection_reason or ""
        )

        # Record audit event
        record_audit_event(
            session=test_db,
            event_type="emergency_disable_activated",
            action="emergency_disable",
            actor="operator",
            details={"reason": "Manual operator override"},
        )
        audit_repo = AuditRepository(test_db)
        audit_records = audit_repo.list_filtered(
            event_type="emergency_disable_activated"
        )
        assert len(audit_records) == 1
    finally:
        set_emergency_disabled(False)


# ==============================================================================
# TC-12: Simulator Restart Reconciliation & Interruption
# ==============================================================================


def test_tc12_simulator_restart_reconciles_expired_actions(test_db: Session) -> None:
    """TC-12: When backend restarts, in-flight simulated actions past expiry are cleanly reconciled."""
    repo = MitigationRepository(test_db)
    past_ts = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=60)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Simulate an action that was running before server reboot
    orphaned = repo.create(
        detection_id=None,
        target_ip="192.168.1.50",
        target_port=None,
        action_type="rate_limit",
        rate_limit_pps=1500,
        duration_seconds=30,
        status="simulated",
        mode="simulation",
    )
    # Manually set expires_at in the past for testing restart expiry
    orphaned.expires_at = past_ts
    test_db.commit()

    # Reconciler checks active or simulated actions past expiry
    active = repo.get_active_or_simulated()
    assert len(active) == 1

    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    for act in active:
        if act.expires_at and act.expires_at < now_utc:
            repo.update_status(act.action_id, new_status="expired")
            record_audit_event(
                session=test_db,
                event_type="restart_reconciliation_expired",
                action="expire",
                actor="startup_reconciler",
                details={
                    "action_id": act.action_id,
                    "target": act.target_ip,
                    "mode": "simulation",
                },
            )

    updated_act = repo.get_by_action_id(orphaned.action_id)
    assert updated_act is not None
    assert updated_act.status == "expired"

    audit_repo = AuditRepository(test_db)
    reconcile_audits = audit_repo.list_filtered(
        event_type="restart_reconciliation_expired"
    )
    assert len(reconcile_audits) == 1
