"""Hybrid Policy Engine for SENTRIX.

Implements the dual-signal decision matrix:
- Neither signal: "monitor"
- Exactly one signal (ML only OR threshold only): "alert"
- Both signals (ML AND threshold): "request_mitigation"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.detection.predictor import FlowPrediction
from app.detection.scoring import evaluate_ml_threat
from app.policy.thresholds import evaluate_traffic_thresholds
from app.storage.models import ThresholdConfigModel


@dataclass
class PolicyDecision:
    """Outcome of hybrid policy evaluation."""

    action: str  # "monitor", "alert", "request_mitigation"
    ml_threat_detected: bool
    threshold_exceeded: bool
    reasons: list[str]


def evaluate_hybrid_policy(
    prediction: FlowPrediction,
    features: dict[str, Any],
    config: ThresholdConfigModel,
) -> PolicyDecision:
    """Evaluate dual-signal hybrid policy combining ML threat detection and static thresholds."""
    ml_threat = evaluate_ml_threat(
        prediction,
        rf_threshold=config.rf_probability_threshold,
        iforest_threshold=config.iforest_score_threshold,
    )
    threshold_exceeded, violations = evaluate_traffic_thresholds(features, config)

    reasons: list[str] = []
    if ml_threat:
        reasons.append(
            f"ML model ({prediction.model_version}) indicated suspicious pattern (score={prediction.score:.4f})"
        )
    if threshold_exceeded:
        reasons.extend(violations)

    if not ml_threat and not threshold_exceeded:
        action = "monitor"
        reasons.append("Traffic is within normal behavioral bounds")
    elif ml_threat and threshold_exceeded:
        action = "request_mitigation"
        reasons.append(
            "Dual-signal consensus: both ML threat and traffic thresholds exceeded"
        )
    else:
        action = "alert"
        reasons.append(
            "Single-signal alert: monitoring evidence gathered; automatic mitigation withheld"
        )

    return PolicyDecision(
        action=action,
        ml_threat_detected=ml_threat,
        threshold_exceeded=threshold_exceeded,
        reasons=reasons,
    )
