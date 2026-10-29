"""Telemetry ingestion and live monitoring endpoints for SENTRIX.

Provides:
- Ingestion endpoint supporting structured items and raw access logs (Nginx/Apache/JSON)
- IP anonymization for privacy compliance
- Live sliding-window telemetry metrics (RPS, status codes, latency percentiles, Shannon entropy)
- Synchronization with NetFlow window aggregator for unified defense visibility
"""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.security import require_api_auth
from app.features.telemetry_aggregator import telemetry_aggregator
from app.ingestion.log_parser import anonymize_ip, parse_access_logs
from app.ingestion.telemetry_schemas import (
    LiveTelemetrySummaryResponse,
    RequestTelemetryItem,
    TelemetryIngressRequest,
    TelemetryIngressResponse,
)
from app.services.pipeline import window_aggregator

router = APIRouter(
    prefix="/telemetry", tags=["telemetry"], dependencies=[Depends(require_api_auth)]
)


@router.post(
    "/ingress",
    response_model=TelemetryIngressResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest real-time HTTP telemetry or raw access logs",
)
def ingest_telemetry(payload: TelemetryIngressRequest) -> TelemetryIngressResponse:
    """Ingest single or batch HTTP telemetry items or raw web server access logs.

    Accepts up to 1,000 items per batch. Raw logs are parsed into standardized
    telemetry records. Client IP addresses are optionally anonymized.
    """
    all_items: list[RequestTelemetryItem] = []
    dropped_count = 0

    # 1. Parse raw log lines if present
    if payload.raw_logs:
        parsed_items, dropped = parse_access_logs(payload.raw_logs)
        all_items.extend(parsed_items)
        dropped_count += dropped

    # 2. Add pre-structured telemetry items
    if payload.items:
        all_items.extend(payload.items)

    # 3. Optional IP anonymization (/24 for IPv4, /48 for IPv6)
    if payload.anonymize_ips:
        for item in all_items:
            item.client_ip = anonymize_ip(item.client_ip)

    # 4. Feed into the L7 sliding window aggregator
    if all_items:
        telemetry_aggregator.add_items(all_items)

        # 5. Keep NetFlow sliding window synchronized with live HTTP traffic
        for item in all_items:
            # Estimate TCP flow parameters for HTTP request/response exchange
            est_packets = (
                10 if item.bytes_sent < 10000 else int(item.bytes_sent / 1500) + 4
            )
            est_bytes = max(item.bytes_sent + 512, 1024)
            window_aggregator.add_observation(
                timestamp=datetime.datetime.now(datetime.timezone.utc).timestamp(),
                packet_count=est_packets,
                byte_count=est_bytes,
                syn_flags=1,
                ack_flags=1,
                source_ip=item.client_ip,
            )

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return TelemetryIngressResponse(
        status="accepted",
        accepted_count=len(all_items),
        dropped_or_invalid_count=dropped_count,
        ingested_at=now_iso,
    )


@router.get(
    "/summary",
    response_model=LiveTelemetrySummaryResponse,
    summary="Retrieve live HTTP telemetry metrics over the active sliding window",
)
def get_telemetry_summary(
    window_seconds: Annotated[
        float,
        Query(
            description="Duration of sliding window to analyze in seconds",
            ge=1.0,
            le=300.0,
        ),
    ] = 10.0,
) -> LiveTelemetrySummaryResponse:
    """Return aggregated live metrics including RPS, latency percentiles, error rates,

    unique client diversity, and Shannon entropy.
    """
    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
    return telemetry_aggregator.get_summary(
        current_timestamp=now_ts, window_duration=window_seconds
    )


@router.post(
    "/reset",
    summary="Reset real-time telemetry sliding window buffers",
)
def reset_telemetry() -> dict[str, str]:
    """Clear all buffered telemetry metrics in memory."""
    telemetry_aggregator.reset()
    return {
        "status": "reset",
        "message": "Telemetry sliding window buffer cleared successfully.",
    }
