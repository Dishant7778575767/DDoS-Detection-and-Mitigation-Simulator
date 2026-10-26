"""Threshold-based traffic evaluation."""

from __future__ import annotations

from typing import Any

from app.storage.models import ThresholdConfigModel


def evaluate_traffic_thresholds(
    features: dict[str, Any],
    config: ThresholdConfigModel,
) -> tuple[bool, list[str]]:
    """Evaluate whether flow observations or window metrics exceed configured traffic thresholds."""
    violations: list[str] = []

    # Check forward packet rate
    fwd_pps = float(features.get("Fwd Packets/s", 0.0))
    if fwd_pps > config.pps_threshold:
        violations.append(
            f"Packet rate {fwd_pps:.1f} pps exceeded threshold {config.pps_threshold:.1f} pps"
        )

    # Check byte rate
    byte_rate = float(features.get("Flow Bytes/s", 0.0))
    if byte_rate > config.bps_threshold:
        violations.append(
            f"Byte rate {byte_rate:.1f} Bps exceeded threshold {config.bps_threshold:.1f} Bps"
        )

    # Check forward PSH / SYN burst flag activity if available
    psh_flags = float(features.get("Fwd PSH Flags", 0.0))
    if psh_flags > config.syn_pps_threshold:
        violations.append(
            f"Flag burst count {psh_flags:.0f} exceeded threshold {config.syn_pps_threshold:.0f}"
        )

    is_exceeded = len(violations) > 0
    return is_exceeded, violations
