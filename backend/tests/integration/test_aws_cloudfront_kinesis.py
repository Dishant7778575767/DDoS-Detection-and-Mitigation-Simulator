"""Tests for AWS CloudFront Real-Time Logs ingestion via Kinesis and AWS WAFv2 Export."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import NoCredentialsError
from fastapi.testclient import TestClient

from app.aws.kinesis_consumer import CloudFrontKinesisConsumer
from app.core.config import get_settings
from app.ingestion.cloudfront_parser import (
    CloudFrontRealTimeLogParser,
)
from app.main import create_app
from app.mitigation.config_exporter import (
    export_aws_wafv2_cli_script,
    export_aws_wafv2_ipset,
    export_aws_wafv2_rules,
)
from app.mitigation.defensive_engine import (
    DefensiveActionType,
    DefensiveMitigationEngine,
)
from app.storage.database import get_session_factory
from app.storage.repositories import (
    CloudFrontKinesisRepository,
    KinesisCheckpointRepository,
)


def _sample_cloudfront_line(
    timestamp: float = 1730200000.123,
    client_ip: str = "198.51.100.42",
    ttfb: float = 0.045,
    status: int = 200,
    request_id: str = "cf_test_req_001",
    uri_query: str = "token=secret123&user=admin",
) -> str:
    # 18 standard fields:
    # timestamp, c-ip, time-to-first-byte, sc-status, sc-bytes, cs-method,
    # cs-protocol, cs-host, cs-uri-stem, cs-uri-query, c-port, x-edge-location,
    # x-edge-request-id, x-host-header, time-taken, cs-protocol-version,
    # c-ip-version, cs-user-agent
    fields = [
        str(timestamp),
        client_ip,
        str(ttfb),
        str(status),
        "1024",
        "POST",
        "https",
        "cdn.example.com",
        "/api/v1/login",
        uri_query,
        "443",
        "IAD89-C1",
        request_id,
        "cdn.example.com",
        "0.050",
        "HTTP/2.0",
        "IPv4",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    ]
    return "\t".join(fields)


def test_cloudfront_parser_units_and_privacy() -> None:
    parser = CloudFrontRealTimeLogParser()
    line = _sample_cloudfront_line()
    res = parser.parse_line(line)
    assert res is not None
    req_id, item = res

    assert req_id == "cf_test_req_001"
    assert item.client_ip == "198.51.100.42"
    assert item.method == "POST"
    assert item.status_code == 200
    assert item.bytes_sent == 1024
    # Check TTFB unit conversion (0.045 seconds -> 45.0 ms)
    assert item.latency_ms == 45.0
    # Check privacy: query parameters stripped from normalized URI
    assert "token=secret123" not in item.uri
    assert item.uri == "/api/v1/login"
    # Check ISO timestamp
    assert "T" in item.timestamp


def test_cloudfront_parser_poison_and_anomalies() -> None:
    parser = CloudFrontRealTimeLogParser()

    # Empty and comment lines ignored
    assert parser.parse_line("") is None
    assert parser.parse_line("#Fields: timestamp c-ip") is None

    # Truncated line (fewer than minimum required fields)
    assert parser.parse_line("1730200000.123\t198.51.100.1") is None

    # Invalid timestamp
    invalid_line = _sample_cloudfront_line().replace(
        "1730200000.123", "not-a-timestamp"
    )
    assert parser.parse_line(invalid_line) is None

    # Batch parser reports poison count
    lines = [
        _sample_cloudfront_line(request_id="cf_good_1"),
        "invalid\tmalformed\tline",
        _sample_cloudfront_line(request_id="cf_good_2"),
    ]
    items, poison_count = parser.parse_batch(lines)
    assert len(items) == 2
    assert poison_count == 1
    assert items[0].request_id == "cf_good_1"
    assert items[1].request_id == "cf_good_2"


def test_kinesis_checkpoint_and_event_persistence(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "kinesis_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    get_settings.cache_clear()

    session_factory = get_session_factory()
    # Create tables
    from app.storage.database import Base, create_database_engine

    engine = create_database_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)

    with session_factory() as session:
        ckpt_repo = KinesisCheckpointRepository(session)
        cf_repo = CloudFrontKinesisRepository(session)

        # 1. Checkpoint upsert
        ckpt = ckpt_repo.update_checkpoint(
            stream_name="test-stream",
            shard_id="shard-001",
            sequence_number="seq-100",
            records_processed_delta=5,
        )
        assert ckpt.last_sequence_number == "seq-100"
        assert ckpt.records_processed == 5

        # 2. Checkpoint retrieve
        retrieved_seq = ckpt_repo.get_checkpoint("test-stream", "shard-001")
        assert retrieved_seq == "seq-100"

        # 3. CloudFront events deduplication
        events = [
            ("req-01", "2026-10-29T10:00:00Z", "test-stream", "shard-001", "seq-100"),
            ("req-02", "2026-10-29T10:00:01Z", "test-stream", "shard-001", "seq-100"),
        ]
        accepted_ids, dup_count = cf_repo.record_events_batch(events)
        assert accepted_ids == ["req-01", "req-02"]
        assert dup_count == 0

        # Attempt to insert same events again -> must be deduplicated
        accepted_ids_2, dup_count_2 = cf_repo.record_events_batch(events)
        assert accepted_ids_2 == []
        assert dup_count_2 == 2


def test_kinesis_consumer_mock_ingest(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "kinesis_consumer_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    get_settings.cache_clear()

    from app.storage.database import Base, create_database_engine

    engine = create_database_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)

    consumer = CloudFrontKinesisConsumer()
    lines = [
        _sample_cloudfront_line(request_id="cf_mock_001"),
        _sample_cloudfront_line(request_id="cf_mock_002"),
        "invalid poison pill line",
    ]

    counts = consumer.mock_ingest(lines)
    assert counts["accepted"] == 2
    assert counts["duplicate"] == 0
    assert counts["poison"] == 1

    # Re-ingest same lines -> duplicates detected
    counts_dups = consumer.mock_ingest(lines)
    assert counts_dups["accepted"] == 0
    assert counts_dups["duplicate"] == 2
    assert counts_dups["poison"] == 1

    # Verify mock_ingest does NOT write fake sequence checkpoints into the DB
    with consumer.get_session() as session:
        from app.storage.repositories import KinesisCheckpointRepository
        ckpt = KinesisCheckpointRepository(session).get_checkpoint(
            consumer.stream_name, "shardId-000000000000"
        )
        assert ckpt is None


def test_kinesis_consumer_invalid_checkpoint_recovery(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "kinesis_recovery_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    get_settings.cache_clear()

    from app.storage.database import Base, create_database_engine
    from app.storage.repositories import KinesisCheckpointRepository
    from app.aws.kinesis_consumer import CloudFrontKinesisConsumer, ShardState

    engine = create_database_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)

    session_factory = get_session_factory()
    with session_factory() as session:
        ckpt_repo = KinesisCheckpointRepository(session)
        # Seed an invalid mock sequence number
        ckpt_repo.update_checkpoint(
            "sentrix-cloudfront-realtime-logs",
            "shardId-000000000000",
            "mock-seq-1793287523-000006",
        )

    mock_boto = MagicMock()
    mock_boto.get_shard_iterator.return_value = {"ShardIterator": "valid-iterator-123"}
    consumer = CloudFrontKinesisConsumer(boto_client=mock_boto)
    shard = ShardState("shardId-000000000000")

    with session_factory() as session:
        it = consumer._get_or_init_shard_iterator(shard, session)
        assert it == "valid-iterator-123"

        # Check that it did NOT call AFTER_SEQUENCE_NUMBER with mock-seq
        call_kwargs = mock_boto.get_shard_iterator.call_args[1]
        assert call_kwargs["ShardIteratorType"] == "LATEST"
        assert "StartingSequenceNumber" not in call_kwargs

        # Check that the invalid checkpoint was purged from DB
        purged = KinesisCheckpointRepository(session).get_checkpoint(
            "sentrix-cloudfront-realtime-logs", "shardId-000000000000"
        )
        assert purged is None


def test_kinesis_consumer_missing_credentials_handling() -> None:
    mock_boto = MagicMock()
    mock_boto.get_paginator.side_effect = NoCredentialsError()

    consumer = CloudFrontKinesisConsumer(boto_client=mock_boto)
    with pytest.raises(NoCredentialsError):
        consumer.refresh_shards()

    assert consumer.status == "no_credentials"
    assert "AWS credentials missing" in (consumer.last_error or "")


def test_aws_wafv2_exporter() -> None:
    engine = DefensiveMitigationEngine()
    rule_active = engine.propose_rule(
        target_ip_or_cidr="198.51.100.50",
        action_type=DefensiveActionType.BLOCK,
        reason="Repeated Credential Stuffing",
        dry_run=False,
    )
    rule_dry = engine.propose_rule(
        target_ip_or_cidr="203.0.113.10",
        action_type=DefensiveActionType.BLOCK,
        reason="Volumetric Anomaly",
        dry_run=True,
    )

    rules = [rule_active, rule_dry]

    # 1. IPSet definition
    ipset = export_aws_wafv2_ipset(rules, ipset_name="sentrix-test-ipset")
    assert ipset["Name"] == "sentrix-test-ipset"
    assert ipset["Scope"] == "CLOUDFRONT"
    assert ipset["Region"] == "us-east-1"
    # Addresses must be in CIDR notation
    assert "198.51.100.50/32" in ipset["Addresses"]
    assert "203.0.113.10/32" in ipset["Addresses"]

    # 2. WebACL Rules
    webacl_rules = export_aws_wafv2_rules(rules)
    assert len(webacl_rules) == 2
    # Active rule maps to Block action
    assert webacl_rules[0]["Action"] == {"Block": {}}
    # Dry-run rule maps to Count action
    assert webacl_rules[1]["Action"] == {"Count": {}}

    # 3. CLI Script
    cli_script = export_aws_wafv2_cli_script(rules, ipset_name="sentrix-test-ipset")
    assert "aws wafv2 create-ip-set" in cli_script
    assert 'SCOPE="CLOUDFRONT"' in cli_script
    assert 'REGION="us-east-1"' in cli_script


def test_aws_kinesis_and_waf_api_endpoints(monkeypatch, tmp_path) -> None:
    db_file = tmp_path / "api_test.db"
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "test-auth-token")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    get_settings.cache_clear()

    from app.storage.database import Base, create_database_engine

    engine = create_database_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=engine)

    headers = {"Authorization": "Bearer test-auth-token"}

    with TestClient(create_app()) as client:
        # 1. Kinesis status endpoint
        resp_status = client.get(
            "/api/v1/integrations/aws/kinesis/status", headers=headers
        )
        assert resp_status.status_code == 200
        data = resp_status.json()
        assert "status" in data
        assert "stream_name" in data
        assert "metrics" in data

        # 2. Kinesis mock ingest endpoint
        sample_line = _sample_cloudfront_line(request_id="cf_api_test_01")
        resp_ingest = client.post(
            "/api/v1/integrations/aws/kinesis/mock-ingest",
            headers=headers,
            json={"lines": [sample_line]},
        )
        assert resp_ingest.status_code == 202
        ingest_data = resp_ingest.json()
        assert ingest_data["status"] == "accepted"
        assert ingest_data["accepted_count"] == 1

        # 3. AWS WAFv2 export endpoints
        resp_waf = client.get("/api/v1/mitigations/export/aws-waf", headers=headers)
        assert resp_waf.status_code == 200
        waf_data = resp_waf.json()
        assert waf_data["provider"] == "aws_wafv2"
        assert waf_data["scope"] == "CLOUDFRONT"
        assert waf_data["region"] == "us-east-1"
        assert "ipset" in waf_data

        resp_cli = client.get("/api/v1/mitigations/export/aws-waf/cli", headers=headers)
        assert resp_cli.status_code == 200
        assert "aws wafv2" in resp_cli.text
