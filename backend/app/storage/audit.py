"""Audit helper module for logging security and state transition events."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.storage.models import AuditEventModel
from app.storage.repositories import AuditRepository


def record_audit_event(
    session: Session,
    event_type: str,
    action: str,
    actor: str,
    details: dict[str, Any],
) -> AuditEventModel:
    """Record an immutable audit log entry."""
    repo = AuditRepository(session)
    return repo.log(
        event_type=event_type,
        action=action,
        actor=actor,
        details=details,
    )
