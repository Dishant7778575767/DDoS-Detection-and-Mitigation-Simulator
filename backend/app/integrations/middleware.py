"""Reusable FastAPI / Starlette Telemetry Middleware for SENTRIX.

Monitors incoming HTTP requests in real-time and transmits standardized telemetry
records (latency, status code, client IP, path, byte size) to SENTRIX.

Can operate in:
1. "in-process" mode: Directly updates local SENTRIX telemetry aggregator (zero network overhead).
2. "remote" mode: Asynchronously batches and exports telemetry via HTTP POST to an external SENTRIX cluster.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import time
from collections.abc import Callable

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.features.telemetry_aggregator import telemetry_aggregator
from app.ingestion.log_parser import anonymize_ip
from app.ingestion.telemetry_schemas import RequestTelemetryItem

logger = logging.getLogger("sentrix.middleware")

DEFAULT_EXCLUDED_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/api/v1/telemetry/ingress",
    "/api/v1/telemetry/summary",
    "/api/v1/telemetry/reset",
}


class SentrixTelemetryMiddleware(BaseHTTPMiddleware):
    """Starlette/FastAPI middleware for automated HTTP telemetry collection."""

    def __init__(
        self,
        app: Callable,
        sentrix_endpoint: str | None = "in-process",
        api_token: str | None = None,
        batch_size: int = 50,
        flush_interval_seconds: float = 2.0,
        anonymize_ips: bool = True,
        excluded_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.sentrix_endpoint = sentrix_endpoint
        self.api_token = api_token
        self.batch_size = max(1, batch_size)
        self.flush_interval_seconds = max(0.5, flush_interval_seconds)
        self.anonymize_ips = anonymize_ips
        self.excluded_paths = (
            set(excluded_paths)
            if excluded_paths is not None
            else DEFAULT_EXCLUDED_PATHS
        )

        self._queue: list[RequestTelemetryItem] = []
        self._queue_lock = asyncio.Lock()
        self._last_flush_time = time.time()
        self._flush_task: asyncio.Task | None = None
        self._is_in_process = (
            sentrix_endpoint is None
            or sentrix_endpoint == "in-process"
            or sentrix_endpoint == ""
        )

    def _extract_client_ip(self, request: Request) -> str:
        """Extract real client IP from headers (X-Forwarded-For, X-Real-IP) or socket."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # First IP in comma-separated list is client IP
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        if request.client and request.client.host:
            return request.client.host

        return "127.0.0.1"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Intercept request, measure timing, and record telemetry."""
        path = request.url.path
        if path in self.excluded_paths:
            return await call_next(request)

        start_time = time.perf_counter()
        status_code = 500
        response: Response | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = max(0.01, (time.perf_counter() - start_time) * 1000.0)

            # Compute bytes sent from response headers if available
            bytes_sent = 0
            if response is not None:
                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit():
                    bytes_sent = int(content_length)

            client_ip = self._extract_client_ip(request)
            if self.anonymize_ips:
                client_ip = anonymize_ip(client_ip)

            item = RequestTelemetryItem(
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                client_ip=client_ip,
                method=request.method,
                uri=path,
                status_code=status_code,
                latency_ms=round(duration_ms, 2),
                bytes_sent=bytes_sent,
                user_agent=request.headers.get("user-agent"),
            )

            # Record telemetry asynchronously without delaying request return
            if self._is_in_process:
                # Direct in-memory recording
                try:
                    telemetry_aggregator.add_item(item)
                except (ValueError, TypeError, KeyError, RuntimeError) as exc:
                    logger.debug("Failed in-process telemetry recording: %s", exc)
            else:
                # Async remote dispatch
                asyncio.create_task(self._enqueue_and_maybe_flush(item))

    async def _enqueue_and_maybe_flush(self, item: RequestTelemetryItem) -> None:
        """Buffer telemetry and flush when batch size or interval threshold reached."""
        try:
            to_flush: list[RequestTelemetryItem] = []
            async with self._queue_lock:
                self._queue.append(item)
                now = time.time()
                if (
                    len(self._queue) >= self.batch_size
                    or (now - self._last_flush_time) >= self.flush_interval_seconds
                ):
                    to_flush = list(self._queue)
                    self._queue.clear()
                    self._last_flush_time = now

            if to_flush and self.sentrix_endpoint:
                await self._export_batch(to_flush)
        except (RuntimeError, OSError) as exc:
            logger.debug("Error enqueuing telemetry item: %s", exc)

    async def _export_batch(self, items: list[RequestTelemetryItem]) -> None:
        """Send telemetry batch over HTTP to SENTRIX ingress endpoint."""
        if not self.sentrix_endpoint:
            return

        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        payload = {
            "items": [item.model_dump() for item in items],
            "anonymize_ips": False,  # Already anonymized during capture if configured
            "source_identifier": "sentrix-middleware",
        }

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(
                    self.sentrix_endpoint,
                    json=payload,
                    headers=headers,
                )
                if resp.status_code not in (200, 201, 202):
                    logger.warning(
                        "Remote telemetry export failed with HTTP %d: %s",
                        resp.status_code,
                        resp.text[:200],
                    )
        except (httpx.HTTPError, OSError) as exc:
            logger.debug("SENTRIX telemetry exporter unreachable: %s", exc)
