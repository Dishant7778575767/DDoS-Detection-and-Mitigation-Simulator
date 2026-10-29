import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette import status

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unavailable")


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorEnvelope(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=_request_id(request),
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
        headers=headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
        default_errors: dict[int, tuple[str, str]] = {
            status.HTTP_400_BAD_REQUEST: ("INVALID_REQUEST", "Invalid request."),
            status.HTTP_401_UNAUTHORIZED: ("UNAUTHORIZED", "Authentication required."),
            status.HTTP_403_FORBIDDEN: ("FORBIDDEN", "Access denied."),
            status.HTTP_404_NOT_FOUND: ("NOT_FOUND", "Resource not found."),
            status.HTTP_409_CONFLICT: (
                "CONFLICT",
                "Request conflicts with current state.",
            ),
            status.HTTP_413_CONTENT_TOO_LARGE: (
                "REQUEST_TOO_LARGE",
                "Request exceeds the allowed size.",
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: (
                "RATE_LIMITED",
                "Too many requests.",
            ),
        }
        code, default_msg = default_errors.get(
            exc.status_code,
            ("HTTP_ERROR", "Request could not be completed."),
        )
        # Preserve specific endpoint exception detail if provided, fallback to default message
        message = str(exc.detail) if exc.detail else default_msg
        return _error_response(
            request, exc.status_code, code, message, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Provide human-readable field errors
        field_errors = []
        for error in exc.errors():
            loc = " -> ".join(str(l) for l in error.get("loc", []))
            msg = error.get("msg", "invalid")
            field_errors.append(f"{loc}: {msg}")
        readable_msg = (
            "; ".join(field_errors) if field_errors else "Request validation failed."
        )

        return _error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "VALIDATION_ERROR",
            readable_msg,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled request error request_id=%s",
            _request_id(request),
            exc_info=exc,
        )
        return _error_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred.",
        )
