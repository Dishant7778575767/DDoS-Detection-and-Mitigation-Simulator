from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.middleware.base import RequestResponseEndpoint

from app.api.v1.alerts import router as alerts_router
from app.api.v1.audit import router as audit_router
from app.api.v1.config import router as config_router
from app.api.v1.detection import router as detection_router
from app.api.v1.health import router as health_router
from app.api.v1.mitigations import router as mitigations_router
from app.api.v1.models import router as models_router
from app.api.v1.traffic import router as traffic_router
from app.core.config import get_settings, validate_runtime_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.storage.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    validate_runtime_settings(get_settings())
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="SENTRIX API", lifespan=lifespan)
    install_error_handlers(app)

    # Enable CORS for Next.js frontend development and testing
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register all Phase 3 API routers under /api/v1 prefix
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(traffic_router, prefix="/api/v1")
    app.include_router(detection_router, prefix="/api/v1")
    app.include_router(models_router, prefix="/api/v1")
    app.include_router(alerts_router, prefix="/api/v1")
    app.include_router(mitigations_router, prefix="/api/v1")
    app.include_router(config_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")

    @app.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = f"req_{uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    return app


app = create_app()
