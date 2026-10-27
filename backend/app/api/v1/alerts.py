"""Alert retrieval and filtering endpoints."""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_api_auth
from app.storage.database import get_db_session
from app.storage.repositories import AlertRepository

router = APIRouter(tags=["alerts"], dependencies=[Depends(require_api_auth)])


class AlertItem(BaseModel):
    alert_id: str
    detection_id: int | None
    severity: str
    title: str
    description: str
    source_id: str
    target_ip: str | None
    timestamp: str
    status: str


class AlertsListResponse(BaseModel):
    total_count: int
    limit: int
    offset: int
    alerts: list[AlertItem]


@router.get("/alerts", response_model=AlertsListResponse)
def list_alerts(
    session: Annotated[Session, Depends(get_db_session)],
    severity: Annotated[
        str | None,
        Query(description="Filter by severity ('info', 'warning', 'critical')"),
    ] = None,
    status: Annotated[
        str | None, Query(description="Filter by status ('active', 'resolved')")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AlertsListResponse:
    """Return filtered and paginated alerts."""
    safe_limit = limit.default if hasattr(limit, "default") else int(limit)
    safe_offset = offset.default if hasattr(offset, "default") else int(offset)

    repo = AlertRepository(session)
    items = repo.list_filtered(
        severity=severity, status=status, limit=safe_limit, offset=safe_offset
    )
    total = repo.count_filtered(severity=severity, status=status)

    def _extract_target_ip(alert) -> str | None:
        if alert.detection is not None and alert.detection.observation is not None:
            if alert.detection.observation.target_ip:
                return alert.detection.observation.target_ip
        # Fallback to parsing IP from description text if legacy alert
        if alert.description:
            match = re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", alert.description)
            if match:
                return match.group(0).rstrip(".")
        return None

    alert_items = [
        AlertItem(
            alert_id=a.alert_id,
            detection_id=a.detection_id,
            severity=a.severity,
            title=a.title,
            description=a.description,
            source_id=a.source_id,
            target_ip=_extract_target_ip(a),
            timestamp=a.timestamp,
            status=a.status,
        )
        for a in items
    ]

    return AlertsListResponse(
        total_count=total,
        limit=safe_limit,
        offset=safe_offset,
        alerts=alert_items,
    )
