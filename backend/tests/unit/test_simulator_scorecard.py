"""Unit tests for Phase 9: Simulation Scorecard, Hand-Calculated Fixtures, and Null Edge Cases."""

from __future__ import annotations

import pytest

from app.detection.predictor import FlowPrediction
from app.simulator.mitigation_effects import VirtualMitigation
from app.simulator.scenarios import GroundTruth, ScenarioType
from app.simulator.scorecard import SimulationScorecard, compute_scorecard
from app.simulator.tick_evaluator import TickEvaluationResult
from app.simulator.victim import VictimMetrics


def _create_mock_tick_result(
    tick: int,
    is_attack: bool,
    prediction_str: str,
    policy_action: str,
    offered_legit: float = 200.0,
    offered_attack: float = 0.0,
    blocked_attack: float = 0.0,
    dropped_legit: float = 0.0,
    availability_pct: float = 100.0,
    latency_ms: float = 15.0,
    is_mitigated: bool = False,
) -> TickEvaluationResult:
    """Helper to build a deterministic TickEvaluationResult for hand-calculated verification."""
    gt = GroundTruth(
        tick=tick,
        is_attack=is_attack,
        attack_type=None if not is_attack else ScenarioType.SYN_FLOOD,
        attack_pps=offered_attack,
        legitimate_pps=offered_legit,
        total_pps=offered_legit + offered_attack,
        label="SynFlood" if is_attack else "BENIGN",
    )

    pred = FlowPrediction(
        prediction=prediction_str,
        score=0.90 if prediction_str == "suspicious" else 0.10,
        score_type="random_forest_probability",
        model_version="rf-1.0.0",
        feature_schema_version="1.0.0",
    )

    active_mits = []
    if is_mitigated:
        active_mits.append(
            VirtualMitigation(
                action_id=f"act-{tick}",
                start_tick=tick,
                duration_ticks=5,
                expiry_tick=tick + 5,
                attack_reduction_rate=0.95,
                collateral_drop_rate=0.02,
                status="active",
            )
        )

    vm = VictimMetrics(
        tick=tick,
        offered_legitimate_pps=offered_legit,
        offered_attack_pps=offered_attack,
        offered_total_pps=offered_legit + offered_attack,
        offered_bandwidth_mbps=1.0,
        offered_connections=100,
        blocked_attack_pps=blocked_attack,
        collateral_legitimate_pps=dropped_legit,
        served_legitimate_pps=offered_legit - dropped_legit,
        served_attack_pps=offered_attack - blocked_attack,
        dropped_legitimate_pps=dropped_legit,
        dropped_attack_pps=blocked_attack,
        latency_ms=latency_ms,
        availability_pct=availability_pct,
        bandwidth_utilization_pct=10.0,
        cpu_utilization_pct=10.0,
        connection_utilization_pct=10.0,
        bottleneck_pressure=0.1,
    )

    return TickEvaluationResult(
        tick=tick,
        features={},
        ground_truth=gt,
        prediction=pred,
        policy_action=policy_action,
        policy_reasons=[],
        victim_metrics=vm,
        active_mitigations=active_mits,
        new_actions=[],
        expired_actions=[],
        audit_events=[],
    )


def test_hand_calculated_scorecard_fixture() -> None:
    """Validate scorecard against an exact hand-calculated test sequence.

    Sequence of 10 ticks:
    - Ticks 0-2 (3 ticks): Benign traffic, correctly identified as normal.
      (TN=3)
    - Tick 3 (1 tick): Benign traffic, but false alarm triggered by model.
      (FP=1)
    - Ticks 4-8 (5 ticks): SYN Flood attack (starts at tick 4).
      - Tick 4: Undetected (FN=1)
      - Tick 5: Detected! TTD = 5 - 4 = 1.0s (TP=1)
      - Tick 6: Mitigated! TTM = 6 - 4 = 2.0s (TP=2)
      - Tick 7: Mitigated (TP=3)
      - Tick 8: Mitigated (TP=4)
    - Tick 9 (1 tick): Benign, normal. (TN=4)

    Summary of matrix:
    TP = 4, FP = 1, TN = 4, FN = 1. Total = 10 ticks.
    Precision = 4 / (4 + 1) = 0.8000
    Recall = 4 / (4 + 1) = 0.8000
    FPR = 1 / (1 + 4) = 0.2000
    TTD = 1.0s
    TTM = 2.0s
    """
    ticks = [
        # 0-2: Benign
        _create_mock_tick_result(
            0, is_attack=False, prediction_str="normal", policy_action="monitor"
        ),
        _create_mock_tick_result(
            1, is_attack=False, prediction_str="normal", policy_action="monitor"
        ),
        _create_mock_tick_result(
            2, is_attack=False, prediction_str="normal", policy_action="monitor"
        ),
        # 3: Benign, False Positive
        _create_mock_tick_result(
            3, is_attack=False, prediction_str="suspicious", policy_action="alert"
        ),
        # 4: Attack start, missed (FN)
        _create_mock_tick_result(
            4,
            is_attack=True,
            prediction_str="normal",
            policy_action="monitor",
            offered_attack=5000.0,
            availability_pct=40.0,
        ),
        # 5: Attack detected (TP), not yet mitigated
        _create_mock_tick_result(
            5,
            is_attack=True,
            prediction_str="suspicious",
            policy_action="request_mitigation",
            offered_attack=5000.0,
            availability_pct=40.0,
        ),
        # 6: Attack mitigated (TP)
        _create_mock_tick_result(
            6,
            is_attack=True,
            prediction_str="suspicious",
            policy_action="request_mitigation",
            offered_attack=5000.0,
            blocked_attack=4750.0,
            dropped_legit=4.0,
            is_mitigated=True,
            availability_pct=98.0,
        ),
        # 7: Attack mitigated (TP)
        _create_mock_tick_result(
            7,
            is_attack=True,
            prediction_str="suspicious",
            policy_action="request_mitigation",
            offered_attack=5000.0,
            blocked_attack=4750.0,
            dropped_legit=4.0,
            is_mitigated=True,
            availability_pct=98.0,
        ),
        # 8: Attack mitigated (TP)
        _create_mock_tick_result(
            8,
            is_attack=True,
            prediction_str="suspicious",
            policy_action="request_mitigation",
            offered_attack=5000.0,
            blocked_attack=4750.0,
            dropped_legit=4.0,
            is_mitigated=True,
            availability_pct=98.0,
        ),
        # 9: Benign normal (TN)
        _create_mock_tick_result(
            9, is_attack=False, prediction_str="normal", policy_action="monitor"
        ),
    ]

    scorecard = compute_scorecard(
        ticks, seconds_per_tick=1.0, downtime_availability_threshold=50.0
    )

    assert scorecard.total_ticks == 10
    assert scorecard.attack_ticks == 5
    assert scorecard.benign_ticks == 5

    assert scorecard.true_positives == 4
    assert scorecard.false_positives == 1
    assert scorecard.true_negatives == 4
    assert scorecard.false_negatives == 1

    assert scorecard.precision == pytest.approx(0.8000)
    assert scorecard.recall == pytest.approx(0.8000)
    assert scorecard.false_positive_rate == pytest.approx(0.2000)

    # Time-to-Detect: Attack started at 4, detected at 5 -> 1.0s
    assert scorecard.time_to_detect_seconds == 1.0

    # Time-to-Mitigate: Attack started at 4, mitigated at 6 -> 2.0s
    assert scorecard.time_to_mitigate_seconds == 2.0

    # Downtime: Ticks 4 and 5 had availability 40% (< 50% threshold) -> 2 seconds downtime
    assert scorecard.downtime_seconds == 2

    # Blocked attack packets: 3 ticks with 4750 blocked = 14250. Offered = 5 ticks * 5000 = 25000.
    # % blocked = 14250 / 25000 * 100 = 57.0%
    assert scorecard.attack_traffic_blocked_pct == 57.0


def test_pure_benign_null_denominators() -> None:
    """When a scenario has NO attack traffic, attack metrics must be None, NOT misleading 0.0."""
    ticks = [
        _create_mock_tick_result(
            i, is_attack=False, prediction_str="normal", policy_action="monitor"
        )
        for i in range(10)
    ]

    scorecard = compute_scorecard(ticks)

    assert scorecard.total_ticks == 10
    assert scorecard.attack_ticks == 0
    assert scorecard.benign_ticks == 10

    # Must be None, not 0.0!
    assert scorecard.time_to_detect_seconds is None
    assert scorecard.time_to_mitigate_seconds is None
    assert scorecard.attack_traffic_blocked_pct is None
    assert scorecard.recall is None

    # No false alarms were raised
    assert scorecard.false_positives == 0
    assert scorecard.true_negatives == 10
    assert scorecard.false_positive_rate == 0.0
    # No alarms fired at all -> precision denominator is 0
    assert scorecard.precision is None


def test_empty_ticks_graceful_handling() -> None:
    """Empty run returns a valid default scorecard without exceptions."""
    scorecard = compute_scorecard([])
    assert isinstance(scorecard, SimulationScorecard)
    assert scorecard.total_ticks == 0
    assert scorecard.time_to_detect_seconds is None
    assert scorecard.precision is None
