"""Amazon Kinesis Data Streams consumer for CloudFront real-time access logs.

Consumes tab-delimited real-time log records from Amazon Kinesis Data Streams,
normalizes them into RequestTelemetryItem schemas, persists deduplication
records and shard checkpoints in SQL storage, and feeds items into the
SENTRIX sliding-window telemetry aggregator.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from app.core.config import Settings, get_settings
from app.features.telemetry_aggregator import telemetry_aggregator
from app.ingestion.cloudfront_parser import (
    DEFAULT_CLOUDFRONT_LOG_FIELDS,
    CloudFrontRealTimeLogParser,
)
from app.ingestion.telemetry_schemas import RequestTelemetryItem
from app.storage.database import get_session_factory
from app.storage.repositories import (
    CloudFrontKinesisRepository,
    KinesisCheckpointRepository,
)

logger = logging.getLogger(__name__)


# AWS Kinesis sequence numbers must satisfy regular expression pattern: ^(0|([1-9]\d{0,128}))$
AWS_SEQUENCE_NUMBER_REGEX = re.compile(r"^(0|([1-9]\d{0,128}))$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ShardState:
    """In-memory state and cursor tracking for an individual Kinesis stream shard."""

    def __init__(self, shard_id: str) -> None:
        self.shard_id = shard_id
        self.shard_iterator: str | None = None
        self.last_sequence_number: str | None = None
        self.millis_behind_latest: int = 0
        self.records_processed: int = 0
        self.is_closed: bool = False
        self.consecutive_empty_polls: int = 0


class CloudFrontKinesisConsumer:
    """Dedicated worker service for streaming CloudFront real-time logs via Kinesis."""

    def __init__(
        self,
        settings: Settings | None = None,
        session_factory: Callable[[], Any] | None = None,
        boto_client: Any | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._boto_client = boto_client

        # Configure parser based on configured or default CloudFront log field list
        field_list = (
            [
                f.strip()
                for f in self.settings.cloudfront_log_fields.split(",")
                if f.strip()
            ]
            if self.settings.cloudfront_log_fields
            else DEFAULT_CLOUDFRONT_LOG_FIELDS
        )
        self.parser = CloudFrontRealTimeLogParser(field_names=field_list)

        self.stream_name = self.settings.aws_kinesis_stream_name
        self.region = self.settings.aws_region
        self.batch_size = self.settings.aws_kinesis_batch_size
        self.poll_interval = self.settings.aws_kinesis_poll_interval_seconds
        self.default_iterator_type = self.settings.aws_kinesis_iterator_type

        # Runtime status
        self.status: str = "stopped"  # stopped, running, paused, error, no_credentials
        self.last_error: str | None = None
        self.last_poll_at: str | None = None
        self.started_at: str | None = None

        # Cumulative metrics
        self.records_ingested_total: int = 0
        self.records_duplicate_total: int = 0
        self.records_poison_total: int = 0

        # Shard management
        self._shards: dict[str, ShardState] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None

    @property
    def settings(self) -> Settings:
        return self._settings or get_settings()

    def get_session(self) -> Any:
        factory = self._session_factory or get_session_factory(self.settings)
        return factory()

    def _get_kinesis_client(self) -> Any:
        if self._boto_client is not None:
            return self._boto_client

        import boto3

        client_kwargs: dict[str, Any] = {"region_name": self.region}
        if self.settings.aws_access_key_id and self.settings.aws_secret_access_key:
            key_id = self.settings.aws_access_key_id.get_secret_value().strip()
            secret_key = self.settings.aws_secret_access_key.get_secret_value().strip()
            if key_id and secret_key:
                client_kwargs["aws_access_key_id"] = key_id
                client_kwargs["aws_secret_access_key"] = secret_key
                if self.settings.aws_session_token:
                    session_token = (
                        self.settings.aws_session_token.get_secret_value().strip()
                    )
                    if session_token:
                        client_kwargs["aws_session_token"] = session_token

        self._boto_client = boto3.client("kinesis", **client_kwargs)
        return self._boto_client

    def refresh_shards(self) -> list[str]:
        """Discover active shards for the configured Kinesis stream."""
        client = self._get_kinesis_client()
        discovered_shard_ids: list[str] = []

        try:
            paginator = client.get_paginator("list_shards")
            for page in paginator.paginate(StreamName=self.stream_name):
                for shard in page.get("Shards", []):
                    s_id = shard["ShardId"]
                    discovered_shard_ids.append(s_id)
                    with self._lock:
                        if s_id not in self._shards:
                            self._shards[s_id] = ShardState(s_id)
            if self.status in ("no_credentials", "stream_unavailable", "access_denied"):
                self.status = "running"
                self.last_error = None
        except NoCredentialsError as exc:
            self.status = "no_credentials"
            self.last_error = f"AWS credentials missing: {exc}"
            logger.warning("Cannot list Kinesis shards: %s", self.last_error)
            raise
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "ClientError")
            if code == "ResourceNotFoundException":
                self.status = "stream_unavailable"
                self.last_error = f"Kinesis stream '{self.stream_name}' was not found in region {self.region}."
            elif code in ("AccessDeniedException", "UnauthorizedOperation"):
                self.status = "access_denied"
                self.last_error = f"IAM access denied reading Kinesis stream '{self.stream_name}': {exc}"
            else:
                self.status = "consumer_error"
                self.last_error = f"AWS Kinesis error ({code}): {exc}"
            logger.error("Kinesis ClientError: %s", self.last_error)
            raise
        except BotoCoreError as exc:
            self.status = "consumer_error"
            self.last_error = f"Failed to connect to Kinesis: {exc}"
            logger.error("Kinesis BotoCoreError: %s", self.last_error)
            raise

        return discovered_shard_ids

    def _get_or_init_shard_iterator(
        self, shard: ShardState, session: Any
    ) -> str | None:
        """Initialize or refresh a shard iterator, honoring checkpoints."""
        if shard.shard_iterator is not None:
            return shard.shard_iterator

        client = self._get_kinesis_client()
        ckpt_repo = KinesisCheckpointRepository(session)
        last_seq = ckpt_repo.get_checkpoint(self.stream_name, shard.shard_id)
        shard.last_sequence_number = last_seq

        params: dict[str, Any] = {
            "StreamName": self.stream_name,
            "ShardId": shard.shard_id,
        }

        use_checkpoint = False
        if last_seq:
            if AWS_SEQUENCE_NUMBER_REGEX.match(str(last_seq)):
                use_checkpoint = True
                params["ShardIteratorType"] = "AFTER_SEQUENCE_NUMBER"
                params["StartingSequenceNumber"] = str(last_seq)
                logger.info(
                    "Resuming shard %s from sequence number %s",
                    shard.shard_id,
                    last_seq,
                )
            else:
                logger.warning(
                    "Non-numeric checkpoint '%s' detected for shard %s on stream %s. Clearing invalid checkpoint and falling back to %s.",
                    last_seq,
                    shard.shard_id,
                    self.stream_name,
                    self.default_iterator_type,
                )
                ckpt_repo.delete_checkpoint(self.stream_name, shard.shard_id)
                shard.last_sequence_number = None

        if not use_checkpoint:
            params["ShardIteratorType"] = self.default_iterator_type
            logger.info(
                "Starting shard %s from configured default %s",
                shard.shard_id,
                self.default_iterator_type,
            )

        try:
            resp = client.get_shard_iterator(**params)
            shard.shard_iterator = resp.get("ShardIterator")
            return shard.shard_iterator
        except ClientError as exc:
            err_code = exc.response.get("Error", {}).get("Code", "Unknown")
            if use_checkpoint and err_code in (
                "InvalidArgumentException",
                "ValidationException",
                "ResourceNotFoundException",
            ):
                logger.warning(
                    "Shard iterator error (%s) resuming from checkpoint %s for shard %s: %s. Falling back to default %s iterator.",
                    err_code,
                    last_seq,
                    shard.shard_id,
                    exc,
                    self.default_iterator_type,
                )
                ckpt_repo.delete_checkpoint(self.stream_name, shard.shard_id)
                shard.last_sequence_number = None
                fallback_params: dict[str, Any] = {
                    "StreamName": self.stream_name,
                    "ShardId": shard.shard_id,
                    "ShardIteratorType": self.default_iterator_type,
                }
                try:
                    resp = client.get_shard_iterator(**fallback_params)
                    shard.shard_iterator = resp.get("ShardIterator")
                    return shard.shard_iterator
                except (ClientError, BotoCoreError) as fallback_exc:
                    logger.warning(
                        "Fallback shard iterator also failed for %s: %s",
                        shard.shard_id,
                        fallback_exc,
                    )
                    return None

            logger.warning(
                "Could not obtain shard iterator for %s: %s", shard.shard_id, exc
            )
            return None
        except BotoCoreError as exc:
            logger.warning(
                "Could not obtain shard iterator for %s: %s", shard.shard_id, exc
            )
            return None

    def poll_once(self) -> dict[str, int]:
        """Poll all active shards once, processing retrieved records."""
        self.last_poll_at = _utc_now_iso()
        counts = {"accepted": 0, "duplicate": 0, "poison": 0}

        with self.get_session() as session:
            # Refresh shard list if empty
            if not self._shards:
                try:
                    self.refresh_shards()
                except (NoCredentialsError, ClientError):
                    raise
                except Exception:  # noqa: BLE001
                    return counts

            client = self._get_kinesis_client()
            active_shards = list(self._shards.values())

            for shard in active_shards:
                if shard.is_closed:
                    continue

                iterator = self._get_or_init_shard_iterator(shard, session)
                if not iterator:
                    continue

                try:
                    resp = client.get_records(
                        ShardIterator=iterator, Limit=self.batch_size
                    )
                except ClientError as exc:
                    err_code = exc.response.get("Error", {}).get("Code", "Unknown")
                    if err_code in (
                        "ExpiredIteratorException",
                        "ResourceNotFoundException",
                    ):
                        logger.warning(
                            "Iterator expired or invalid for shard %s; resetting: %s",
                            shard.shard_id,
                            exc,
                        )
                        shard.shard_iterator = None
                    else:
                        logger.error("Error reading shard %s: %s", shard.shard_id, exc)
                    continue
                except BotoCoreError as exc:
                    logger.error(
                        "BotoCore error reading shard %s: %s",
                        shard.shard_id,
                        exc,
                    )
                    continue

                records = resp.get("Records", [])
                next_iterator = resp.get("NextShardIterator")
                millis_behind = resp.get("MillisBehindLatest", 0)

                shard.millis_behind_latest = millis_behind
                shard.shard_iterator = next_iterator

                if next_iterator is None:
                    shard.is_closed = True
                    logger.info("Shard %s reached end of stream", shard.shard_id)

                if not records:
                    shard.consecutive_empty_polls += 1
                    continue

                shard.consecutive_empty_polls = 0
                accepted, dups, poisons = self.process_kinesis_records(
                    records, shard, session
                )
                counts["accepted"] += accepted
                counts["duplicate"] += dups
                counts["poison"] += poisons

        with self._lock:
            self.records_ingested_total += counts["accepted"]
            self.records_duplicate_total += counts["duplicate"]
            self.records_poison_total += counts["poison"]

        return counts

    def process_kinesis_records(
        self,
        records: list[dict[str, Any]],
        shard: ShardState,
        session: Any,
        update_checkpoint: bool = True,
    ) -> tuple[int, int, int]:
        """Decode, parse, deduplicate, and ingest a batch of Kinesis records."""
        raw_lines: list[tuple[str, str]] = []  # (raw_line, sequence_number)

        for rec in records:
            seq = str(rec.get("SequenceNumber", ""))
            data = rec.get("Data", b"")
            if isinstance(data, str):
                data = data.encode("utf-8")

            try:
                decoded_str = data.decode("utf-8", errors="replace")
                # Records may contain multiple newline-separated lines
                for line in decoded_str.splitlines():
                    trimmed = line.strip()
                    if trimmed and not trimmed.startswith("#"):
                        raw_lines.append((trimmed, seq))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to decode Kinesis record payload: %s", exc)

        if not raw_lines:
            return 0, 0, 0

        # Parse log records via CloudFront parser
        lines_only = [line for line, _ in raw_lines]
        parsed_items, poison_count = self.parser.parse_batch(lines_only)

        # Pair parsed items with sequence numbers
        db_events: list[
            tuple[str, str, str, str, str]
        ] = []  # req_id, ts, stream, shard, seq
        valid_items_map: dict[str, RequestTelemetryItem] = {}

        for item, (_, seq) in zip(parsed_items, raw_lines, strict=False):
            if not item.request_id:
                continue
            valid_items_map[item.request_id] = item
            db_events.append(
                (
                    item.request_id,
                    item.timestamp,
                    self.stream_name,
                    shard.shard_id,
                    seq,
                )
            )

        if not db_events:
            return 0, 0, poison_count

        # Persist deduplication records with savepoints
        cf_repo = CloudFrontKinesisRepository(session)
        accepted_ids, duplicate_count = cf_repo.record_events_batch(db_events)

        # Filter to only newly accepted non-duplicate telemetry items
        accepted_items = [
            valid_items_map[req_id]
            for req_id in accepted_ids
            if req_id in valid_items_map
        ]

        if accepted_items:
            telemetry_aggregator.add_items(accepted_items)

        # Update shard checkpoint with highest sequence number from this batch
        last_seq = records[-1].get("SequenceNumber") if records else None
        if last_seq and update_checkpoint:
            seq_str = str(last_seq)
            if AWS_SEQUENCE_NUMBER_REGEX.match(seq_str):
                ckpt_repo = KinesisCheckpointRepository(session)
                ckpt_repo.update_checkpoint(
                    self.stream_name,
                    shard.shard_id,
                    seq_str,
                    records_processed_delta=len(accepted_items),
                )
            shard.last_sequence_number = seq_str
            shard.records_processed += len(accepted_items)

        return len(accepted_items), duplicate_count, poison_count

    def mock_ingest(
        self,
        raw_lines: list[str],
        stream_name: str = "mock-stream",
        shard_id: str = "shardId-000000000000",
    ) -> dict[str, int]:
        """Ingest raw tab-delimited CloudFront log lines without AWS connectivity.

        Used for local development, integration tests, and manual replay.
        """
        counts = {"accepted": 0, "duplicate": 0, "poison": 0}
        with self.get_session() as session:
            mock_records = []
            for i, line in enumerate(raw_lines):
                mock_records.append(
                    {
                        "SequenceNumber": f"mock-seq-{int(time.time())}-{i:06d}",
                        "Data": line.encode("utf-8"),
                    }
                )

            shard = ShardState(shard_id)
            accepted, dups, poisons = self.process_kinesis_records(
                mock_records, shard, session, update_checkpoint=False
            )
            counts["accepted"] = accepted
            counts["duplicate"] = dups
            counts["poison"] = poisons

        with self._lock:
            self.records_ingested_total += counts["accepted"]
            self.records_duplicate_total += counts["duplicate"]
            self.records_poison_total += counts["poison"]

        return counts

    def run_worker_loop(self) -> None:
        """Main worker loop executed in dedicated background worker or process."""
        self.status = "running"
        self.started_at = _utc_now_iso()
        logger.info(
            "CloudFront Kinesis Consumer started for stream: %s",
            self.stream_name,
        )

        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except NoCredentialsError:
                self.status = "no_credentials"
                logger.warning(
                    "CloudFront Kinesis worker paused: AWS credentials not found. Provide AWS credentials in .env or attach an IAM role to start."
                )
                break
            except ClientError as exc:
                err_code = exc.response.get("Error", {}).get("Code", "ClientError")
                if err_code in (
                    "UnrecognizedClientException",
                    "InvalidSignatureException",
                    "AuthFailure",
                ):
                    self.status = "no_credentials"
                    self.last_error = f"AWS credentials rejected ({err_code}): check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."
                    logger.warning(
                        "CloudFront Kinesis worker paused: %s", self.last_error
                    )
                    break
                elif err_code == "ResourceNotFoundException":
                    self.status = "stream_unavailable"
                    self.last_error = f"Kinesis stream '{self.stream_name}' was not found in AWS region {self.region}."
                    logger.warning(
                        "CloudFront Kinesis worker paused: %s", self.last_error
                    )
                    break
                elif err_code in ("AccessDeniedException", "UnauthorizedOperation"):
                    self.status = "access_denied"
                    self.last_error = f"IAM access denied reading Kinesis stream '{self.stream_name}'."
                    logger.warning(
                        "CloudFront Kinesis worker paused: %s", self.last_error
                    )
                    break
                else:
                    self.status = "error"
                    self.last_error = str(exc)
                    logger.error("ClientError in Kinesis consumer poll loop: %s", exc)
            except Exception as exc:  # noqa: BLE001
                self.status = "error"
                self.last_error = str(exc)
                logger.error("Error in Kinesis consumer poll loop: %s", exc)

            self._stop_event.wait(self.poll_interval)

        if self.status == "running":
            self.status = "stopped"
        logger.info("CloudFront Kinesis Consumer stopped")

    def start_background(self) -> None:
        """Start consumer loop in a daemon thread."""
        with self._lock:
            if self.status == "running":
                return
            self._boto_client = None
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self.run_worker_loop,
                name="CloudFrontKinesisConsumer",
                daemon=True,
            )
            self._worker_thread.start()

    def stop(self) -> None:
        """Stop background worker loop."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
        self.status = "stopped"

    def get_status_report(self) -> dict[str, Any]:
        """Return diagnostic metrics and shard status."""
        shards_info = {}
        with self._lock:
            for s_id, s in self._shards.items():
                shards_info[s_id] = {
                    "last_sequence_number": s.last_sequence_number,
                    "millis_behind_latest": s.millis_behind_latest,
                    "records_processed": s.records_processed,
                    "is_closed": s.is_closed,
                }

            computed_status = self.status
            if self.status == "stopped":
                if not self.settings.aws_kinesis_consumer_enabled:
                    computed_status = "consumer_disabled"
                elif not self.stream_name or not self.region:
                    computed_status = "not_configured"
            elif self.status == "running":
                if self.records_ingested_total > 0:
                    computed_status = "receiving_records"
                else:
                    computed_status = "connected_awaiting_records"

            return {
                "status": computed_status,
                "stream_name": self.stream_name,
                "region": self.region,
                "started_at": self.started_at,
                "last_poll_at": self.last_poll_at,
                "last_error": self.last_error,
                "metrics": {
                    "records_ingested_total": self.records_ingested_total,
                    "records_duplicate_total": self.records_duplicate_total,
                    "records_poison_total": self.records_poison_total,
                },
                "shards": shards_info,
            }


# Global singleton instance for application worker runtime
kinesis_consumer = CloudFrontKinesisConsumer()
