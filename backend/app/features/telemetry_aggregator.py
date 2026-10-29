"""Real-Time Sliding Window Aggregator for L7 HTTP Telemetry.

Computes:
- Requests Per Second (RPS) and Byte throughput (Bps)
- HTTP Status Code distributions (2xx, 3xx, 4xx, 5xx) and error rate percentage
- Latency percentiles (P50, P90, P95, P99, min, max, avg)
- Client IP diversity and Shannon Entropy (H(X) = -sum(p * log2(p)))
- Top requested URI endpoints and HTTP methods
- Anomaly heuristic detection
"""

from __future__ import annotations

import collections
import datetime
import math
import threading
from typing import NamedTuple

import numpy as np

from app.ingestion.telemetry_schemas import (
    ClientEntropyMetrics,
    LatencyPercentiles,
    LiveTelemetrySummaryResponse,
    RequestTelemetryItem,
    StatusCodeDistribution,
    TopClientItem,
    TopUriItem,
)


class TelemetryRecord(NamedTuple):
    timestamp: float
    client_ip: str
    method: str
    uri: str
    status_code: int
    latency_ms: float
    bytes_sent: int


class TelemetryWindowAggregator:
    """Thread-safe sliding-window metrics aggregator for HTTP request telemetry."""

    def __init__(
        self,
        window_duration_seconds: float = 10.0,
        max_records: int = 100_000,
    ) -> None:
        if window_duration_seconds <= 0:
            raise ValueError("window_duration_seconds must be positive")
        self.window_duration_seconds = window_duration_seconds
        self.max_records = max_records
        self._buffer: collections.deque[TelemetryRecord] = collections.deque(
            maxlen=max_records
        )
        self._lock = threading.Lock()

    def _parse_timestamp(self, ts_str: str) -> float:
        """Parse ISO timestamp or float string into epoch timestamp."""
        try:
            # Check if it's already a float / int epoch string
            return float(ts_str)
        except ValueError:
            pass

        try:
            dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, TypeError, OSError):
            return datetime.datetime.now(datetime.timezone.utc).timestamp()

    def add_item(self, item: RequestTelemetryItem) -> None:
        """Add a single telemetry item into the sliding window."""
        ts = self._parse_timestamp(item.timestamp)
        record = TelemetryRecord(
            timestamp=ts,
            client_ip=item.client_ip,
            method=item.method.upper(),
            uri=item.uri,
            status_code=item.status_code,
            latency_ms=float(item.latency_ms),
            bytes_sent=int(item.bytes_sent),
        )
        with self._lock:
            self._buffer.append(record)

    def add_items(self, items: list[RequestTelemetryItem]) -> None:
        """Batch-add multiple telemetry items under a single lock acquisition."""
        if not items:
            return

        records: list[TelemetryRecord] = []
        for item in items:
            ts = self._parse_timestamp(item.timestamp)
            records.append(
                TelemetryRecord(
                    timestamp=ts,
                    client_ip=item.client_ip,
                    method=item.method.upper(),
                    uri=item.uri,
                    status_code=item.status_code,
                    latency_ms=float(item.latency_ms),
                    bytes_sent=int(item.bytes_sent),
                )
            )

        with self._lock:
            self._buffer.extend(records)

    def _prune_locked(self, cutoff: float, max_future_ts: float | None = None) -> None:
        """Internal prune older records and distant future records. Must be called while holding self._lock."""
        if not self._buffer:
            return

        # Prune out-of-order stale records and future drift timestamps across the buffer
        self._buffer = collections.deque(
            (
                rec
                for rec in self._buffer
                if rec.timestamp >= cutoff
                and (max_future_ts is None or rec.timestamp <= max_future_ts)
            ),
            maxlen=self.max_records,
        )

    def get_summary(
        self,
        current_timestamp: float | None = None,
        window_duration: float | None = None,
    ) -> LiveTelemetrySummaryResponse:
        """Calculate aggregated real-time metrics over the active sliding window."""
        window_sec = (
            float(window_duration)
            if window_duration and window_duration > 0
            else self.window_duration_seconds
        )
        now_ts = (
            float(current_timestamp)
            if current_timestamp is not None
            else datetime.datetime.now(datetime.timezone.utc).timestamp()
        )
        cutoff = now_ts - window_sec
        # Allow minor network clock drift (up to 2.0s), but filter future outliers beyond that
        max_future_ts = now_ts + 2.0

        with self._lock:
            self._prune_locked(cutoff, max_future_ts)
            snapshot = [
                rec for rec in self._buffer if cutoff <= rec.timestamp <= max_future_ts
            ]

        total_requests = len(snapshot)
        effective_window = max(window_sec, 0.1)

        if total_requests == 0:
            return LiveTelemetrySummaryResponse(
                window_duration_seconds=window_sec,
                total_requests=0,
                requests_per_second=0.0,
                bytes_per_second=0.0,
                status_codes=StatusCodeDistribution(),
                latencies=LatencyPercentiles(),
                client_metrics=ClientEntropyMetrics(),
                top_uris=[],
                top_methods={},
                is_anomaly=False,
            )

        total_bytes = 0
        c_2xx = 0
        c_3xx = 0
        c_4xx = 0
        c_5xx = 0
        latencies: list[float] = []
        client_counter: collections.Counter[str] = collections.Counter()
        uri_counter: collections.Counter[str] = collections.Counter()
        method_counter: collections.Counter[str] = collections.Counter()

        for rec in snapshot:
            total_bytes += rec.bytes_sent
            latencies.append(rec.latency_ms)
            client_counter[rec.client_ip] += 1
            uri_counter[rec.uri] += 1
            method_counter[rec.method] += 1

            code = rec.status_code
            if 200 <= code <= 299:
                c_2xx += 1
            elif 300 <= code <= 399:
                c_3xx += 1
            elif 400 <= code <= 499:
                c_4xx += 1
            elif 500 <= code <= 599:
                c_5xx += 1

        rps = round(total_requests / effective_window, 2)
        bps = round(total_bytes / effective_window, 2)

        # Status Code Distribution
        pct_2xx = round((c_2xx / total_requests) * 100.0, 2)
        pct_3xx = round((c_3xx / total_requests) * 100.0, 2)
        pct_4xx = round((c_4xx / total_requests) * 100.0, 2)
        pct_5xx = round((c_5xx / total_requests) * 100.0, 2)
        error_rate_pct = round(((c_4xx + c_5xx) / total_requests) * 100.0, 2)

        status_dist = StatusCodeDistribution(
            c_2xx=c_2xx,
            c_3xx=c_3xx,
            c_4xx=c_4xx,
            c_5xx=c_5xx,
            pct_2xx=pct_2xx,
            pct_3xx=pct_3xx,
            pct_4xx=pct_4xx,
            pct_5xx=pct_5xx,
            error_rate_pct=error_rate_pct,
        )

        # Latency Percentiles
        latencies_arr = np.array(latencies, dtype=np.float64)
        p50, p90, p95, p99 = np.percentile(latencies_arr, [50, 90, 95, 99])
        latency_stats = LatencyPercentiles(
            p50_ms=round(float(p50), 2),
            p90_ms=round(float(p90), 2),
            p95_ms=round(float(p95), 2),
            p99_ms=round(float(p99), 2),
            min_ms=round(float(np.min(latencies_arr)), 2),
            max_ms=round(float(np.max(latencies_arr)), 2),
            avg_ms=round(float(np.mean(latencies_arr)), 2),
        )

        # Shannon Entropy & Client Diversity
        unique_clients = len(client_counter)
        if total_requests > 0 and unique_clients > 1:
            shannon_h = 0.0
            for count in client_counter.values():
                p = count / total_requests
                if p > 0:
                    shannon_h -= p * math.log2(p)
            max_possible_h = math.log2(unique_clients)
            entropy_ratio = (
                round(shannon_h / max_possible_h, 4) if max_possible_h > 0 else 1.0
            )
            shannon_h = round(shannon_h, 4)
            max_possible_h = round(max_possible_h, 4)
        elif unique_clients == 1:
            shannon_h = 0.0
            max_possible_h = 0.0
            entropy_ratio = 0.0
        else:
            shannon_h = 0.0
            max_possible_h = 0.0
            entropy_ratio = 0.0

        client_metrics = ClientEntropyMetrics(
            unique_clients=unique_clients,
            shannon_entropy=shannon_h,
            max_possible_entropy=max_possible_h,
            entropy_ratio=entropy_ratio,
        )

        # Top URIs (up to 10)
        top_uris: list[TopUriItem] = [
            TopUriItem(
                uri=uri,
                count=count,
                pct=round((count / total_requests) * 100.0, 2),
            )
            for uri, count in uri_counter.most_common(10)
        ]

        # Top Clients (up to 10)
        top_clients: list[TopClientItem] = [
            TopClientItem(
                client_ip=ip,
                count=count,
                pct=round((count / total_requests) * 100.0, 2),
            )
            for ip, count in client_counter.most_common(10)
        ]

        # Top Methods
        top_methods = dict(method_counter.most_common(10))

        # Heuristic Anomaly Flag:
        # High error rate (> 30%), high latency (P95 > 2500ms), or massive RPS
        is_anomaly = bool(
            error_rate_pct >= 30.0 or latency_stats.p95_ms >= 2500.0 or rps >= 1500.0
        )

        return LiveTelemetrySummaryResponse(
            window_duration_seconds=window_sec,
            total_requests=total_requests,
            requests_per_second=rps,
            bytes_per_second=bps,
            status_codes=status_dist,
            latencies=latency_stats,
            client_metrics=client_metrics,
            top_uris=top_uris,
            top_clients=top_clients,
            top_methods=top_methods,
            is_anomaly=is_anomaly,
        )

    def reset(self) -> None:
        """Clear all buffered telemetry observations."""
        with self._lock:
            self._buffer.clear()


# Module-level singleton instance
telemetry_aggregator = TelemetryWindowAggregator()
