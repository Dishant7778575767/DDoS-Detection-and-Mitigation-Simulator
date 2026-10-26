"""Periodic / on-demand reconciliation of mitigations and Linux lab firewall state."""

from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path
from typing import Any

# Ensure repo root is on sys.path for enforcement module import
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from enforcement.agent import CleanupVerificationError, LinuxEnforcementAgent
from sqlalchemy.orm import Session

from app.mitigation.lifecycle import validate_lifecycle_transition
from app.safety.gate import set_emergency_disabled
from app.storage.audit import record_audit_event
from app.storage.repositories import MitigationRepository

logger = logging.getLogger("sentrix.mitigation.reconcile")


def reconcile_expired_mitigations(session: Session) -> list[dict[str, Any]]:
    """Scan active/simulated mitigations and expire those past their duration."""
    repo = MitigationRepository(session)
    active_actions = repo.get_active_or_simulated()
    now_utc = datetime.datetime.now(datetime.UTC)
    expired_actions: list[dict[str, Any]] = []

    for action in active_actions:
        if not action.expires_at:
            continue
        try:
            exp_dt = datetime.datetime.fromisoformat(
                action.expires_at.replace("Z", "+00:00")
            )
            if now_utc >= exp_dt:
                repo.update_status(action.action_id, "expired")
                record_audit_event(
                    session=session,
                    event_type="mitigation_state_transition",
                    action="expire",
                    actor="reconciliation_worker",
                    details={
                        "action_id": action.action_id,
                        "target_ip": action.target_ip,
                        "previous_state": action.status,
                        "new_state": "expired",
                    },
                )
                expired_actions.append(
                    {"action_id": action.action_id, "status": "expired"}
                )
        except ValueError:
            continue

    return expired_actions


def reconcile_lab_enforcement(
    session: Session, agent: LinuxEnforcementAgent
) -> dict[str, Any]:
    """Reconcile persisted lab actions against kernel nftables state (PRD 8.4 & TC-12).

    1. Cross-checks active database records (status == 'applied') with firewall rules.
    2. Removes orphaned firewall rules not tracked in database.
    3. Detects missing firewall rules (DB says applied, kernel has no rule) -> fails closed.
    4. Expires rules whose TTL has passed and verifies clean removal.
    5. On any state mismatch or cleanup failure, locks down via emergency disable.
    """
    repo = MitigationRepository(session)
    now_utc = datetime.datetime.now(datetime.UTC)
    now_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    result: dict[str, Any] = {
        "reconciled": True,
        "healthy": True,
        "orphaned_rules_removed": 0,
        "missing_rules_detected": 0,
        "expired_rules_cleaned": 0,
        "errors": [],
    }

    try:
        kernel_rules = agent.list_active_rules()
        kernel_action_map: dict[str, list[dict[str, Any]]] = {}
        for r in kernel_rules:
            act = r.get("action_id")
            if act:
                kernel_action_map.setdefault(act, []).append(r)

        # Get DB actions with status == 'applied'
        db_applied = [
            m for m in repo.list_filtered(mode="lab", limit=500) if m.status == "applied"
        ]
        db_action_map = {m.action_id: m for m in db_applied}

        # 1. Clean up orphaned kernel rules (rules in firewall not present as 'applied' in DB)
        for kernel_action_id, rules in kernel_action_map.items():
            if kernel_action_id not in db_action_map:
                logger.warning(
                    "Detected orphaned firewall rule '%s'. Cleaning up.", kernel_action_id
                )
                try:
                    for rule in rules:
                        target_ip = rule.get("target_ip", "0.0.0.0")
                        agent.cancel_rate_limit(kernel_action_id, target_ip)
                    result["orphaned_rules_removed"] += 1
                    record_audit_event(
                        session=session,
                        event_type="orphaned_rule_cleaned",
                        action="reconcile_orphan",
                        actor="lab_reconciler",
                        details={
                            "action_id": kernel_action_id,
                            "timestamp": now_iso,
                        },
                    )
                except (
                    CleanupVerificationError,
                    RuntimeError,
                    OSError,
                    ValueError,
                ) as exc:
                    err_msg = f"Failed to clean orphaned rule '{kernel_action_id}': {exc}"
                    logger.error(err_msg)
                    result["errors"].append(err_msg)
                    result["healthy"] = False

        # 2. Check for missing rules and expired rules among DB applied actions
        for action_id, db_action in db_action_map.items():
            # Check expiration
            is_expired = False
            if db_action.expires_at:
                try:
                    exp_dt = datetime.datetime.fromisoformat(
                        db_action.expires_at.replace("Z", "+00:00")
                    )
                    if now_utc >= exp_dt:
                        is_expired = True
                except ValueError:
                    pass

            if is_expired:
                # Rule should be expired and removed
                try:
                    agent.cancel_rate_limit(action_id, db_action.target_ip)
                    repo.update_status(action_id, "expired")
                    result["expired_rules_cleaned"] += 1
                    record_audit_event(
                        session=session,
                        event_type="mitigation_expired",
                        action="expire_lab_rule",
                        actor="lab_reconciler",
                        details={
                            "action_id": action_id,
                            "target_ip": db_action.target_ip,
                            "timestamp": now_iso,
                        },
                    )
                except (
                    CleanupVerificationError,
                    RuntimeError,
                    OSError,
                    ValueError,
                ) as exc:
                    err_msg = f"TC-10 Cleanup failure expiring '{action_id}': {exc}"
                    logger.critical(err_msg)
                    repo.update_status(action_id, "failed")
                    result["errors"].append(err_msg)
                    result["healthy"] = False
                    set_emergency_disabled(True)
                    record_audit_event(
                        session=session,
                        event_type="cleanup_failure",
                        action="expire_failed",
                        actor="lab_reconciler",
                        details={"action_id": action_id, "error": str(exc)},
                    )
            else:
                # Not expired: verify rule exists in kernel
                if action_id not in kernel_action_map:
                    err_msg = (
                        f"TC-12 Mismatch: DB record '{action_id}' is 'applied' but "
                        "absent from kernel firewall."
                    )
                    logger.critical(err_msg)
                    repo.update_status(action_id, "failed")
                    result["missing_rules_detected"] += 1
                    result["errors"].append(err_msg)
                    result["healthy"] = False
                    set_emergency_disabled(True)
                    record_audit_event(
                        session=session,
                        event_type="lab_reconciliation_mismatch",
                        action="missing_kernel_rule",
                        actor="lab_reconciler",
                        details={"action_id": action_id, "error": err_msg},
                    )

    except (
        CleanupVerificationError,
        RuntimeError,
        OSError,
        ValueError,
        KeyError,
    ) as exc:
        err_msg = f"Fatal reconciliation failure: {exc}"
        logger.critical(err_msg)
        result["reconciled"] = False
        result["healthy"] = False
        result["errors"].append(err_msg)
        set_emergency_disabled(True)
        record_audit_event(
            session=session,
            event_type="lab_reconciliation_fatal",
            action="reconcile_exception",
            actor="lab_reconciler",
            details={"error": str(exc)},
        )

    # Fail closed invariant: if not healthy, lock down enforcement
    if not result["healthy"]:
        set_emergency_disabled(True)

    return result


def recover_failed_action(
    session: Session, agent: LinuxEnforcementAgent, action_id: str
) -> dict[str, Any]:
    """Manually / procedurally recover a 'failed' lab mitigation action (PRD 8.3 & TC-10)."""
    repo = MitigationRepository(session)
    mitigation = repo.get_by_action_id(action_id)
    if not mitigation:
        raise ValueError(f"Mitigation action '{action_id}' not found.")

    validate_lifecycle_transition(mitigation.status, "recovered")

    # Verify that the rule is indeed removed from kernel
    if not agent.verify_rule_removed(action_id):
        raise CleanupVerificationError(
            f"Cannot recover action '{action_id}': rule is still active in kernel."
        )

    now_iso = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    repo.update_status(action_id, "recovered")

    record_audit_event(
        session=session,
        event_type="mitigation_recovered",
        action="recover_action",
        actor="operator_recovery",
        details={
            "action_id": action_id,
            "target_ip": mitigation.target_ip,
            "previous_state": mitigation.status,
            "timestamp": now_iso,
        },
    )

    return {
        "action_id": action_id,
        "status": "recovered",
        "recovered_at": now_iso,
    }
