"""Audit event log retrieval endpoint."""

from __future__ import annotations

import csv
import io
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_api_auth
from app.storage.database import get_db_session
from app.storage.repositories import AuditRepository

router = APIRouter(tags=["audit"], dependencies=[Depends(require_api_auth)])


class AuditItem(BaseModel):
    event_id: str
    event_type: str
    action: str
    actor: str
    details: dict
    timestamp: str


class AuditListResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    events: list[AuditItem]


def _parse_details(val: Any) -> dict:
    if isinstance(val, dict):
        return val
    if not val:
        return {}
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"raw": str(val)}


@router.get("/audit", response_model=None)
def get_audit_records(
    session: Annotated[Session, Depends(get_db_session)],
    event_type: Annotated[str | None, Query(description="Filter by event type")] = None,
    format_type: Annotated[
        str, Query(alias="format", description="Output format: 'json' or 'csv'")
    ] = "json",
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Response | dict[str, Any]:
    """Return immutable system and security audit records."""
    safe_limit = limit.default if hasattr(limit, "default") else int(limit)
    safe_offset = offset.default if hasattr(offset, "default") else int(offset)

    repo = AuditRepository(session)
    records = repo.list_filtered(
        event_type=event_type, limit=safe_limit, offset=safe_offset
    )
    total = repo.count_filtered(event_type=event_type)

    if format_type.lower() == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["event_id", "event_type", "action", "actor", "timestamp", "details"]
        )
        for r in records:
            writer.writerow(
                [
                    r.event_id,
                    r.event_type,
                    r.action,
                    r.actor,
                    r.timestamp,
                    r.details_json,
                ]
            )
        return Response(content=output.getvalue(), media_type="text/csv")

    items = [
        AuditItem(
            event_id=r.event_id,
            event_type=r.event_type,
            action=r.action,
            actor=r.actor,
            details=_parse_details(r.details_json),
            timestamp=r.timestamp,
        )
        for r in records
    ]

    return AuditListResponse(
        total_count=total,
        limit=safe_limit,
        offset=safe_offset,
        events=items,
    ).model_dump()
