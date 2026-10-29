"""Comprehensive Integration Test Suite for SENTRIX Real-Time Telemetry Pipeline (Milestone 1).

Tests:
1. HTTP Access Log Parsing (Combined, CLF, JSON) and IP anonymization
2. TelemetryWindowAggregator sliding-window calculations (RPS, percentiles, Shannon entropy)
3. Ingress API endpoint (/api/v1/telemetry/ingress) with auth, batch limits, and error handling
4. Summary API endpoint (/api/v1/telemetry/summary) and synchronization with NetFlow
5. Reusable SentrixTelemetryMiddleware in-process telemetry capture
"""

from __future__ import annotations

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.features.telemetry_aggregator import (
    TelemetryWindowAggregator,
    telemetry_aggregator,
)
from app.ingestion.log_parser import (
    anonymize_ip,
    parse_access_log_line,
    parse_access_logs,
)
from app.ingestion.telemetry_schemas import RequestTelemetryItem
from app.integrations.middleware import SentrixTelemetryMiddleware
from app.main import create_app

# ---------------------------------------------------------------------------
# 1. Log Parser & IP Anonymization Tests
# ---------------------------------------------------------------------------


def test_ip_anonymization_ipv4_and_ipv6() -> None:
    """Verifies privacy masking for IPv4 (/24) and IPv6 (/48)."""
    assert anonymize_ip("192.168.1.42") == "192.168.1.0"
    assert anonymize_ip("10.0.50.99") == "10.0.50.0"
    assert anonymize_ip("2001:0db8:85a3:0000:0000:8a2e:0370:7334") == "2001:db8:85a3::"
    # Unparseable / local hostnames remain unchanged
    assert anonymize_ip("internal-node-alpha") == "internal-node-alpha"
    assert anonymize_ip("") == "0.0.0.0"


def test_parse_combined_log_format_with_duration() -> None:
    """Parses standard Nginx Combined log with trailing request_time."""
    line = '198.51.100.22 - - [28/Oct/2026:20:00:00 +0000] "GET /api/v1/checkout HTTP/1.1" 200 1450 "https://shop.com" "Mozilla/5.0" 0.045'
    item = parse_access_log_line(line)
    assert item is not None
    assert item.client_ip == "198.51.100.22"
    assert item.method == "GET"
    assert item.uri == "/api/v1/checkout"
    assert item.status_code == 200
    assert item.bytes_sent == 1450
    assert item.latency_ms == pytest.approx(45.0)
    assert item.user_agent == "Mozilla/5.0"


def test_parse_clf_log_format() -> None:
    """Parses Apache Common Log Format (CLF)."""
    line = (
        '192.0.2.1 - frank [10/Oct/2000:13:55:36 -0700] "POST /login HTTP/1.0" 401 250'
    )
    item = parse_access_log_line(line)
    assert item is not None
    assert item.client_ip == "192.0.2.1"
    assert item.method == "POST"
    assert item.uri == "/login"
    assert item.status_code == 401
    assert item.bytes_sent == 250
    assert item.latency_ms == 0.0


def test_parse_json_log_format() -> None:
    """Parses JSON-formatted access log lines (Caddy, Traefik, modern Nginx)."""
    line = (
        '{"client_ip": "203.0.113.15", "method": "DELETE", "uri": "/api/v1/users/42", '
        '"status_code": 204, "latency_ms": 12.8, "bytes_sent": 0, "user_agent": "Python-Httpx"}'
    )
    item = parse_access_log_line(line)
    assert item is not None
    assert item.client_ip == "203.0.113.15"
    assert item.method == "DELETE"
    assert item.uri == "/api/v1/users/42"
    assert item.status_code == 204
    assert item.latency_ms == pytest.approx(12.8)
    assert item.bytes_sent == 0
    assert item.user_agent == "Python-Httpx"


def test_parse_access_logs_batch_and_dropped_lines() -> None:
    """Batch parses logs and tracks dropped or invalid lines."""
    lines = [
        "# Nginx access log dump",
        "",
        '198.51.100.1 - - [28/Oct/2026:20:00:00 +0000] "GET /home HTTP/1.1" 200 500 "-" "-" 0.010',
        "THIS IS A CORRUPT OR PARTIAL LOG LINE",
        '{"remote_addr": "198.51.100.2", "request_method": "GET", "path": "/cart", "status": 200, "duration_ms": 15.0}',
    ]
    parsed, dropped = parse_access_logs(lines)
    assert len(parsed) == 2
    assert dropped == 3  # comment, empty line, corrupt line
    assert parsed[0].client_ip == "198.51.100.1"
    assert parsed[1].client_ip == "198.51.100.2"


# ---------------------------------------------------------------------------
# 2. TelemetryWindowAggregator Unit & Metric Tests
# ---------------------------------------------------------------------------


def test_telemetry_aggregator_empty_state() -> None:
    """Empty window returns zeroed statistics without division-by-zero errors."""
    agg = TelemetryWindowAggregator(window_duration_seconds=10.0)
    summary = agg.get_summary()
    assert summary.total_requests == 0
    assert summary.requests_per_second == 0.0
    assert summary.bytes_per_second == 0.0
    assert summary.status_codes.error_rate_pct == 0.0
    assert summary.latencies.p50_ms == 0.0
    assert summary.client_metrics.unique_clients == 0
    assert summary.client_metrics.shannon_entropy == 0.0
    assert not summary.is_anomaly


def test_telemetry_aggregator_metrics_and_percentiles() -> None:
    """Calculates status code breakdown, latencies (P50/P90/P95/P99), and throughput."""
    agg = TelemetryWindowAggregator(window_duration_seconds=10.0)
    now = time.time()

    items = [
        # 80 successful requests (status 200), latency 10ms to 89ms, 1000 bytes
        RequestTelemetryItem(
            timestamp=str(now),
            client_ip=f"10.0.0.{i % 5}",
            method="GET",
            uri="/api/search",
            status_code=200,
            latency_ms=float(10 + i),
            bytes_sent=1000,
        )
        for i in range(80)
    ]
    # 10 client error requests (status 404), latency 5ms
    items.extend(
        [
            RequestTelemetryItem(
                timestamp=str(now),
                client_ip="10.0.0.99",
                method="GET",
                uri="/missing",
                status_code=404,
                latency_ms=5.0,
                bytes_sent=200,
            )
            for _ in range(10)
        ]
    )
    # 10 server error requests (status 503), latency 200ms
    items.extend(
        [
            RequestTelemetryItem(
                timestamp=str(now),
                client_ip="10.0.0.99",
                method="POST",
                uri="/checkout",
                status_code=503,
                latency_ms=200.0,
                bytes_sent=100,
            )
            for _ in range(10)
        ]
    )

    agg.add_items(items)
    summary = agg.get_summary(current_timestamp=now, window_duration=10.0)

    assert summary.total_requests == 100
    assert summary.requests_per_second == 10.0  # 100 requests / 10s
    assert summary.status_codes.c_2xx == 80
    assert summary.status_codes.c_4xx == 10
    assert summary.status_codes.c_5xx == 10
    assert summary.status_codes.error_rate_pct == 20.0  # (10 + 10) / 100

    # Latencies
    assert summary.latencies.min_ms == 5.0
    assert summary.latencies.max_ms == 200.0
    assert summary.latencies.p50_ms > 10.0
    assert summary.latencies.p99_ms >= 150.0

    # Top URIs
    assert summary.top_uris[0].uri == "/api/search"
    assert summary.top_uris[0].count == 80


def test_telemetry_shannon_entropy() -> None:
    """Verifies Shannon entropy distinguishes single-source flood from distributed flood."""
    agg = TelemetryWindowAggregator(window_duration_seconds=10.0)
    now = time.time()

    # Scenario A: Single client sending 100 requests (Concentrated / DoS)
    dos_items = [
        RequestTelemetryItem(
            timestamp=str(now),
            client_ip="198.51.100.1",
            method="GET",
            uri="/attack",
            status_code=200,
            latency_ms=10.0,
            bytes_sent=100,
        )
        for _ in range(100)
    ]
    agg.add_items(dos_items)
    summary_dos = agg.get_summary(current_timestamp=now)
    # With a single source, entropy is zero
    assert summary_dos.client_metrics.unique_clients == 1
    assert summary_dos.client_metrics.shannon_entropy == 0.0
    assert summary_dos.client_metrics.entropy_ratio == 0.0

    # Scenario B: 50 distinct clients sending 2 requests each (Distributed / Botnet)
    agg.reset()
    ddos_items = [
        RequestTelemetryItem(
            timestamp=str(now),
            client_ip=f"198.51.100.{i}",
            method="GET",
            uri="/attack",
            status_code=200,
            latency_ms=10.0,
            bytes_sent=100,
        )
        for i in range(1, 51)
        for _ in range(2)
    ]
    agg.add_items(ddos_items)
    summary_ddos = agg.get_summary(current_timestamp=now)
    assert summary_ddos.client_metrics.unique_clients == 50
    # Equal distribution among 50 clients: H = log2(50) ≈ 5.6438, ratio ≈ 1.0
    assert summary_ddos.client_metrics.shannon_entropy > 5.0
    assert summary_ddos.client_metrics.entropy_ratio == pytest.approx(1.0, abs=0.01)


def test_telemetry_out_of_order_and_future_skew_pruning() -> None:
    """Verifies that out-of-order stale records and far-future drift timestamps are pruned and excluded."""
    agg = TelemetryWindowAggregator(window_duration_seconds=10.0)
    now = time.time()

    # 1. Valid recent record (within 10s window)
    agg.add_item(
        RequestTelemetryItem(
            timestamp=str(now - 2.0),
            client_ip="192.0.2.1",
            method="GET",
            uri="/valid1",
            status_code=200,
            latency_ms=15.0,
            bytes_sent=500,
        )
    )

    # 2. Out-of-order delayed record (30 seconds old, arrived after newer record)
    agg.add_item(
        RequestTelemetryItem(
            timestamp=str(now - 30.0),
            client_ip="192.0.2.2",
            method="GET",
            uri="/stale",
            status_code=500,
            latency_ms=100.0,
            bytes_sent=100,
        )
    )

    # 3. Second valid recent record
    agg.add_item(
        RequestTelemetryItem(
            timestamp=str(now - 1.0),
            client_ip="192.0.2.3",
            method="POST",
            uri="/valid2",
            status_code=201,
            latency_ms=25.0,
            bytes_sent=800,
        )
    )

    # 4. Far-future timestamp record (e.g. clock drift or malicious timestamp +500s)
    agg.add_item(
        RequestTelemetryItem(
            timestamp=str(now + 500.0),
            client_ip="192.0.2.4",
            method="GET",
            uri="/future",
            status_code=503,
            latency_ms=50.0,
            bytes_sent=200,
        )
    )

    summary = agg.get_summary(current_timestamp=now, window_duration=10.0)

    # Stale record (now - 30) and future record (now + 500) must be excluded!
    assert summary.total_requests == 2
    assert summary.status_codes.c_2xx == 2
    assert summary.status_codes.c_5xx == 0
    assert summary.status_codes.error_rate_pct == 0.0
    assert summary.client_metrics.unique_clients == 2
    uris = [u.uri for u in summary.top_uris]
    assert "/valid1" in uris
    assert "/valid2" in uris
    assert "/stale" not in uris
    assert "/future" not in uris


# ---------------------------------------------------------------------------
# 3. API Endpoint Integration Tests (/api/v1/telemetry)
# ---------------------------------------------------------------------------


def test_telemetry_ingress_requires_auth(monkeypatch) -> None:
    """Rejects unauthenticated requests when auth is enabled."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "valid-test-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        resp = client.post(
            "/api/v1/telemetry/ingress",
            json={
                "items": [
                    {
                        "client_ip": "10.0.0.1",
                        "method": "GET",
                        "uri": "/",
                        "status_code": 200,
                        "latency_ms": 5.0,
                    }
                ]
            },
        )
    assert resp.status_code == 401


def test_telemetry_ingress_payload_validation(monkeypatch) -> None:
    """Enforces batch boundaries and content requirements."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "valid-test-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()
    headers = {"Authorization": "Bearer valid-test-key"}

    with TestClient(create_app()) as client:
        # Empty payload must fail validation (HTTP 422)
        resp_empty = client.post(
            "/api/v1/telemetry/ingress",
            json={"items": [], "raw_logs": []},
            headers=headers,
        )
        assert resp_empty.status_code == 422

        # Exceeding 1,000 items must be rejected (HTTP 422)
        oversized = [
            {
                "client_ip": "1.1.1.1",
                "method": "GET",
                "uri": "/",
                "status_code": 200,
                "latency_ms": 1.0,
            }
            for _ in range(1001)
        ]
        resp_oversized = client.post(
            "/api/v1/telemetry/ingress",
            json={"items": oversized},
            headers=headers,
        )
        assert resp_oversized.status_code == 422


def test_telemetry_ingress_and_summary_flow(monkeypatch) -> None:
    """Tests end-to-end telemetry ingestion with IP anonymization, summary retrieval, and reset."""
    monkeypatch.setenv("API_AUTH_REQUIRED", "true")
    monkeypatch.setenv("API_AUTH_TOKEN", "valid-test-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./sentrix.db")
    get_settings.cache_clear()
    headers = {"Authorization": "Bearer valid-test-key"}

    with TestClient(create_app()) as client:
        # 1. Reset existing buffer
        resp_reset = client.post("/api/v1/telemetry/reset", headers=headers)
        assert resp_reset.status_code == 200

        # 2. Ingest hybrid payload (structured items + raw Nginx log lines)
        import datetime

        log_ts = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%d/%b/%Y:%H:%M:%S +0000"
        )
        payload = {
            "items": [
                {
                    "client_ip": "198.51.100.44",
                    "method": "POST",
                    "uri": "/api/v1/auth/login",
                    "status_code": 200,
                    "latency_ms": 32.5,
                    "bytes_sent": 850,
                }
            ],
            "raw_logs": [
                f'198.51.100.55 - - [{log_ts}] "GET /dashboard HTTP/1.1" 200 4200 "-" "Mozilla/5.0" 0.018',
                f'198.51.100.66 - - [{log_ts}] "GET /admin HTTP/1.1" 403 120 "-" "curl" 0.005',
                "corrupted line that should be dropped",
            ],
            "anonymize_ips": True,
            "source_identifier": "nginx-edge-01",
        }

        resp_ingest = client.post(
            "/api/v1/telemetry/ingress",
            json=payload,
            headers=headers,
        )
        assert resp_ingest.status_code == 202
        ingest_data = resp_ingest.json()
        assert ingest_data["status"] == "accepted"
        assert ingest_data["accepted_count"] == 3  # 1 item + 2 valid logs
        assert ingest_data["dropped_or_invalid_count"] == 1

        # 3. Query live telemetry summary
        resp_summary = client.get(
            "/api/v1/telemetry/summary?window_seconds=15", headers=headers
        )
        assert resp_summary.status_code == 200
        summary_data = resp_summary.json()

        assert summary_data["total_requests"] == 3
        assert summary_data["status_codes"]["c_2xx"] == 2
        assert summary_data["status_codes"]["c_4xx"] == 1
        assert summary_data["client_metrics"]["unique_clients"] >= 1
        assert len(summary_data["top_uris"]) >= 2

        # 4. NetFlow /traffic/summary should also reflect the live observations
        resp_traffic = client.get("/api/v1/traffic/summary", headers=headers)
        assert resp_traffic.status_code == 200
        traffic_data = resp_traffic.json()
        assert traffic_data["observation_count"] >= 3


# ---------------------------------------------------------------------------
# 4. Middleware Integration Test
# ---------------------------------------------------------------------------


def test_sentrix_telemetry_middleware_in_process() -> None:
    """Verifies SentrixTelemetryMiddleware captures application traffic in-process."""
    test_app = FastAPI()
    test_app.add_middleware(
        SentrixTelemetryMiddleware,
        sentrix_endpoint="in-process",
        anonymize_ips=True,
    )

    @test_app.get("/api/data")
    def get_data() -> dict[str, str]:
        return {"data": "ok"}

    @test_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    telemetry_aggregator.reset()

    with TestClient(test_app) as client:
        # Request to monitored route
        client.get("/api/data", headers={"X-Forwarded-For": "203.0.113.88"})
        # Request to excluded route
        client.get("/health")

    # Verify monitored route was recorded in aggregator
    summary = telemetry_aggregator.get_summary()
    assert summary.total_requests == 1
    assert summary.top_uris[0].uri == "/api/data"
    # Anonymized client IP: 203.0.113.88 -> 203.0.113.0
    assert summary.client_metrics.unique_clients == 1


def test_top_clients_calculation() -> None:
    """Verifies that TelemetryWindowAggregator accurately tallies and ranks top client IPs."""
    agg = TelemetryWindowAggregator(window_duration_seconds=30.0)
    now = time.time()

    items = [
        RequestTelemetryItem(
            timestamp=str(now),
            client_ip="198.51.100.10",
            method="GET",
            uri="/test",
            status_code=200,
            latency_ms=10.0,
        )
        for _ in range(70)
    ] + [
        RequestTelemetryItem(
            timestamp=str(now),
            client_ip="198.51.100.20",
            method="GET",
            uri="/test",
            status_code=200,
            latency_ms=10.0,
        )
        for _ in range(30)
    ]

    agg.add_items(items)
    summary = agg.get_summary(current_timestamp=now)

    assert len(summary.top_clients) == 2
    assert summary.top_clients[0].client_ip == "198.51.100.10"
    assert summary.top_clients[0].count == 70
    assert summary.top_clients[0].pct == 70.0
    assert summary.top_clients[1].client_ip == "198.51.100.20"
    assert summary.top_clients[1].count == 30
    assert summary.top_clients[1].pct == 30.0
