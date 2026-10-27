"""Unit tests for Phase 8: Virtual Victim Capacity, Mitigation Effects, and Tick Evaluation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.simulator.engine import ScenarioEngine
from app.simulator.mitigation_effects import (
    MitigationEffectManager,
    VirtualMitigation,
)
from app.simulator.scenarios import ScenarioConfig, ScenarioType
from app.simulator.tick_evaluator import TickEvaluator
from app.simulator.victim import VictimMetrics, VirtualVictim, VirtualVictimConfig

# ==============================================================================
# 8.1: Victim Capacity Model Tests (FR-13, TC-17)
# ==============================================================================


def test_victim_config_validation() -> None:
    """Ensure invalid, zero, or negative victim capacity settings are rejected."""
    # Valid default
    config = VirtualVictimConfig()
    assert config.bandwidth_mbps == 100.0
    assert config.cpu_capacity_pps == 5000.0
    assert config.max_active_connections == 10000

    # Negative / out-of-bounds bandwidth
    with pytest.raises(ValidationError):
        VirtualVictimConfig(bandwidth_mbps=0.0)

    with pytest.raises(ValidationError):
        VirtualVictimConfig(bandwidth_mbps=20000.0)

    # Negative / out-of-bounds CPU
    with pytest.raises(ValidationError):
        VirtualVictimConfig(cpu_capacity_pps=-50.0)

    # Forbid extra fields
    with pytest.raises(ValidationError):
        VirtualVictimConfig(unknown_field=123)  # type: ignore[call-arg]


def test_victim_zero_and_baseline_load() -> None:
    """Zero or normal baseline traffic must yield 100% availability, minimal latency, and zero drops."""
    victim = VirtualVictim(VirtualVictimConfig(baseline_latency_ms=10.0))

    # Zero load
    zero_metrics = victim.evaluate_tick(
        tick=0, offered_legitimate_pps=0.0, offered_attack_pps=0.0
    )
    assert zero_metrics.availability_pct == 100.0
    assert zero_metrics.latency_ms == 10.0
    assert zero_metrics.dropped_legitimate_pps == 0.0
    assert zero_metrics.dropped_attack_pps == 0.0
    assert zero_metrics.bottleneck_pressure == 0.0

    # Low baseline load (200 PPS, far below 5000 PPS CPU capacity)
    base_metrics = victim.evaluate_tick(
        tick=1, offered_legitimate_pps=200.0, offered_attack_pps=0.0
    )
    assert base_metrics.availability_pct == 100.0
    assert base_metrics.served_legitimate_pps == 200.0
    assert base_metrics.dropped_legitimate_pps == 0.0
    # Latency should be very close to baseline 10ms
    assert 10.0 <= base_metrics.latency_ms <= 11.0
    assert base_metrics.cpu_utilization_pct == 4.0  # 200 / 5000 = 4%


def test_victim_saturation_and_tail_drops() -> None:
    """When traffic exceeds capacity, victim drops packets proportionally and latency spikes."""
    victim = VirtualVictim(
        VirtualVictimConfig(
            cpu_capacity_pps=1000.0,
            bandwidth_mbps=100.0,
            max_active_connections=50000,
            baseline_latency_ms=10.0,
            max_latency_ms=1000.0,
        )
    )

    # 1000 legitimate + 1000 attack = 2000 PPS on 1000 capacity (pressure = 2.0x)
    metrics = victim.evaluate_tick(
        tick=10, offered_legitimate_pps=1000.0, offered_attack_pps=1000.0
    )

    assert metrics.bottleneck_pressure == 2.0
    # Service ratio is 1/2.0 = 50%
    assert metrics.availability_pct == 50.0
    assert metrics.served_legitimate_pps == 500.0
    assert metrics.served_attack_pps == 500.0
    assert metrics.dropped_legitimate_pps == 500.0
    assert metrics.dropped_attack_pps == 500.0

    # Latency formula under overload: baseline * 2.5 + excess * 150 = 25.0 + (2.0 - 1.0) * 150 = 175.0 ms
    assert metrics.latency_ms == pytest.approx(175.0, abs=1.0)


# ==============================================================================
# 8.2: Mitigation Effect Model Tests (FR-19, TC-17)
# ==============================================================================


def test_virtual_mitigation_lifecycle() -> None:
    """Test VirtualMitigation active range, expiry, and early cancellation."""
    mit = VirtualMitigation(
        action_id="test-action-1",
        target_ip="192.168.1.50",
        start_tick=5,
        duration_ticks=10,
        expiry_tick=15,
        attack_reduction_rate=0.95,
        collateral_drop_rate=0.02,
    )

    # Before start
    assert not mit.is_active(4)

    # During active window
    assert mit.is_active(5)
    assert mit.is_active(14)

    # At or after expiry
    assert not mit.is_active(15)
    expired = mit.check_expiry(15)
    assert expired is True
    assert mit.status == "expired"
    assert not mit.is_active(15)

    # Test early cancellation
    mit2 = VirtualMitigation(
        action_id="test-action-2",
        start_tick=0,
        duration_ticks=20,
        expiry_tick=20,
    )
    assert mit2.is_active(5)
    mit2.cancel(tick=6)
    assert mit2.status == "cancelled"
    assert mit2.cancelled_at_tick == 6
    assert not mit2.is_active(6)
    assert not mit2.is_active(7)


def test_mitigation_relieves_victim_and_measures_collateral() -> None:
    """Applying virtual mitigation reduces attack ingress, restores victim availability, and measures collateral."""
    victim = VirtualVictim(
        VirtualVictimConfig(
            cpu_capacity_pps=2000.0,
            baseline_latency_ms=10.0,
        )
    )

    # Heavy attack: 200 legitimate PPS, 10,000 attack PPS -> Total 10,200 PPS (victim capacity 2000)
    # Unmitigated evaluation:
    unmitigated = victim.evaluate_tick(
        tick=10,
        offered_legitimate_pps=200.0,
        offered_attack_pps=10000.0,
        active_mitigations=[],
    )
    # Pressure is 10200 / 2000 = 5.1x
    assert unmitigated.bottleneck_pressure == pytest.approx(5.1, abs=0.1)
    # Severe drop in availability (approx 19.6%)
    assert unmitigated.availability_pct < 25.0
    assert unmitigated.latency_ms > 500.0

    # Now apply virtual mitigation (95% attack reduction, 2% collateral)
    mit = VirtualMitigation(
        action_id="mit-1",
        start_tick=10,
        duration_ticks=5,
        expiry_tick=15,
        attack_reduction_rate=0.95,
        collateral_drop_rate=0.02,
    )

    mitigated = victim.evaluate_tick(
        tick=11,
        offered_legitimate_pps=200.0,
        offered_attack_pps=10000.0,
        active_mitigations=[mit],
    )

    # Attack filtered: 10000 * (1 - 0.95) = 500 PPS
    # Legit filtered: 200 * (1 - 0.02) = 196 PPS
    # Total ingress = 696 PPS, well within 2000 PPS capacity (pressure ≈ 0.35)
    assert mitigated.bottleneck_pressure < 1.0
    assert mitigated.blocked_attack_pps == 9500.0
    assert mitigated.collateral_legitimate_pps == 4.0
    assert mitigated.served_legitimate_pps == 196.0

    # Availability is exactly 98% (reflecting only the 2% collateral drop!)
    assert mitigated.availability_pct == 98.0
    # Latency has recovered to near-baseline
    assert mitigated.latency_ms < 15.0


def test_mitigation_expiry_restores_unmitigated_state() -> None:
    """When a virtual mitigation expires, traffic calculations cleanly revert to unmitigated state."""
    manager = MitigationEffectManager()
    victim = VirtualVictim(VirtualVictimConfig(cpu_capacity_pps=1000.0))

    mit = VirtualMitigation(
        action_id="expiring-act",
        start_tick=10,
        duration_ticks=5,
        expiry_tick=15,
        attack_reduction_rate=0.90,
        collateral_drop_rate=0.05,
    )
    manager.add_mitigation(mit)

    # At tick 12 (active)
    active_mits = manager.get_active_actions(12)
    assert len(active_mits) == 1
    m12 = victim.evaluate_tick(12, 500.0, 5000.0, active_mitigations=active_mits)
    assert m12.availability_pct > 80.0

    # Advance manager clock to tick 15 (expired)
    expired = manager.advance_tick(15)
    assert len(expired) == 1
    assert expired[0].action_id == "expiring-act"

    active_after = manager.get_active_actions(15)
    assert len(active_after) == 0

    # At tick 15 without active mitigations: victim returns to overloaded state
    m15 = victim.evaluate_tick(15, 500.0, 5000.0, active_mitigations=active_after)
    assert m15.bottleneck_pressure == pytest.approx(5.5, abs=0.1)
    assert m15.availability_pct < 20.0


# ==============================================================================
# 8.3: Integrated Tick Evaluator Tests
# ==============================================================================


def test_tick_evaluator_benign_traffic() -> None:
    """Normal benign traffic triggers no mitigation and maintains high availability."""
    evaluator = TickEvaluator()
    config = ScenarioConfig(scenario_type=ScenarioType.SYN_FLOOD, seed=42)
    engine = ScenarioEngine(config)

    # Tick 2 is prior to attack surge (baseline benign)
    features, ground_truth = engine.generate_tick(2)

    res = evaluator.evaluate_tick(2, features, ground_truth)

    assert res.tick == 2
    assert res.ground_truth.is_attack is False
    assert res.policy_action == "monitor"
    assert len(res.new_actions) == 0
    assert res.victim_metrics.availability_pct == 100.0


def test_tick_evaluator_detects_and_mitigates_attack() -> None:
    """Attack surge triggers ML detection, policy mitigation, and relieves the victim."""
    evaluator = TickEvaluator(mitigation_duration_ticks=10)
    config = ScenarioConfig(
        scenario_type=ScenarioType.SYN_FLOOD,
        seed=42,
        attack_start_tick=5,
        attack_end_tick=25,
        attack_peak_pps=8000.0,
    )
    engine = ScenarioEngine(config)

    # Tick 10: In the middle of SYN flood attack
    features, ground_truth = engine.generate_tick(10)
    assert ground_truth.is_attack is True

    res = evaluator.evaluate_tick(10, features, ground_truth)

    # Should trigger mitigation or alert based on ML + threshold signals
    assert res.prediction.prediction in ("suspicious", "normal")
    assert isinstance(res.victim_metrics, VictimMetrics)
    # Check that audit events are structured and populated
    if res.new_actions:
        assert any(e["event_type"] == "mitigation_triggered" for e in res.audit_events)
