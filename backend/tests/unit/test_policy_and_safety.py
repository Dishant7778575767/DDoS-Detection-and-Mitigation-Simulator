"""Unit tests for hybrid policy engine and safety gate."""

from app.detection.predictor import FlowPrediction
from app.features.definitions import FEATURE_NAMES
from app.policy.allowlist import is_protected_target
from app.policy.engine import evaluate_hybrid_policy
from app.safety.gate import (
    is_emergency_disabled,
    set_emergency_disabled,
    validate_safety_gate,
)
from app.storage.models import ThresholdConfigModel


def test_hybrid_policy_decision_matrix() -> None:
    """Ensure the dual-signal decision matrix behaves according to architecture:
    - Neither signal: monitor
    - One signal: alert
    - Both signals: request_mitigation
    """
    config = ThresholdConfigModel(
        version="v1.0.0",
        pps_threshold=5000.0,
        bps_threshold=10_000_000.0,
        syn_pps_threshold=500.0,
        rf_probability_threshold=0.75,
    )

    # 1. Neither signal
    normal_pred = FlowPrediction(
        "normal", 0.10, "random_forest_probability", "rf-1.0.0", "1.0.0"
    )
    normal_features = {name: 10.0 for name in FEATURE_NAMES}
    decision = evaluate_hybrid_policy(normal_pred, normal_features, config)
    assert decision.action == "monitor"

    # 2. Only ML signal (threat probability high, traffic rate low)
    threat_pred = FlowPrediction(
        "suspicious", 0.95, "random_forest_probability", "rf-1.0.0", "1.0.0"
    )
    decision_ml_only = evaluate_hybrid_policy(threat_pred, normal_features, config)
    assert decision_ml_only.action == "alert"

    # 3. Only Threshold signal (threat probability low, traffic rate high)
    burst_features = dict(normal_features)
    burst_features["Fwd Packets/s"] = 10000.0  # Exceeds 5000 pps
    decision_thresh_only = evaluate_hybrid_policy(normal_pred, burst_features, config)
    assert decision_thresh_only.action == "alert"

    # 4. Both signals (ML threat AND threshold exceeded)
    decision_both = evaluate_hybrid_policy(threat_pred, burst_features, config)
    assert decision_both.action == "request_mitigation"


def test_safety_gate_allowlist_and_bounds() -> None:
    """Test safety gate checks for protected IPs, parameter bounds, and emergency disable."""
    # Protected IP must be rejected
    assert is_protected_target("127.0.0.1") is True
    assert is_protected_target("8.8.8.8") is True
    assert is_protected_target("192.168.1.50") is False

    res_protected = validate_safety_gate(
        "127.0.0.1", rate_limit_pps=1000, duration_seconds=60
    )
    assert res_protected.allowed is False
    assert "protected infrastructure" in res_protected.rejection_reason

    # Invalid rate bounds
    res_low_rate = validate_safety_gate(
        "192.168.1.50", rate_limit_pps=10, duration_seconds=60
    )
    assert res_low_rate.allowed is False

    # Valid safety gate request
    res_valid = validate_safety_gate(
        "192.168.1.50", rate_limit_pps=1000, duration_seconds=60
    )
    assert res_valid.allowed is True

    # Emergency disable check
    set_emergency_disabled(True)
    assert is_emergency_disabled() is True
    res_emergency = validate_safety_gate(
        "192.168.1.50", rate_limit_pps=1000, duration_seconds=60
    )
    assert res_emergency.allowed is False
    assert "Emergency disable is currently active" in res_emergency.rejection_reason

    # Reset emergency disable
    set_emergency_disabled(False)
    assert is_emergency_disabled() is False
