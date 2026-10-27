"""Scorecard calculation and evaluation metrics for simulation runs.

Part of Phase 9 (Work Packages 9.1 & 9.2): Computes reproducible, ground-truth-aware
metrics including Time-to-Detect (TTD), Time-to-Mitigate (TTM), Attack Traffic Blocked %,
Collateral Legitimate Traffic %, Downtime seconds, Precision, Recall, and False-Positive Rate.
Handles undefined denominators explicitly (returns None / null, never misleading zeros).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.simulator.tick_evaluator import TickEvaluationResult


class SimulationScorecard(BaseModel):
    """Ground-truth aware scorecard metrics for a simulation run."""

    model_config = {"extra": "forbid"}

    # Time-to metrics (None if undefined, e.g. no attack or never detected/mitigated)
    time_to_detect_seconds: float | None = Field(
        default=None,
        description="Elapsed virtual seconds from attack start until first detection",
    )
    time_to_mitigate_seconds: float | None = Field(
        default=None,
        description="Elapsed virtual seconds from attack start until mitigation took effect",
    )

    # Traffic outcome percentages (None if zero offered traffic in denominator)
    attack_traffic_blocked_pct: float | None = Field(
        default=None,
        description="Percentage of offered attack packets dropped by mitigation (0-100%)",
    )
    collateral_legitimate_pct: float | None = Field(
        default=None,
        description="Percentage of legitimate packets dropped due to mitigation or bottleneck (0-100%)",
    )

    # Service impact
    downtime_seconds: int = Field(
        default=0,
        ge=0,
        description="Total virtual seconds where service availability fell below threshold",
    )
    average_availability_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Mean availability across all ticks"
    )
    average_latency_ms: float = Field(
        ..., ge=0.0, description="Mean latency across all ticks in milliseconds"
    )
    max_latency_ms: float = Field(
        ..., ge=0.0, description="Maximum peak latency observed across all ticks"
    )

    # Classification & confusion matrix
    total_ticks: int = Field(..., ge=0)
    attack_ticks: int = Field(..., ge=0)
    benign_ticks: int = Field(..., ge=0)
    true_positives: int = Field(..., ge=0)
    false_positives: int = Field(..., ge=0)
    true_negatives: int = Field(..., ge=0)
    false_negatives: int = Field(..., ge=0)

    # Detection quality metrics (None if denominator is zero)
    precision: float | None = Field(
        default=None, description="TP / (TP + FP); None if TP + FP == 0"
    )
    recall: float | None = Field(
        default=None, description="TP / (TP + FN); None if TP + FN == 0"
    )
    false_positive_rate: float | None = Field(
        default=None, description="FP / (FP + TN); None if FP + TN == 0"
    )

    # Raw volume aggregates
    total_offered_attack_packets: float = Field(..., ge=0.0)
    total_blocked_attack_packets: float = Field(..., ge=0.0)
    total_offered_legitimate_packets: float = Field(..., ge=0.0)
    total_dropped_legitimate_packets: float = Field(..., ge=0.0)

    # Provenance
    simulator_version: str = Field(default="1.5.0")
    model_version: str = Field(default="rf-1.0.0")
    schema_version: str = Field(default="1.0.0")


def compute_scorecard(
    tick_results: list[TickEvaluationResult],
    seconds_per_tick: float = 1.0,
    downtime_availability_threshold: float = 50.0,
    simulator_version: str = "1.5.0",
    model_version: str = "rf-1.0.0",
    schema_version: str = "1.0.0",
) -> SimulationScorecard:
    """Compute reproducible, ground-truth-aware scorecard metrics from simulation tick results.

    Undefined denominators:
    - If there are zero attack ticks in the scenario:
      TTD, TTM, Attack Blocked %, and Recall are None.
    - If no alarms fired (TP + FP == 0):
      Precision is None.
    - If there are zero benign ticks (FP + TN == 0):
      FPR is None.
    """
    total_ticks = len(tick_results)
    if total_ticks == 0:
        return SimulationScorecard(
            total_ticks=0,
            attack_ticks=0,
            benign_ticks=0,
            true_positives=0,
            false_positives=0,
            true_negatives=0,
            false_negatives=0,
            total_offered_attack_packets=0.0,
            total_blocked_attack_packets=0.0,
            total_offered_legitimate_packets=0.0,
            total_dropped_legitimate_packets=0.0,
            average_availability_pct=100.0,
            average_latency_ms=0.0,
            max_latency_ms=0.0,
            simulator_version=simulator_version,
            model_version=model_version,
            schema_version=schema_version,
        )

    attack_start_tick: int | None = None
    first_detect_tick: int | None = None
    first_mitigate_tick: int | None = None

    attack_ticks = 0
    benign_ticks = 0
    tp = 0
    fp = 0
    tn = 0
    fn = 0

    total_offered_attack = 0.0
    total_blocked_attack = 0.0
    total_offered_legit = 0.0
    total_dropped_legit = 0.0

    sum_availability = 0.0
    sum_latency = 0.0
    max_latency = 0.0
    downtime_ticks = 0

    for r in tick_results:
        gt = r.ground_truth
        vm = r.victim_metrics
        pred_positive = r.prediction.prediction == "suspicious" or r.policy_action in (
            "alert",
            "request_mitigation",
        )

        # Track first attack tick
        if gt.is_attack:
            attack_ticks += 1
            if attack_start_tick is None:
                attack_start_tick = r.tick

            if pred_positive:
                tp += 1
                if first_detect_tick is None:
                    first_detect_tick = r.tick
            else:
                fn += 1
        else:
            benign_ticks += 1
            if pred_positive:
                fp += 1
            else:
                tn += 1

        # Track first mitigation tick (active mitigation filtering attack)
        if (
            gt.is_attack
            and first_mitigate_tick is None
            and (
                vm.blocked_attack_pps > 0
                or any(
                    m.start_tick <= r.tick < m.expiry_tick for m in r.active_mitigations
                )
            )
        ):
            first_mitigate_tick = r.tick

        # Volume aggregations
        total_offered_attack += vm.offered_attack_pps * seconds_per_tick
        total_blocked_attack += vm.blocked_attack_pps * seconds_per_tick
        total_offered_legit += vm.offered_legitimate_pps * seconds_per_tick
        total_dropped_legit += vm.dropped_legitimate_pps * seconds_per_tick

        sum_availability += vm.availability_pct
        sum_latency += vm.latency_ms
        max_latency = max(max_latency, vm.latency_ms)

        if vm.availability_pct < downtime_availability_threshold:
            downtime_ticks += 1

    # Time-to-Detect (TTD)
    time_to_detect: float | None = None
    if attack_start_tick is not None and first_detect_tick is not None:
        time_to_detect = max(
            0.0, (first_detect_tick - attack_start_tick) * seconds_per_tick
        )

    # Time-to-Mitigate (TTM)
    time_to_mitigate: float | None = None
    if attack_start_tick is not None and first_mitigate_tick is not None:
        time_to_mitigate = max(
            0.0, (first_mitigate_tick - attack_start_tick) * seconds_per_tick
        )

    # Attack traffic blocked %
    attack_blocked_pct: float | None = None
    if total_offered_attack > 0.0:
        attack_blocked_pct = round(
            min(100.0, max(0.0, (total_blocked_attack / total_offered_attack) * 100.0)),
            2,
        )

    # Collateral legitimate traffic %
    collateral_legit_pct: float | None = None
    if total_offered_legit > 0.0:
        collateral_legit_pct = round(
            min(100.0, max(0.0, (total_dropped_legit / total_offered_legit) * 100.0)),
            2,
        )

    # Precision
    precision: float | None = None
    if (tp + fp) > 0:
        precision = round(tp / (tp + fp), 4)

    # Recall
    recall: float | None = None
    if (tp + fn) > 0:
        recall = round(tp / (tp + fn), 4)

    # False Positive Rate (FPR)
    fpr: float | None = None
    if (fp + tn) > 0:
        fpr = round(fp / (fp + tn), 4)

    avg_avail = round(sum_availability / total_ticks, 2)
    avg_latency = round(sum_latency / total_ticks, 2)
    downtime_seconds = int(downtime_ticks * seconds_per_tick)

    return SimulationScorecard(
        time_to_detect_seconds=time_to_detect,
        time_to_mitigate_seconds=time_to_mitigate,
        attack_traffic_blocked_pct=attack_blocked_pct,
        collateral_legitimate_pct=collateral_legit_pct,
        downtime_seconds=downtime_seconds,
        average_availability_pct=avg_avail,
        average_latency_ms=avg_latency,
        max_latency_ms=round(max_latency, 2),
        total_ticks=total_ticks,
        attack_ticks=attack_ticks,
        benign_ticks=benign_ticks,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        false_positive_rate=fpr,
        total_offered_attack_packets=round(total_offered_attack, 2),
        total_blocked_attack_packets=round(total_blocked_attack, 2),
        total_offered_legitimate_packets=round(total_offered_legit, 2),
        total_dropped_legitimate_packets=round(total_dropped_legit, 2),
        simulator_version=simulator_version,
        model_version=model_version,
        schema_version=schema_version,
    )
