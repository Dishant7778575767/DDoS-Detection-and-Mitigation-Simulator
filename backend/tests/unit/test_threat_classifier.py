"""Unit tests for Multi-Tier Threat Classification & Flash-Crowd Differentiation."""

from __future__ import annotations

import pytest

from app.detection.baselines import AdaptiveTelemetryBaseline
from app.detection.threat_classifier import (
    RecommendedAction,
    ThreatSeverity,
    ThreatType,
    classify_telemetry_snapshot,
)
from app.ingestion.telemetry_schemas import (
    ClientEntropyMetrics,
    LatencyPercentiles,
    LiveTelemetrySummaryResponse,
    StatusCodeDistribution,
    TopUriItem,
)


@pytest.fixture
def calibrated_baseline() -> AdaptiveTelemetryBaseline:
    baseline = AdaptiveTelemetryBaseline()
    baseline.calibrate(
        initial_rps=25.0,
        initial_error_pct=1.5,
        initial_p95_ms=30.0,
        initial_bps=12000.0,
    )
    return baseline


def test_classify_benign_traffic(
    calibrated_baseline: AdaptiveTelemetryBaseline,
) -> None:
    """Verifies that normal, healthy traffic is classified as BENIGN."""
    summary = LiveTelemetrySummaryResponse(
        window_duration_seconds=10.0,
        total_requests=250,
        requests_per_second=25.0,
        bytes_per_second=12500.0,
        status_codes=StatusCodeDistribution(
            c_2xx=245, c_4xx=5, pct_2xx=98.0, error_rate_pct=2.0
        ),
        latencies=LatencyPercentiles(p50_ms=20.0, p95_ms=35.0, avg_ms=22.0),
        client_metrics=ClientEntropyMetrics(
            unique_clients=40, shannon_entropy=4.8, entropy_ratio=0.88
        ),
        top_uris=[TopUriItem(uri="/index.html", count=100, pct=40.0)],
        top_methods={"GET": 250},
        is_anomaly=False,
    )

    result = classify_telemetry_snapshot(summary, baseline=calibrated_baseline)
    assert result.threat_type == ThreatType.BENIGN
    assert result.severity == ThreatSeverity.INFO
    assert not result.is_threat
    assert not result.is_flash_crowd
    assert result.recommended_action == RecommendedAction.ALLOW


def test_classify_flash_crowd_differentiation(
    calibrated_baseline: AdaptiveTelemetryBaseline,
) -> None:
    """Verifies that a genuine surge (high RPS, high unique clients, high entropy, low errors)

    is classified as FLASH_CROWD rather than being blocked.
    """
    summary = LiveTelemetrySummaryResponse(
        window_duration_seconds=10.0,
        total_requests=1200,
        requests_per_second=120.0,  # ~5x normal baseline
        bytes_per_second=60000.0,
        status_codes=StatusCodeDistribution(
            c_2xx=1150, c_4xx=50, pct_2xx=95.8, error_rate_pct=4.2
        ),
        latencies=LatencyPercentiles(p50_ms=45.0, p95_ms=120.0, avg_ms=50.0),
        client_metrics=ClientEntropyMetrics(
            unique_clients=300, shannon_entropy=7.8, entropy_ratio=0.92
        ),
        top_uris=[TopUriItem(uri="/breaking-news", count=600, pct=50.0)],
        top_methods={"GET": 1200},
        is_anomaly=False,
    )

    result = classify_telemetry_snapshot(summary, baseline=calibrated_baseline)
    assert result.threat_type == ThreatType.FLASH_CROWD
    assert result.is_flash_crowd
    assert not result.is_threat
    assert result.recommended_action == RecommendedAction.ALLOW
    assert "legitimate organic demand" in result.reasons[0].lower()


def test_classify_single_source_flood(
    calibrated_baseline: AdaptiveTelemetryBaseline,
) -> None:
    """Verifies that concentrated traffic from a single/few clients is flagged as SINGLE_SOURCE_FLOOD."""
    summary = LiveTelemetrySummaryResponse(
        window_duration_seconds=10.0,
        total_requests=800,
        requests_per_second=80.0,
        bytes_per_second=40000.0,
        status_codes=StatusCodeDistribution(
            c_2xx=800, pct_2xx=100.0, error_rate_pct=0.0
        ),
        latencies=LatencyPercentiles(p50_ms=15.0, p95_ms=25.0, avg_ms=18.0),
        client_metrics=ClientEntropyMetrics(
            unique_clients=1, shannon_entropy=0.0, entropy_ratio=0.0
        ),
        top_uris=[TopUriItem(uri="/api/items", count=800, pct=100.0)],
        top_methods={"GET": 800},
        is_anomaly=True,
    )

    result = classify_telemetry_snapshot(summary, baseline=calibrated_baseline)
    assert result.threat_type == ThreatType.SINGLE_SOURCE_FLOOD
    assert result.is_threat
    assert not result.is_flash_crowd
    assert result.severity == ThreatSeverity.HIGH
    assert result.recommended_action == RecommendedAction.BLOCK_IP


def test_classify_credential_stuffing(
    calibrated_baseline: AdaptiveTelemetryBaseline,
) -> None:
    """Verifies that an error spike targeting authentication endpoints is flagged as CREDENTIAL_STUFFING."""
    summary = LiveTelemetrySummaryResponse(
        window_duration_seconds=10.0,
        total_requests=400,
        requests_per_second=40.0,
        bytes_per_second=20000.0,
        status_codes=StatusCodeDistribution(
            c_2xx=100, c_4xx=300, pct_2xx=25.0, error_rate_pct=75.0
        ),
        latencies=LatencyPercentiles(p50_ms=25.0, p95_ms=60.0, avg_ms=30.0),
        client_metrics=ClientEntropyMetrics(
            unique_clients=15, shannon_entropy=2.5, entropy_ratio=0.65
        ),
        top_uris=[TopUriItem(uri="/api/v1/auth/login", count=380, pct=95.0)],
        top_methods={"POST": 400},
        is_anomaly=True,
    )

    result = classify_telemetry_snapshot(summary, baseline=calibrated_baseline)
    assert result.threat_type == ThreatType.CREDENTIAL_STUFFING_ERROR_BURST
    assert result.is_threat
    assert result.severity in (ThreatSeverity.HIGH, ThreatSeverity.CRITICAL)
    assert result.recommended_action == RecommendedAction.CHALLENGE_CAPTCHA


def test_classify_slowloris_exhaustion(
    calibrated_baseline: AdaptiveTelemetryBaseline,
) -> None:
    """Verifies that severe latency inflation with low byte throughput is classified as SLOWLORIS."""
    summary = LiveTelemetrySummaryResponse(
        window_duration_seconds=10.0,
        total_requests=50,
        requests_per_second=5.0,
        bytes_per_second=250.0,  # Very low data rate
        status_codes=StatusCodeDistribution(c_2xx=30, c_5xx=20, error_rate_pct=40.0),
        latencies=LatencyPercentiles(
            p50_ms=1800.0, p95_ms=4500.0, avg_ms=2200.0
        ),  # Extreme latency
        client_metrics=ClientEntropyMetrics(
            unique_clients=8, shannon_entropy=2.2, entropy_ratio=0.73
        ),
        top_uris=[TopUriItem(uri="/api/stream", count=50, pct=100.0)],
        top_methods={"GET": 50},
        is_anomaly=True,
    )

    result = classify_telemetry_snapshot(summary, baseline=calibrated_baseline)
    assert result.threat_type == ThreatType.SLOWLORIS_CONNECTION_EXHAUSTION
    assert result.is_threat
    assert result.recommended_action == RecommendedAction.TERMINATE_SLOW_CONNECTIONS


def test_classify_candidate_target_ips_propagation(
    calibrated_baseline: AdaptiveTelemetryBaseline,
) -> None:
    """Verifies that top offender client IPs are attributed into candidate_target_ips when threat is detected."""
    from app.ingestion.telemetry_schemas import TopClientItem

    summary = LiveTelemetrySummaryResponse(
        window_duration_seconds=10.0,
        total_requests=800,
        requests_per_second=80.0,
        bytes_per_second=40000.0,
        status_codes=StatusCodeDistribution(
            c_2xx=800, pct_2xx=100.0, error_rate_pct=0.0
        ),
        latencies=LatencyPercentiles(p50_ms=15.0, p95_ms=25.0, avg_ms=18.0),
        client_metrics=ClientEntropyMetrics(
            unique_clients=1, shannon_entropy=0.0, entropy_ratio=0.0
        ),
        top_uris=[TopUriItem(uri="/api/items", count=800, pct=100.0)],
        top_clients=[TopClientItem(client_ip="198.51.100.77", count=800, pct=100.0)],
        top_methods={"GET": 800},
        is_anomaly=True,
    )

    result = classify_telemetry_snapshot(summary, baseline=calibrated_baseline)
    assert result.is_threat
    assert result.candidate_target_ips == ["198.51.100.77"]
