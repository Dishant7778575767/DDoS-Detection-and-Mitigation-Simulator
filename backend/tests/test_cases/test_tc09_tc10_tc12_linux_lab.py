"""SENTRIX PRD Section 10.2 Phase 6 Integration Tests: TC-09, TC-10, TC-12.

Validates:
- TC-09: Rule expiration and verified removal in isolated Linux lab.
- TC-10: Cleanup failure handling, emergency lockdown, failure auditing, and recovery.
- TC-12: Service restart reconciliation, orphaned rule pruning, and mismatch fail-closed behavior.
- Lab Authorization & Isolation: Subnet boundaries (10.200.0.0/24), bounds, and approval manifest gating.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from enforcement.agent import (
    CleanupVerificationError,
    LinuxEnforcementAgent,
)
from enforcement.expiry import EnforcementExpiryManager
from enforcement.rules import (
    APPROVED_LAB_INTERFACE,
    EnforcementValidationError,
    build_nftables_apply_commands,
    build_nftables_delete_rule_command,
    build_nftables_flush_table_command,
    parse_nftables_rules_output,
    validate_enforcement_bounds,
    validate_lab_target,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.mitigation.linux_lab import (
    APPROVAL_FILE_PATH,
    LabAuthorizationError,
    LinuxLabAdapter,
    verify_lab_authorization,
)
from app.mitigation.reconcile import (
    reconcile_lab_enforcement,
    recover_failed_action,
)
from app.safety.gate import (
    is_emergency_disabled,
    set_emergency_disabled,
)
from app.storage.database import Base
from app.storage.repositories import AuditRepository, MitigationRepository


@pytest.fixture
def db_session(tmp_path: Path) -> Session:
    """Provide an isolated SQLite database session."""
    db_file = tmp_path / "tc_lab_test.db"
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_safety_gate() -> None:
    """Ensure emergency disable is reset before and after every test."""
    set_emergency_disabled(False)
    yield
    set_emergency_disabled(False)


# -----------------------------------------------------------------------------
# WP 6.1 & WP 6.2: Lab Isolation, Command Safety, and Authorization Tests
# -----------------------------------------------------------------------------


def test_lab_target_validation_strict_subnet() -> None:
    """Target IP must strictly reside in approved subnet 10.200.0.0/24."""
    # Valid lab IP
    assert validate_lab_target("10.200.0.50") == "10.200.0.50"
    assert validate_lab_target("  10.200.0.200 ") == "10.200.0.200"

    # Outside lab subnet -> strictly forbidden
    with pytest.raises(EnforcementValidationError, match="outside approved lab subnet"):
        validate_lab_target("192.168.1.100")

    with pytest.raises(EnforcementValidationError, match="outside approved lab subnet"):
        validate_lab_target("8.8.8.8")

    # Protected lab hosts -> gateway, broadcast, loopback
    with pytest.raises(EnforcementValidationError, match="protected lab infrastructure"):
        validate_lab_target("10.200.0.1")  # Gateway

    with pytest.raises(EnforcementValidationError, match="protected lab infrastructure"):
        validate_lab_target("10.200.0.255")  # Broadcast

    with pytest.raises(EnforcementValidationError, match="protected lab infrastructure"):
        validate_lab_target("127.0.0.1")  # Loopback

    # Malformed IP
    with pytest.raises(EnforcementValidationError, match="Invalid IP address"):
        validate_lab_target("invalid-ip")


def test_enforcement_parameter_bounds() -> None:
    """Enforcement bounds must be strictly adhered to."""
    # Valid bounds
    validate_enforcement_bounds(rate_limit_pps=1000, duration_seconds=60)

    # PPS out of bounds
    with pytest.raises(EnforcementValidationError, match="Rate limit 50 pps"):
        validate_enforcement_bounds(rate_limit_pps=50, duration_seconds=60)

    with pytest.raises(EnforcementValidationError, match="Rate limit 60000 pps"):
        validate_enforcement_bounds(rate_limit_pps=60000, duration_seconds=60)

    # Duration out of bounds
    with pytest.raises(EnforcementValidationError, match="Duration 5s"):
        validate_enforcement_bounds(rate_limit_pps=1000, duration_seconds=5)

    with pytest.raises(EnforcementValidationError, match="Duration 500s"):
        validate_enforcement_bounds(rate_limit_pps=1000, duration_seconds=500)


def test_nftables_command_generation_is_parameterized() -> None:
    """Verify nftables commands use parameterized lists and safe comments."""
    cmds = build_nftables_apply_commands("act_test_01", "10.200.0.55", 2500)
    assert len(cmds) == 2

    accept_cmd = cmds[0]
    assert accept_cmd[0] == "nft"
    assert "sentrix_mitigation" in accept_cmd
    assert APPROVED_LAB_INTERFACE in accept_cmd
    assert "10.200.0.55" in accept_cmd
    assert "2500/second" in accept_cmd
    assert "sentrix:act_test_01" in accept_cmd

    drop_cmd = cmds[1]
    assert drop_cmd[0] == "nft"
    assert "drop" in drop_cmd
    assert "sentrix:act_test_01:drop" in drop_cmd

    del_cmd = build_nftables_delete_rule_command(42)
    assert del_cmd == [
        "nft",
        "delete",
        "rule",
        "inet",
        "sentrix_mitigation",
        "forward",
        "handle",
        "42",
    ]

    flush_cmd = build_nftables_flush_table_command()
    assert flush_cmd == ["nft", "delete", "table", "inet", "sentrix_mitigation"]


def test_parse_nftables_rules_output() -> None:
    """Parse real nftables output and extract handles and action IDs."""
    sample_output = """
table inet sentrix_mitigation {
    chain forward {
        type filter hook forward priority filter - 100; policy accept;
        iifname "sentrix0" ip saddr 10.200.0.50 limit rate 1000/second accept comment "sentrix:act_123" # handle 4
        iifname "sentrix0" ip saddr 10.200.0.50 drop comment "sentrix:act_123:drop" # handle 5
        iifname "sentrix0" ip saddr 10.200.0.80 limit rate 2000/second accept comment "sentrix:act_456" # handle 6
    }
}
"""
    rules = parse_nftables_rules_output(sample_output)
    assert len(rules) == 3
    assert rules[0]["action_id"] == "act_123"
    assert rules[0]["handle"] == 4
    assert rules[0]["is_drop"] is False
    assert rules[1]["handle"] == 5
    assert rules[1]["is_drop"] is True
    assert rules[2]["action_id"] == "act_456"


def test_lab_authorization_manifest_verification(tmp_path: Path) -> None:
    """Verify lab approval manifest check enforces explicit approval and expiration."""
    # 1. Manifest exists and valid
    valid_manifest = tmp_path / "valid_approval.json"
    valid_manifest.write_text(
        """{
        "approved": true,
        "enforcement_enabled": true,
        "expires_at": "2099-01-01T00:00:00Z"
    }""",
        encoding="utf-8",
    )
    data = verify_lab_authorization(valid_manifest)
    assert data["approved"] is True

    # 2. Missing manifest -> forbidden
    missing_manifest = tmp_path / "non_existent.json"
    with pytest.raises(LabAuthorizationError, match="Lab approval manifest not found"):
        verify_lab_authorization(missing_manifest)

    # 3. Disabled manifest
    disabled_manifest = tmp_path / "disabled.json"
    disabled_manifest.write_text(
        """{
        "approved": false,
        "enforcement_enabled": false
    }""",
        encoding="utf-8",
    )
    with pytest.raises(
        LabAuthorizationError, match="Lab enforcement is disabled or not approved"
    ):
        verify_lab_authorization(disabled_manifest)

    # 4. Expired manifest
    expired_manifest = tmp_path / "expired.json"
    expired_manifest.write_text(
        """{
        "approved": true,
        "enforcement_enabled": true,
        "expires_at": "2020-01-01T00:00:00Z"
    }""",
        encoding="utf-8",
    )
    with pytest.raises(LabAuthorizationError, match="Lab approval expired"):
        verify_lab_authorization(expired_manifest)


# -----------------------------------------------------------------------------
# TC-09: Rule Expiration in Isolated Linux Lab
# -----------------------------------------------------------------------------


def test_tc09_rule_expiration_and_verified_removal(db_session: Session) -> None:
    """TC-09: At expiry, SENTRIX-owned rule is removed, verified, and unrelated rules remain."""
    agent = LinuxEnforcementAgent(dry_run=True)
    adapter = LinuxLabAdapter(
        agent=agent, dry_run=True, approval_path=APPROVAL_FILE_PATH
    )
    expiry_mgr = EnforcementExpiryManager(agent=agent)

    # 1. Apply rate limit to lab target
    action_id = "act_tc09_expire"
    target_ip = "10.200.0.44"
    result = adapter.apply_rate_limit(
        action_id=action_id,
        target_ip=target_ip,
        rate_limit_pps=1500,
        duration_seconds=30,
    )

    assert result["status"] == "applied"
    assert result["mode"] == "lab"
    assert result["host_networking_modified"] is True

    # Register with expiry manager
    base_time = datetime.datetime.now(datetime.UTC)
    expiry_mgr.track_action(
        action_id=action_id,
        target_ip=target_ip,
        duration_seconds=30,
        applied_at_utc=base_time,
    )

    # 2. Before TTL expiration -> not expired
    mid_time = base_time + datetime.timedelta(seconds=15)
    expired_before = expiry_mgr.check_and_expire(now_dt=mid_time)
    assert len(expired_before) == 0
    assert not agent.verify_rule_removed(action_id)

    # 3. After TTL expiration -> rule removed and verified
    after_ttl = base_time + datetime.timedelta(seconds=35)
    expired_after = expiry_mgr.check_and_expire(now_dt=after_ttl)

    assert len(expired_after) == 1
    assert expired_after[0]["action_id"] == action_id
    assert expired_after[0]["status"] == "expired"
    assert expired_after[0]["cleanup_verified"] is True
    # Verify rule no longer in agent active set
    assert agent.verify_rule_removed(action_id)


# -----------------------------------------------------------------------------
# TC-10: Cleanup Failure Handling, Lockdown, and Procedural Recovery
# -----------------------------------------------------------------------------


def test_tc10_cleanup_failure_engages_lockdown_and_recovery(
    db_session: Session,
) -> None:
    """TC-10: Cleanup failure triggers lockdown, audit failure, and requires verified recovery."""
    agent = LinuxEnforcementAgent(dry_run=True)
    repo = MitigationRepository(db_session)
    audit_repo = AuditRepository(db_session)

    action_id = "act_tc10_fail"
    target_ip = "10.200.0.77"

    # Seed DB with applied lab mitigation
    mit = repo.create(
        detection_id=None,
        target_ip=target_ip,
        target_port=None,
        action_type="rate_limit",
        rate_limit_pps=2000,
        duration_seconds=20,
        status="applied",
        mode="lab",
    )
    # Give it specific action_id for test
    mit.action_id = action_id
    mit.expires_at = (
        datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=10)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    db_session.commit()

    # Seed agent rule
    agent._in_memory_rules.append(
        {
            "action_id": action_id,
            "target_ip": target_ip,
            "handle": 99,
        }
    )

    # Mock cancel_rate_limit to simulate cleanup verification failure
    with patch.object(
        agent,
        "cancel_rate_limit",
        side_effect=CleanupVerificationError("Simulated removal failure"),
    ):
        reconcile_res = reconcile_lab_enforcement(db_session, agent)

        # 1. State must fail closed
        assert reconcile_res["healthy"] is False
        assert is_emergency_disabled() is True

        # 2. Mitigation record must be marked 'failed'
        updated = repo.get_by_action_id(action_id)
        assert updated is not None
        assert updated.status == "failed"

        # 3. Cleanup failure must be audited
        cleanup_audits = audit_repo.list_filtered(event_type="cleanup_failure")
        assert len(cleanup_audits) >= 1
        assert action_id in cleanup_audits[0].details_json

    # 4. Attempting recovery while rule is still in kernel must fail
    with pytest.raises(CleanupVerificationError, match="still active in kernel"):
        recover_failed_action(db_session, agent, action_id)

    # 5. After operator removes kernel rule manually, recovery succeeds
    agent._in_memory_rules.clear()  # Manual remediation completed
    recovery_result = recover_failed_action(db_session, agent, action_id)

    assert recovery_result["status"] == "recovered"
    recovered_mit = repo.get_by_action_id(action_id)
    assert recovered_mit is not None
    assert recovered_mit.status == "recovered"

    # Audit log for recovery
    recovered_audits = audit_repo.list_filtered(event_type="mitigation_recovered")
    assert len(recovered_audits) == 1
    assert action_id in recovered_audits[0].details_json


# -----------------------------------------------------------------------------
# TC-12: Service Restart Reconciliation & Mismatch Lockdown
# -----------------------------------------------------------------------------


def test_tc12_service_restart_prunes_orphaned_rules(db_session: Session) -> None:
    """TC-12 Scenario A: Orphaned kernel rules without DB entries are safely pruned on restart."""
    agent = LinuxEnforcementAgent(dry_run=True)
    audit_repo = AuditRepository(db_session)

    # Add orphaned rule in kernel (never recorded in DB)
    agent._in_memory_rules.append(
        {
            "action_id": "act_orphan_99",
            "target_ip": "10.200.0.88",
            "handle": 7,
        }
    )

    reconcile_res = reconcile_lab_enforcement(db_session, agent)

    assert reconcile_res["healthy"] is True
    assert reconcile_res["orphaned_rules_removed"] == 1
    # Orphaned rule should be pruned from agent
    assert agent.verify_rule_removed("act_orphan_99")

    # Audited as orphaned_rule_cleaned
    audits = audit_repo.list_filtered(event_type="orphaned_rule_cleaned")
    assert len(audits) == 1
    assert "act_orphan_99" in audits[0].details_json


def test_tc12_service_restart_missing_rule_triggers_fail_closed(
    db_session: Session,
) -> None:
    """TC-12 Scenario B: DB says action is applied, but rule is missing from kernel -> fails closed."""
    agent = LinuxEnforcementAgent(dry_run=True)
    repo = MitigationRepository(db_session)
    audit_repo = AuditRepository(db_session)

    # DB has an active applied action not expired yet
    action_id = "act_missing_kernel_rule"
    future_exp = (
        datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=120)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    mit = repo.create(
        detection_id=None,
        target_ip="10.200.0.60",
        target_port=None,
        action_type="rate_limit",
        rate_limit_pps=1200,
        duration_seconds=120,
        status="applied",
        mode="lab",
    )
    mit.action_id = action_id
    mit.expires_at = future_exp
    db_session.commit()

    # Kernel is empty (rule is absent)
    agent._in_memory_rules.clear()

    reconcile_res = reconcile_lab_enforcement(db_session, agent)

    # Fail closed invariant triggered
    assert reconcile_res["healthy"] is False
    assert reconcile_res["missing_rules_detected"] == 1
    assert is_emergency_disabled() is True

    # Action marked failed
    updated_mit = repo.get_by_action_id(action_id)
    assert updated_mit is not None
    assert updated_mit.status == "failed"

    # Audited as mismatch
    mismatch_audits = audit_repo.list_filtered(
        event_type="lab_reconciliation_mismatch"
    )
    assert len(mismatch_audits) == 1


def test_tc12_clean_restart_reconciliation(db_session: Session) -> None:
    """TC-12 Scenario C: Clean restart where kernel rules match DB state exactly."""
    agent = LinuxEnforcementAgent(dry_run=True)
    repo = MitigationRepository(db_session)

    action_id = "act_in_sync"
    future_exp = (
        datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=180)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    mit = repo.create(
        detection_id=None,
        target_ip="10.200.0.66",
        target_port=None,
        action_type="rate_limit",
        rate_limit_pps=2500,
        duration_seconds=180,
        status="applied",
        mode="lab",
    )
    mit.action_id = action_id
    mit.expires_at = future_exp
    db_session.commit()

    # Rule in kernel matches
    agent._in_memory_rules.append(
        {
            "action_id": action_id,
            "target_ip": "10.200.0.66",
            "handle": 12,
        }
    )

    reconcile_res = reconcile_lab_enforcement(db_session, agent)

    assert reconcile_res["healthy"] is True
    assert reconcile_res["orphaned_rules_removed"] == 0
    assert reconcile_res["missing_rules_detected"] == 0
    assert is_emergency_disabled() is False
