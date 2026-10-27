"""Tick evaluator integrating scenario generation, ML inference, policy, victim, and mitigations.

Part of Phase 8 (Work Package 8.3): Integrates synthetic flow features, runtime model
inference, threshold-based policy decision, virtual mitigation lifecycle, and virtual
victim resource QoS without touching host network or operating system state.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.detection.model_loader import load_runtime_model
from app.detection.predictor import FlowPrediction, run_flow_inference
from app.policy.engine import evaluate_hybrid_policy
from app.simulator.mitigation_effects import MitigationEffectManager, VirtualMitigation
from app.simulator.scenarios import GroundTruth
from app.simulator.victim import VictimMetrics, VirtualVictim, VirtualVictimConfig
from app.storage.models import ThresholdConfigModel


class TickEvaluationResult(BaseModel):
    """Full outcome of a single simulated tick execution."""

    model_config = {"extra": "forbid"}

    tick: int = Field(..., ge=0)
    features: dict[str, float]
    ground_truth: GroundTruth
    prediction: FlowPrediction
    policy_action: str
    policy_reasons: list[str]
    victim_metrics: VictimMetrics
    active_mitigations: list[VirtualMitigation]
    new_actions: list[VirtualMitigation]
    expired_actions: list[VirtualMitigation]
    audit_events: list[dict[str, Any]]


class TickEvaluator:
    """Evaluates a single simulation tick combining detection, policy, victim, and mitigations."""

    def __init__(
        self,
        victim_config: VirtualVictimConfig | None = None,
        threshold_config: ThresholdConfigModel | None = None,
        mitigation_duration_ticks: int = 15,
        cooldown_ticks: int = 10,
        model: Any | None = None,
    ) -> None:
        self.victim = VirtualVictim(victim_config or VirtualVictimConfig())
        self.threshold_config = threshold_config or ThresholdConfigModel(
            version="default-1.0.0",
            pps_threshold=5000.0,
            bps_threshold=10_000_000.0,
            syn_pps_threshold=500.0,
            rf_probability_threshold=0.75,
            iforest_score_threshold=0.2664,
            created_at="2026-10-27T00:00:00Z",
        )
        self.mitigation_duration_ticks = mitigation_duration_ticks
        self.cooldown_ticks = cooldown_ticks
        self.mitigation_manager = MitigationEffectManager()
        self.model = model if model is not None else load_runtime_model()
        self._last_mitigation_tick: int | None = None

    def evaluate_tick(
        self,
        tick: int,
        features: dict[str, float],
        ground_truth: GroundTruth,
        target_ip: str = "192.168.1.100",
        target_port: int | None = 80,
    ) -> TickEvaluationResult:
        """Execute complete tick evaluation pipeline."""
        audit_events: list[dict[str, Any]] = []

        # 1. Advance virtual clock and detect expirations
        expired_actions = self.mitigation_manager.advance_tick(tick)
        for exp in expired_actions:
            audit_events.append(
                {
                    "event_type": "mitigation_expired",
                    "action": "expire_simulated_mitigation",
                    "actor": "simulator_engine",
                    "details": {
                        "action_id": exp.action_id,
                        "target_ip": exp.target_ip,
                        "expiry_tick": exp.expiry_tick,
                        "current_tick": tick,
                    },
                }
            )

        # 2. ML model inference on synthetic schema features (Zero label leakage)
        prediction = run_flow_inference(features, model=self.model)

        # 3. Hybrid Policy evaluation (ML consensus + Traffic thresholds)
        policy_decision = evaluate_hybrid_policy(
            prediction, features, self.threshold_config
        )

        # 4. Check for virtual mitigation trigger
        new_actions: list[VirtualMitigation] = []
        if policy_decision.action == "request_mitigation":
            # Check cooldown against last triggered mitigation
            in_cooldown = (
                self._last_mitigation_tick is not None
                and (tick - self._last_mitigation_tick) < self.cooldown_ticks
            )
            # Check if there is already an active mitigation on this target
            has_active_on_target = any(
                m.is_active(tick) and m.target_ip == target_ip
                for m in self.mitigation_manager.all_actions
            )

            if not in_cooldown and not has_active_on_target:
                action_id = f"sim-act-{tick}-{uuid.uuid4().hex[:6]}"
                action = VirtualMitigation(
                    action_id=action_id,
                    target_ip=target_ip,
                    target_port=target_port,
                    action_type="simulate_rate_limit",
                    start_tick=tick,
                    duration_ticks=self.mitigation_duration_ticks,
                    expiry_tick=tick + self.mitigation_duration_ticks,
                    attack_reduction_rate=0.95,
                    collateral_drop_rate=0.02,
                    status="active",
                )
                self.mitigation_manager.add_mitigation(action)
                new_actions.append(action)
                self._last_mitigation_tick = tick

                audit_events.append(
                    {
                        "event_type": "mitigation_triggered",
                        "action": "simulate_rate_limit",
                        "actor": "hybrid_policy",
                        "details": {
                            "action_id": action.action_id,
                            "target_ip": target_ip,
                            "start_tick": action.start_tick,
                            "expiry_tick": action.expiry_tick,
                            "attack_reduction_rate": action.attack_reduction_rate,
                            "collateral_drop_rate": action.collateral_drop_rate,
                        },
                    }
                )

        # 5. Virtual victim resource evaluation
        active_mitigations = self.mitigation_manager.get_active_actions(tick)
        victim_metrics = self.victim.evaluate_tick(
            tick=tick,
            offered_legitimate_pps=ground_truth.legitimate_pps,
            offered_attack_pps=ground_truth.attack_pps,
            active_mitigations=active_mitigations,
        )

        return TickEvaluationResult(
            tick=tick,
            features=features,
            ground_truth=ground_truth,
            prediction=prediction,
            policy_action=policy_decision.action,
            policy_reasons=policy_decision.reasons,
            victim_metrics=victim_metrics,
            active_mitigations=active_mitigations,
            new_actions=new_actions,
            expired_actions=expired_actions,
            audit_events=audit_events,
        )
