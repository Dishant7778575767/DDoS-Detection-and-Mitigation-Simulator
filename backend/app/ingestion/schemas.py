"""Pydantic schemas for network traffic ingestion."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.features.definitions import FEATURE_SCHEMA_VERSION


class FlowObservationRequest(BaseModel):
    """Pydantic model validating an incoming flow observation."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(
        ..., min_length=1, max_length=64, description="Sensor or collector identifier"
    )
    timestamp: str = Field(
        ...,
        description="ISO 8601 UTC timestamp of observation",
        examples=["2026-10-25T10:30:00Z"],
    )
    window_seconds: float = Field(
        default=10.0,
        ge=1.0,
        le=300.0,
        description="Time-window aggregation period in seconds",
    )
    feature_schema_version: str = Field(
        default=FEATURE_SCHEMA_VERSION,
        description="Version of feature schema used by sensor",
    )
    features: dict[str, float] = Field(
        ...,
        description="Flow-level statistical features matching schema",
    )
    target_ip: str | None = Field(
        default=None,
        max_length=64,
        description="Optional destination/target IP address",
    )
    target_port: int | None = Field(
        default=None,
        ge=0,
        le=65535,
        description="Optional destination/target port",
    )


class FlowBatchIngestionRequest(BaseModel):
    """Batch ingestion request containing up to 1,000 flow observations."""

    model_config = ConfigDict(extra="forbid")

    observations: list[FlowObservationRequest] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of flow observation records",
    )


class FlowIngestionResponse(BaseModel):
    """Response returned upon processing flow observations."""

    processed_count: int
    detections: list[dict[str, Any]]
    alerts_created: int
    mitigations_requested: int


class TrafficSummaryResponse(BaseModel):
    """Summary metrics aggregated over the active sliding time window."""

    window_duration_seconds: float
    observation_count: int
    packet_rate: float
    byte_rate: float
    syn_rate: float
    syn_ack_ratio: float
    unique_sources: int
    is_burst: bool
