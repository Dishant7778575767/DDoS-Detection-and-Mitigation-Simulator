from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_api_auth

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse)
def health_check(
    _: Annotated[None, Depends(require_api_auth)],
) -> HealthResponse:
    return HealthResponse(status="ok")
