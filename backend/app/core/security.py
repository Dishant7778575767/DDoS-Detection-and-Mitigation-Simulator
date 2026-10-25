import hmac
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette import status

from app.core.config import Settings, get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


def require_api_auth(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not settings.api_auth_required:
        return

    expected = (
        settings.api_auth_token.get_secret_value()
        if settings.api_auth_token is not None
        else ""
    )
    supplied = credentials.credentials if credentials is not None else ""
    if not expected or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
