"""Alert retrieval and filtering endpoints."""

from __future__ import annotations

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
    severity: str | None = Query(
        default=None, description="Filter by severity ('info', 'warning', 'critical')"
    ),
    status: str | None = Query(
        default=None, description="Filter by status ('active', 'resolved')"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AlertsListResponse:
    """Return filtered and paginated alerts."""
    repo = AlertRepository(session)
    items = repo.list_filtered(
        severity=severity, status=status, limit=limit, offset=offset
    )
    total = repo.count_filtered(severity=severity, status=status)

    alert_items = [
        AlertItem(
            alert_id=a.alert_id,
            detection_id=a.detection_id,
            severity=a.severity,
            title=a.title,
            description=a.description,
            source_id=a.source_id,
            timestamp=a.timestamp,
            status=a.status,
        )
        for a in items
    ]

    return AlertsListResponse(
        total_count=total,
        limit=limit,
        offset=offset,
        alerts=alert_items,
    )
