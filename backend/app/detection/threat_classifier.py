"""Multi-Tier Threat Classifier & Attack Pattern Detector for SENTRIX.

Evaluates real-time HTTP telemetry snapshots through:
1. Statistical velocity Z-scores against adaptive EWMA baselines
2. Signature heuristics (HTTP Volumetric Floods, Slowloris, Credential Stuffing)
3. Flash Crowd vs. Botnet Differentiator using Shannon Entropy and error ratios
4. Explainable root-cause reporting and recommended defense actions
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.detection.baselines import AdaptiveTelemetryBaseline, telemetry_baseline
from app.ingestion.telemetry_schemas import LiveTelemetrySummaryResponse


class ThreatType(str, Enum):
    BENIGN = "BENIGN"
    VOLUMETRIC_HTTP_FLOOD = "VOLUMETRIC_HTTP_FLOOD"
    SLOWLORIS_CONNECTION_EXHAUSTION = "SLOWLORIS_CONNECTION_EXHAUSTION"
    CREDENTIAL_STUFFING_ERROR_BURST = "CREDENTIAL_STUFFING_ERROR_BURST"
    FLASH_CROWD = "FLASH_CROWD"
    SINGLE_SOURCE_FLOOD = "SINGLE_SOURCE_FLOOD"
    BOTNET_DISTRIBUTED_FLOOD = "BOTNET_DISTRIBUTED_FLOOD"


class ThreatSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendedAction(str, Enum):
    ALLOW = "ALLOW"
    MONITOR = "MONITOR"
    RATE_LIMIT = "RATE_LIMIT"
    CHALLENGE_CAPTCHA = "CHALLENGE_CAPTCHA"
    BLOCK_IP = "BLOCK_IP"
    TERMINATE_SLOW_CONNECTIONS = "TERMINATE_SLOW_CONNECTIONS"


class ThreatClassificationResult(BaseModel):
    """Detailed explainable assessment of incoming telemetry."""

    threat_type: ThreatType
    severity: ThreatSeverity
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_threat: bool
    is_flash_crowd: bool
    recommended_action: RecommendedAction
    z_scores: dict[str, float]
    current_metrics: dict[str, float]
    baseline_metrics: dict[str, Any]
    reasons: list[str]
    targeted_endpoints: list[str]
    candidate_target_ips: list[str] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


def classify_telemetry_snapshot(
    summary: LiveTelemetrySummaryResponse,
    baseline: AdaptiveTelemetryBaseline | None = None,
    update_baseline_if_normal: bool = True,
) -> ThreatClassificationResult:
    """Classify live telemetry summary and return explainable threat assessment."""
    if baseline is None:
        baseline = telemetry_baseline

    rps = summary.requests_per_second
    error_rate = summary.status_codes.error_rate_pct
    p95_latency = summary.latencies.p95_ms
    bps = summary.bytes_per_second
    entropy_ratio = summary.client_metrics.entropy_ratio
    unique_clients = summary.client_metrics.unique_clients
    total_reqs = summary.total_requests

    # Compute Z-scores relative to adaptive EWMA baseline
    z_scores = baseline.compute_z_scores(
        rps=rps,
        error_rate_pct=error_rate,
        p95_ms=p95_latency,
        bytes_per_sec=bps,
    )
    z_rps = z_scores["z_rps"]
    z_err = z_scores["z_error_rate"]
    z_lat = z_scores["z_p95_latency"]

    top_endpoints = [item.uri for item in summary.top_uris[:5]]
    candidate_ips = [item.client_ip for item in getattr(summary, "top_clients", [])[:3]]

    current_metrics = {
        "rps": rps,
        "error_rate_pct": error_rate,
        "p95_latency_ms": p95_latency,
        "bytes_per_sec": bps,
        "entropy_ratio": entropy_ratio,
        "unique_clients": float(unique_clients),
        "total_requests": float(total_reqs),
    }

    reasons: list[str] = []

    # If traffic is virtually empty or minimal
    if total_reqs < 3:
        return ThreatClassificationResult(
            threat_type=ThreatType.BENIGN,
            severity=ThreatSeverity.INFO,
            confidence=0.95,
            is_threat=False,
            is_flash_crowd=False,
            recommended_action=RecommendedAction.ALLOW,
            z_scores=z_scores,
            current_metrics=current_metrics,
            baseline_metrics=baseline.get_summary(),
            reasons=["Traffic volume is within normal idle baseline."],
            targeted_endpoints=top_endpoints,
        )

    # -----------------------------------------------------------------------
    # 1. Flash Crowd Evaluation (Critical Differentiator)
    # High RPS + High unique clients + High entropy + Low error rate + Normal latency
    # -----------------------------------------------------------------------
    if (
        (z_rps >= 2.0 or rps >= baseline.rps.mean * 2.0)
        and unique_clients >= 5
        and entropy_ratio >= 0.75
        and error_rate < 10.0
        and summary.status_codes.pct_2xx >= 85.0
        and p95_latency < 1200.0
    ):
        reasons.append(
            f"Traffic surge detected (RPS={rps:.1f}, Z={z_rps:+.1f}), but high client entropy "
            f"({entropy_ratio:.2f}) and high HTTP 2xx ratio ({summary.status_codes.pct_2xx:.1f}%) "
            f"demonstrate legitimate organic demand."
        )
        return ThreatClassificationResult(
            threat_type=ThreatType.FLASH_CROWD,
            severity=ThreatSeverity.LOW,
            confidence=0.92,
            is_threat=False,
            is_flash_crowd=True,
            recommended_action=RecommendedAction.ALLOW,
            z_scores=z_scores,
            current_metrics=current_metrics,
            baseline_metrics=baseline.get_summary(),
            reasons=reasons,
            targeted_endpoints=top_endpoints,
            candidate_target_ips=candidate_ips,
        )

    # -----------------------------------------------------------------------
    # 2. Single-Source Concentrated Flood
    # Elevated RPS + Very low entropy (< 0.30) indicating 1 client blasting traffic
    # -----------------------------------------------------------------------
    if (
        (z_rps >= 2.5 or rps >= 100.0)
        and (entropy_ratio < 0.35 or unique_clients <= 2)
        and total_reqs >= 10
    ):
        reasons.append(
            f"High-frequency request surge (RPS={rps:.1f}, Z={z_rps:+.1f}) concentrated among "
            f"{unique_clients} client(s) with minimal Shannon entropy ({entropy_ratio:.2f})."
        )
        return ThreatClassificationResult(
            threat_type=ThreatType.SINGLE_SOURCE_FLOOD,
            severity=ThreatSeverity.HIGH,
            confidence=0.96,
            is_threat=True,
            is_flash_crowd=False,
            recommended_action=RecommendedAction.BLOCK_IP,
            z_scores=z_scores,
            current_metrics=current_metrics,
            baseline_metrics=baseline.get_summary(),
            reasons=reasons,
            targeted_endpoints=top_endpoints,
            candidate_target_ips=candidate_ips,
        )

    # -----------------------------------------------------------------------
    # 3. Slowloris / Connection Exhaustion
    # P95 latency is extremely high (>= 2000ms) with low byte throughput
    # Evaluated before credential stuffing because thread starvation induces 5xx timeouts
    # -----------------------------------------------------------------------
    avg_bytes_per_req = bps / max(rps, 0.1)
    if (
        (p95_latency >= 2000.0 or z_lat >= 3.5)
        and avg_bytes_per_req < 500.0
        and total_reqs >= 5
    ):
        reasons.append(
            f"Abnormal P95 latency inflation ({p95_latency:.1f}ms, Z={z_lat:+.1f}) paired with "
            f"extremely low data throughput ({avg_bytes_per_req:.1f} B/req), characteristic of Slowloris thread starvation."
        )
        return ThreatClassificationResult(
            threat_type=ThreatType.SLOWLORIS_CONNECTION_EXHAUSTION,
            severity=ThreatSeverity.HIGH,
            confidence=0.88,
            is_threat=True,
            is_flash_crowd=False,
            recommended_action=RecommendedAction.TERMINATE_SLOW_CONNECTIONS,
            z_scores=z_scores,
            current_metrics=current_metrics,
            baseline_metrics=baseline.get_summary(),
            reasons=reasons,
            targeted_endpoints=top_endpoints,
            candidate_target_ips=candidate_ips,
        )

    # -----------------------------------------------------------------------
    # 4. Credential Stuffing / Error Burst Attack
    # High error rate (4xx + 5xx >= 35%, or elevated >= 15% with significant velocity shift)
    # -----------------------------------------------------------------------
    auth_paths = {"/auth", "/login", "/signin", "/token", "/api/v1/auth", "/user/login"}
    is_targeting_auth = any(
        any(auth_kw in uri.lower() for auth_kw in auth_paths) for uri in top_endpoints
    )
    if (
        error_rate >= 35.0 or (error_rate >= 15.0 and z_err >= 3.0)
    ) and total_reqs >= 8:
        reasons.append(
            f"Elevated HTTP error rate of {error_rate:.1f}% (Z={z_err:+.1f}) exceeds defensive threshold."
        )
        if is_targeting_auth:
            reasons.append(
                f"Concentrated failure pattern observed on authentication endpoints: {top_endpoints}"
            )
        severity = (
            ThreatSeverity.CRITICAL
            if (error_rate >= 60.0 or is_targeting_auth)
            else ThreatSeverity.HIGH
        )
        action = (
            RecommendedAction.CHALLENGE_CAPTCHA
            if is_targeting_auth
            else RecommendedAction.RATE_LIMIT
        )

        return ThreatClassificationResult(
            threat_type=ThreatType.CREDENTIAL_STUFFING_ERROR_BURST,
            severity=severity,
            confidence=0.90,
            is_threat=True,
            is_flash_crowd=False,
            recommended_action=action,
            z_scores=z_scores,
            current_metrics=current_metrics,
            baseline_metrics=baseline.get_summary(),
            reasons=reasons,
            targeted_endpoints=top_endpoints,
            candidate_target_ips=candidate_ips,
        )

    # -----------------------------------------------------------------------
    # 5. Volumetric HTTP Flood
    # RPS velocity exceeds 3.0 standard deviations or static ceiling
    # -----------------------------------------------------------------------
    if (z_rps >= 3.0 or rps >= 150.0) and total_reqs >= 15:
        reasons.append(
            f"Volumetric request rate surge ({rps:.1f} RPS, Z={z_rps:+.1f}) breaches baseline statistical capacity."
        )
        # Check if distributed or botnet
        if unique_clients >= 10 and (error_rate >= 20.0 or p95_latency >= 1000.0):
            return ThreatClassificationResult(
                threat_type=ThreatType.BOTNET_DISTRIBUTED_FLOOD,
                severity=ThreatSeverity.CRITICAL,
                confidence=0.94,
                is_threat=True,
                is_flash_crowd=False,
                recommended_action=RecommendedAction.RATE_LIMIT,
                z_scores=z_scores,
                current_metrics=current_metrics,
                baseline_metrics=baseline.get_summary(),
                reasons=reasons,
                targeted_endpoints=top_endpoints,
                candidate_target_ips=candidate_ips,
            )
        else:
            return ThreatClassificationResult(
                threat_type=ThreatType.VOLUMETRIC_HTTP_FLOOD,
                severity=ThreatSeverity.HIGH,
                confidence=0.91,
                is_threat=True,
                is_flash_crowd=False,
                recommended_action=RecommendedAction.RATE_LIMIT,
                z_scores=z_scores,
                current_metrics=current_metrics,
                baseline_metrics=baseline.get_summary(),
                reasons=reasons,
                targeted_endpoints=top_endpoints,
                candidate_target_ips=candidate_ips,
            )

    # -----------------------------------------------------------------------
    # 6. Benign / Normal Traffic
    # -----------------------------------------------------------------------
    reasons.append(
        "All observed telemetry metrics reside within healthy statistical thresholds."
    )

    # Only update baseline when traffic is classified as clean/benign to prevent poison attacks
    if update_baseline_if_normal and total_reqs >= 5:
        baseline.update(
            rps=rps,
            error_rate_pct=error_rate,
            p95_ms=p95_latency,
            bytes_per_sec=bps,
        )

    return ThreatClassificationResult(
        threat_type=ThreatType.BENIGN,
        severity=ThreatSeverity.INFO,
        confidence=0.95,
        is_threat=False,
        is_flash_crowd=False,
        recommended_action=RecommendedAction.ALLOW,
        z_scores=z_scores,
        current_metrics=current_metrics,
        baseline_metrics=baseline.get_summary(),
        reasons=reasons,
        targeted_endpoints=top_endpoints,
    )
