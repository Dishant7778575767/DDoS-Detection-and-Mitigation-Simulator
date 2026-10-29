"""API endpoints for AWS CloudFront real-time logs via Amazon Kinesis Data Streams."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.aws.kinesis_consumer import kinesis_consumer
from app.core.config import Settings, get_settings
from app.core.security import require_api_auth

router = APIRouter(
    prefix="/integrations/aws/kinesis",
    tags=["AWS Kinesis Integration"],
    dependencies=[Depends(require_api_auth)],
)


class KinesisMockIngestRequest(BaseModel):
    """Payload for local mock ingestion and replay of CloudFront real-time logs."""

    lines: list[str] = Field(
        ...,
        max_length=5000,
        description="Raw tab-delimited CloudFront log lines",
    )
    stream_name: str = "mock-stream"
    shard_id: str = "shardId-000000000000"


class KinesisIngestResponse(BaseModel):
    status: str
    accepted_count: int
    duplicate_count: int
    poison_count: int


@router.get("/status", summary="Get Kinesis consumer worker status and shard lag")
def get_consumer_status() -> dict[str, Any]:
    """Retrieve consumer status, discovered shards, replication lag, and cumulative record counts."""
    return kinesis_consumer.get_status_report()


@router.post(
    "/mock-ingest",
    response_model=KinesisIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest raw CloudFront real-time log records (local mock/replay)",
)
def mock_ingest(payload: KinesisMockIngestRequest) -> KinesisIngestResponse:
    """Ingest tab-delimited CloudFront log lines without requiring live AWS credentials.

    Validates field format, dedupes using durable event store, and pipes records into the
    sliding-window telemetry aggregator.
    """
    if not payload.lines:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No log lines provided"
        )

    counts = kinesis_consumer.mock_ingest(
        raw_lines=payload.lines,
        stream_name=payload.stream_name,
        shard_id=payload.shard_id,
    )

    return KinesisIngestResponse(
        status="accepted",
        accepted_count=counts["accepted"],
        duplicate_count=counts["duplicate"],
        poison_count=counts["poison"],
    )


@router.post(
    "/start",
    summary="Start background Kinesis consumer worker",
)
def start_consumer(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Start the Kinesis polling thread in background."""
    kinesis_consumer.start_background()
    return {
        "status": "started",
        "message": "Kinesis consumer background thread started",
    }


@router.post(
    "/stop",
    summary="Stop background Kinesis consumer worker",
)
def stop_consumer() -> dict[str, str]:
    """Stop the background Kinesis polling thread."""
    kinesis_consumer.stop()
    return {"status": "stopped", "message": "Kinesis consumer stopped"}
