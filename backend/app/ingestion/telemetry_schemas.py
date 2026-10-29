"""Pydantic schemas for real-time HTTP telemetry and access log ingestion."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RequestTelemetryItem(BaseModel):
    """Normalized telemetry record for a single L7 HTTP request."""

    model_config = ConfigDict(extra="ignore")

    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        description="ISO 8601 UTC timestamp or Unix timestamp string of request occurrence",
        examples=["2026-10-28T20:00:00Z"],
    )
    client_ip: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Client IPv4, IPv6 address, or anonymized client identifier",
        examples=["198.51.100.42"],
    )
    method: str = Field(
        default="GET",
        min_length=1,
        max_length=16,
        description="HTTP request method",
        examples=["GET", "POST"],
    )
    uri: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Requested URI path or route pattern",
        examples=["/api/v1/checkout"],
    )
    status_code: int = Field(
        ...,
        ge=100,
        le=599,
        description="HTTP response status code",
        examples=[200, 404, 503],
    )
    latency_ms: float = Field(
        ...,
        ge=0.0,
        description="Request processing duration in milliseconds",
        examples=[18.5],
    )
    bytes_sent: int = Field(
        default=0,
        ge=0,
        description="HTTP response body size in bytes",
    )
    user_agent: str | None = Field(
        default=None,
        max_length=512,
        description="Client User-Agent header string",
    )
    request_id: str | None = Field(
        default=None,
        max_length=64,
        description="Correlation / trace ID of the request",
    )


class TelemetryIngressRequest(BaseModel):
    """Payload for single or batch telemetry ingestion."""

    model_config = ConfigDict(extra="ignore")

    items: list[RequestTelemetryItem] = Field(
        default_factory=list,
        max_length=1000,
        description="Pre-parsed telemetry records (up to 1,000 per batch)",
    )
    raw_logs: list[str] = Field(
        default_factory=list,
        max_length=1000,
        description="Unparsed raw access log lines (Nginx/Apache Combined/CLF or JSON)",
    )
    anonymize_ips: bool = Field(
        default=True,
        description="Whether to mask the last octet of client IP addresses for privacy",
    )
    source_identifier: str = Field(
        default="authorized-web-node",
        max_length=64,
        description="Label identifying the emitting reverse proxy or server",
    )

    @model_validator(mode="after")
    def validate_payload_has_content(self) -> TelemetryIngressRequest:
        total_count = len(self.items) + len(self.raw_logs)
        if total_count == 0:
            raise ValueError(
                "Telemetry payload must contain at least one item in 'items' or 'raw_logs'"
            )
        if total_count > 1000:
            raise ValueError(
                f"Total telemetry batch size exceeds 1,000 items (received {total_count})"
            )
        return self


class TelemetryIngressResponse(BaseModel):
    """Ingestion confirmation response."""

    status: str = Field(default="accepted", description="Processing status")
    accepted_count: int = Field(
        ..., description="Number of valid telemetry events ingested"
    )
    dropped_or_invalid_count: int = Field(
        default=0, description="Number of discarded or unparseable events"
    )
    ingested_at: str = Field(..., description="ISO 8601 UTC timestamp of ingestion")


class LatencyPercentiles(BaseModel):
    """Statistical percentile distribution of request latency in milliseconds."""

    p50_ms: float = 0.0
    p90_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    avg_ms: float = 0.0


class StatusCodeDistribution(BaseModel):
    """Bucketed HTTP status code distribution and error ratios."""

    c_2xx: int = 0
    c_3xx: int = 0
    c_4xx: int = 0
    c_5xx: int = 0
    pct_2xx: float = 0.0
    pct_3xx: float = 0.0
    pct_4xx: float = 0.0
    pct_5xx: float = 0.0
    error_rate_pct: float = 0.0


class ClientEntropyMetrics(BaseModel):
    """Quantifies client IP concentration versus dispersion using Shannon Entropy."""

    unique_clients: int = 0
    shannon_entropy: float = 0.0
    max_possible_entropy: float = 0.0
    entropy_ratio: float = 0.0


class TopUriItem(BaseModel):
    """Frequently requested endpoints."""

    uri: str
    count: int
    pct: float


class TopClientItem(BaseModel):
    """Top source client IP and request percentage."""

    client_ip: str
    count: int
    pct: float


class LiveTelemetrySummaryResponse(BaseModel):
    """Aggregated real-time metrics over the active sliding window."""

    window_duration_seconds: float
    total_requests: int
    requests_per_second: float
    bytes_per_second: float
    status_codes: StatusCodeDistribution
    latencies: LatencyPercentiles
    client_metrics: ClientEntropyMetrics
    top_uris: list[TopUriItem]
    top_clients: list[TopClientItem] = Field(default_factory=list)
    top_methods: dict[str, int]
    is_anomaly: bool = False
