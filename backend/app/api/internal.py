"""Internal operational and keep-alive endpoints."""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import require_keepalive_auth
from app.storage.database import get_db_session

router = APIRouter(tags=["internal"])


class KeepaliveResponse(BaseModel):
    status: str
    database: str
    timestamp: str


@router.get("/keepalive", response_model=KeepaliveResponse)
def database_keepalive(
    _: Annotated[None, Depends(require_keepalive_auth)],
    session: Annotated[Session, Depends(get_db_session)],
) -> KeepaliveResponse:
    """Execute a lightweight real database ping to verify and maintain connection activity."""
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connectivity check failed.",
        ) from exc

    return KeepaliveResponse(
        status="ok",
        database="connected",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
