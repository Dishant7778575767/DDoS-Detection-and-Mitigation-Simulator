"""Periodic / on-demand reconciliation of expired mitigations."""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.storage.audit import record_audit_event
from app.storage.repositories import MitigationRepository


def reconcile_expired_mitigations(session: Session) -> list[dict[str, Any]]:
    """Scan active/simulated mitigations and expire those past their duration."""
    repo = MitigationRepository(session)
    active_actions = repo.get_active_or_simulated()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
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
