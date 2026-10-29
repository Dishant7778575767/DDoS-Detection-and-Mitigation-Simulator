"""Adaptive Traffic Baselining & Z-Score Velocity Anomaly Detection for SENTRIX.

Maintains Exponentially Weighted Moving Average (EWMA) and Exponential Moving Variance
for core L7 metrics:
- Requests Per Second (RPS)
- Error Rate Percentage (4xx + 5xx)
- P95 Latency (ms)
- Byte Throughput (Bytes/sec)

Provides statistical Z-score velocity shifts:
    Z = (x - mean) / (std_dev + epsilon)
"""

from __future__ import annotations

import math
import threading
from typing import Any

from pydantic import BaseModel


class MetricBaseline(BaseModel):
    """Statistical tracking state for an individual metric."""

    mean: float = 0.0
    variance: float = 1.0
    samples_count: int = 0
    alpha: float = 0.15  # Smoothing factor for mean
    beta: float = 0.15  # Smoothing factor for variance

    @property
    def std_dev(self) -> float:
        return math.sqrt(max(self.variance, 1e-6))

    def update(self, value: float) -> None:
        """Update EWMA mean and variance with a new observation."""
        val = float(value)
        if self.samples_count == 0:
            self.mean = val
            # Initialize variance with a reasonable default relative to value
            self.variance = max((val * 0.2) ** 2, 1.0)
            self.samples_count = 1
            return

        diff = val - self.mean
        # Update mean
        self.mean = self.mean + self.alpha * diff
        # Update variance
        self.variance = (1.0 - self.beta) * self.variance + self.beta * (diff**2)
        self.samples_count += 1

    def calculate_z_score(self, value: float) -> float:
        """Calculate statistical Z-score: (value - mean) / std_dev."""
        if self.samples_count == 0:
            return 0.0
        return (float(value) - self.mean) / (self.std_dev + 1e-5)


class AdaptiveTelemetryBaseline:
    """Thread-safe adaptive baseline engine for real-time web telemetry."""

    def __init__(
        self,
        alpha: float = 0.15,
        beta: float = 0.15,
        z_threshold: float = 3.0,
    ) -> None:
        self.alpha = alpha
        self.beta = beta
        self.z_threshold = z_threshold
        # Use RLock (re-entrant lock) to prevent deadlocks when methods call each other
        self._lock = threading.RLock()

        self.rps = MetricBaseline(alpha=alpha, beta=beta)
        self.error_rate = MetricBaseline(alpha=alpha, beta=beta)
        self.p95_latency = MetricBaseline(alpha=alpha, beta=beta)
        self.bytes_per_sec = MetricBaseline(alpha=alpha, beta=beta)

    def update(
        self,
        rps: float,
        error_rate_pct: float,
        p95_ms: float,
        bytes_per_sec: float,
    ) -> None:
        """Update all metric baselines with latest observation."""
        with self._lock:
            self.rps.update(rps)
            self.error_rate.update(error_rate_pct)
            self.p95_latency.update(p95_ms)
            self.bytes_per_sec.update(bytes_per_sec)

    def compute_z_scores(
        self,
        rps: float,
        error_rate_pct: float,
        p95_ms: float,
        bytes_per_sec: float,
    ) -> dict[str, float]:
        """Compute Z-scores for incoming metrics against current baseline."""
        with self._lock:
            return {
                "z_rps": round(self.rps.calculate_z_score(rps), 2),
                "z_error_rate": round(
                    self.error_rate.calculate_z_score(error_rate_pct), 2
                ),
                "z_p95_latency": round(self.p95_latency.calculate_z_score(p95_ms), 2),
                "z_bytes_per_sec": round(
                    self.bytes_per_sec.calculate_z_score(bytes_per_sec), 2
                ),
            }

    def get_summary(self) -> dict[str, Any]:
        """Return snapshot of current baseline statistics."""
        with self._lock:
            return {
                "samples_count": self.rps.samples_count,
                "rps": {
                    "mean": round(self.rps.mean, 2),
                    "std_dev": round(self.rps.std_dev, 2),
                },
                "error_rate_pct": {
                    "mean": round(self.error_rate.mean, 2),
                    "std_dev": round(self.error_rate.std_dev, 2),
                },
                "p95_latency_ms": {
                    "mean": round(self.p95_latency.mean, 2),
                    "std_dev": round(self.p95_latency.std_dev, 2),
                },
                "bytes_per_sec": {
                    "mean": round(self.bytes_per_sec.mean, 2),
                    "std_dev": round(self.bytes_per_sec.std_dev, 2),
                },
            }

    def _reset_locked(self) -> None:
        """Reset internal metrics without acquiring lock. Must hold self._lock."""
        self.rps = MetricBaseline(alpha=self.alpha, beta=self.beta)
        self.error_rate = MetricBaseline(alpha=self.alpha, beta=self.beta)
        self.p95_latency = MetricBaseline(alpha=self.alpha, beta=self.beta)
        self.bytes_per_sec = MetricBaseline(alpha=self.alpha, beta=self.beta)

    def reset(self) -> None:
        """Reset all tracked baselines to initial uncalibrated state."""
        with self._lock:
            self._reset_locked()

    def calibrate(
        self,
        initial_rps: float = 20.0,
        initial_error_pct: float = 1.0,
        initial_p95_ms: float = 25.0,
        initial_bps: float = 15000.0,
        warmup_iterations: int = 15,
    ) -> None:
        """Seed baseline with normal healthy traffic profiles for rapid warm-up."""
        with self._lock:
            self._reset_locked()
            for _ in range(warmup_iterations):
                self.rps.update(initial_rps)
                self.error_rate.update(initial_error_pct)
                self.p95_latency.update(initial_p95_ms)
                self.bytes_per_sec.update(initial_bps)


# Module-level singleton instance calibrated with standard baseline defaults
telemetry_baseline = AdaptiveTelemetryBaseline()
telemetry_baseline.calibrate()
