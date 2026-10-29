"""Unit tests for Adaptive EWMA Baselines & Z-Score Anomaly Calculation."""

from __future__ import annotations

import pytest

from app.detection.baselines import AdaptiveTelemetryBaseline, MetricBaseline


def test_metric_baseline_initialization_and_update() -> None:
    """Verifies that MetricBaseline correctly updates mean and variance."""
    metric = MetricBaseline(alpha=0.2, beta=0.2)
    assert metric.samples_count == 0

    # First observation seeds mean and estimated variance
    metric.update(100.0)
    assert metric.samples_count == 1
    assert metric.mean == 100.0
    assert metric.variance > 0.0

    # Subsequent updates move mean towards new value smoothly
    metric.update(120.0)
    assert metric.samples_count == 2
    # mean = 100 + 0.2 * (120 - 100) = 104.0
    assert metric.mean == pytest.approx(104.0)


def test_z_score_calculation() -> None:
    """Verifies Z-score reflects deviation in units of standard deviation."""
    metric = MetricBaseline(alpha=0.2, beta=0.2)
    metric.mean = 50.0
    metric.variance = 100.0  # std_dev = 10.0
    metric.samples_count = 10

    # Observation at mean gives Z = 0
    assert metric.calculate_z_score(50.0) == pytest.approx(0.0, abs=0.01)

    # Observation at mean + 3*sigma gives Z = 3.0
    assert metric.calculate_z_score(80.0) == pytest.approx(3.0, abs=0.01)

    # Observation below mean gives negative Z
    assert metric.calculate_z_score(20.0) == pytest.approx(-3.0, abs=0.01)


def test_adaptive_telemetry_baseline_multi_metric() -> None:
    """Verifies multi-metric baseline updating and Z-score output."""
    baseline = AdaptiveTelemetryBaseline()
    baseline.calibrate(
        initial_rps=20.0,
        initial_error_pct=1.0,
        initial_p95_ms=30.0,
        initial_bps=10000.0,
    )

    summary = baseline.get_summary()
    assert summary["samples_count"] >= 10
    assert summary["rps"]["mean"] == pytest.approx(20.0, abs=1.0)
    assert summary["error_rate_pct"]["mean"] == pytest.approx(1.0, abs=0.5)

    # Incoming normal metrics should have low Z-scores
    normal_z = baseline.compute_z_scores(
        rps=22.0, error_rate_pct=1.2, p95_ms=32.0, bytes_per_sec=10500.0
    )
    assert abs(normal_z["z_rps"]) < 2.0
    assert abs(normal_z["z_error_rate"]) < 2.0

    # Incoming massive spike should trigger high Z-score
    spike_z = baseline.compute_z_scores(
        rps=500.0, error_rate_pct=45.0, p95_ms=3500.0, bytes_per_sec=200000.0
    )
    assert spike_z["z_rps"] > 3.0
    assert spike_z["z_error_rate"] > 3.0
    assert spike_z["z_p95_latency"] > 3.0
