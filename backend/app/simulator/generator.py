"""Deterministic PRNG-based synthetic traffic generator producing Schema 1.0.0 features."""

from __future__ import annotations

import random

from app.features.definitions import FEATURE_NAMES
from app.simulator.scenarios import GroundTruth, ScenarioConfig, ScenarioType


def generate_tick_traffic(
    config: ScenarioConfig,
    tick: int,
    prng: random.Random,
) -> tuple[dict[str, float], GroundTruth]:
    """Generate reproducible Schema 1.0.0 traffic features and ground truth for a given tick.

    The PRNG must be a seeded instance of random.Random so that given the same
    seed and tick sequence, generation is 100% deterministic and reproducible.
    """
    is_in_surge_window = config.attack_start_tick <= tick <= config.attack_end_tick

    # Normal legitimate background jitter (+/- 10%)
    jitter = prng.uniform(0.90, 1.10)
    legit_pps = config.baseline_pps * jitter

    # Calculate ramp-up / sustained attack intensity
    if is_in_surge_window:
        attack_span = max(1, config.attack_end_tick - config.attack_start_tick)
        tick_offset = tick - config.attack_start_tick

        # Triangular / trapezoidal ramp: ramp up in first 20% of window, ramp down in last 10%
        ramp_up_len = max(1, int(attack_span * 0.2))
        ramp_down_len = max(1, int(attack_span * 0.1))

        if tick_offset < ramp_up_len:
            intensity = (tick_offset + 1) / ramp_up_len
        elif tick_offset > attack_span - ramp_down_len:
            intensity = (attack_span - tick_offset) / ramp_down_len
        else:
            intensity = 1.0

        intensity = max(0.1, min(1.0, intensity))
    else:
        intensity = 0.0

    scenario_type = config.scenario_type

    # Flash crowd is high legitimate traffic (NOT an attack)
    if scenario_type == ScenarioType.FLASH_CROWD:
        is_attack = False
        attack_pps = 0.0
        if is_in_surge_window:
            legit_pps += config.attack_peak_pps * intensity * prng.uniform(0.85, 1.05)
        total_pps = legit_pps
        ground_truth_label = "BENIGN"
        active_attack_type = None

    elif is_in_surge_window and intensity > 0:
        is_attack = True
        active_attack_type = scenario_type
        if scenario_type == ScenarioType.LOW_AND_SLOW:
            # Low & slow deliberately stays modest in PPS to challenge rate thresholds
            attack_pps = 600.0 * intensity * prng.uniform(0.95, 1.05)
            ground_truth_label = "LowAndSlow"
        elif scenario_type == ScenarioType.SYN_FLOOD:
            attack_pps = config.attack_peak_pps * intensity * prng.uniform(0.92, 1.08)
            ground_truth_label = "SynFlood"
        elif scenario_type == ScenarioType.UDP_FLOOD:
            attack_pps = config.attack_peak_pps * intensity * prng.uniform(0.95, 1.10)
            ground_truth_label = "UDPFlood"
        elif scenario_type == ScenarioType.HTTP_FLOOD:
            attack_pps = config.attack_peak_pps * intensity * prng.uniform(0.90, 1.05)
            ground_truth_label = "HTTPFlood"
        elif scenario_type == ScenarioType.MIXED:
            attack_pps = config.attack_peak_pps * intensity * prng.uniform(0.90, 1.10)
            ground_truth_label = "MixedAttack"
        else:
            attack_pps = config.attack_peak_pps * intensity
            ground_truth_label = "Attack"
        total_pps = legit_pps + attack_pps
    else:
        is_attack = False
        attack_pps = 0.0
        total_pps = legit_pps
        ground_truth_label = "BENIGN"
        active_attack_type = None

    # Construct Schema 1.0.0 features based on scenario signature
    features = _synthesize_schema_features(
        scenario_type=scenario_type if is_in_surge_window else None,
        total_pps=total_pps,
        is_attack=is_attack,
        prng=prng,
    )

    # Invariant check: Feature dictionary must contain exactly all 14 Schema features
    assert len(features) == len(FEATURE_NAMES), (
        f"Generated feature count ({len(features)}) does not match Schema 1.0.0 ({len(FEATURE_NAMES)})"
    )

    ground_truth = GroundTruth(
        tick=tick,
        is_attack=is_attack,
        attack_type=active_attack_type,
        attack_pps=round(attack_pps, 2),
        legitimate_pps=round(legit_pps, 2),
        total_pps=round(total_pps, 2),
        label=ground_truth_label,
    )

    return features, ground_truth


def _synthesize_schema_features(
    scenario_type: ScenarioType | None,
    total_pps: float,
    is_attack: bool,
    prng: random.Random,
) -> dict[str, float]:
    """Compute 14 statistical flow features tailored to specific traffic profiles."""
    if not is_attack or scenario_type is None:
        # Benign / Baseline or Flash Crowd legitimate traffic
        avg_pkt_len = prng.uniform(250.0, 550.0)
        flow_bps = total_pps * avg_pkt_len
        fwd_iat = max(50.0, 1_000_000.0 / max(1.0, total_pps))

        return {
            "Total Length of Fwd Packets": round(flow_bps * 1.5, 2),
            "Bwd Packet Length Max": round(prng.uniform(1000.0, 1460.0), 2),
            "Flow Bytes/s": round(flow_bps, 2),
            "Fwd IAT Total": round(fwd_iat * 25.0, 2),
            "Bwd IAT Total": round(fwd_iat * 30.0, 2),
            "Fwd PSH Flags": round(prng.uniform(2.0, 10.0), 2),
            "Fwd Packets/s": round(total_pps, 2),
            "FIN Flag Count": round(prng.uniform(1.0, 5.0), 2),
            "Fwd Avg Bytes/Bulk": 0.0,
            "Bwd Avg Bulk Rate": 0.0,
            "Subflow Fwd Packets": round(total_pps * 0.5, 2),
            "Init_Win_bytes_forward": 29200.0,
            "Active Mean": round(prng.uniform(10000.0, 25000.0), 2),
            "Idle Mean": round(prng.uniform(5000.0, 15000.0), 2),
        }

    if scenario_type == ScenarioType.SYN_FLOOD:
        # SYN Flood: Small packets (64 bytes), zero FIN/PSH flags, high SYN window
        avg_pkt_len = 64.0
        flow_bps = total_pps * avg_pkt_len
        fwd_iat = max(1.0, 1_000_000.0 / max(1.0, total_pps))

        return {
            "Total Length of Fwd Packets": round(flow_bps * 1.0, 2),
            "Bwd Packet Length Max": 0.0,  # Unanswered SYNs
            "Flow Bytes/s": round(flow_bps, 2),
            "Fwd IAT Total": round(fwd_iat * 10.0, 2),
            "Bwd IAT Total": 0.0,
            "Fwd PSH Flags": 0.0,
            "Fwd Packets/s": round(total_pps, 2),
            "FIN Flag Count": 0.0,
            "Fwd Avg Bytes/Bulk": 0.0,
            "Bwd Avg Bulk Rate": 0.0,
            "Subflow Fwd Packets": round(total_pps * 0.9, 2),
            "Init_Win_bytes_forward": 29200.0,
            "Active Mean": 5000.0,
            "Idle Mean": 0.0,
        }

    if scenario_type == ScenarioType.UDP_FLOOD:
        # UDP Flood: No TCP handshakes or window sizes, medium/large packet payloads
        avg_pkt_len = prng.uniform(512.0, 1024.0)
        flow_bps = total_pps * avg_pkt_len
        fwd_iat = max(1.0, 1_000_000.0 / max(1.0, total_pps))

        return {
            "Total Length of Fwd Packets": round(flow_bps * 1.2, 2),
            "Bwd Packet Length Max": 0.0,
            "Flow Bytes/s": round(flow_bps, 2),
            "Fwd IAT Total": round(fwd_iat * 5.0, 2),
            "Bwd IAT Total": 0.0,
            "Fwd PSH Flags": 0.0,
            "Fwd Packets/s": round(total_pps, 2),
            "FIN Flag Count": 0.0,
            "Fwd Avg Bytes/Bulk": 0.0,
            "Bwd Avg Bulk Rate": 0.0,
            "Subflow Fwd Packets": round(total_pps * 0.95, 2),
            "Init_Win_bytes_forward": 0.0,  # No TCP Window
            "Active Mean": 1000.0,
            "Idle Mean": 0.0,
        }

    if scenario_type == ScenarioType.HTTP_FLOOD:
        # HTTP Flood: Layer 7 push traffic, high PSH flags, medium payload
        avg_pkt_len = prng.uniform(400.0, 800.0)
        flow_bps = total_pps * avg_pkt_len
        fwd_iat = max(5.0, 1_000_000.0 / max(1.0, total_pps))

        return {
            "Total Length of Fwd Packets": round(flow_bps * 1.8, 2),
            "Bwd Packet Length Max": round(prng.uniform(300.0, 1460.0), 2),
            "Flow Bytes/s": round(flow_bps, 2),
            "Fwd IAT Total": round(fwd_iat * 15.0, 2),
            "Bwd IAT Total": round(fwd_iat * 18.0, 2),
            "Fwd PSH Flags": round(prng.uniform(15.0, 40.0), 2),
            "Fwd Packets/s": round(total_pps, 2),
            "FIN Flag Count": round(prng.uniform(0.0, 1.0), 2),
            "Fwd Avg Bytes/Bulk": 0.0,
            "Bwd Avg Bulk Rate": 0.0,
            "Subflow Fwd Packets": round(total_pps * 0.8, 2),
            "Init_Win_bytes_forward": 29200.0,
            "Active Mean": 8000.0,
            "Idle Mean": 1000.0,
        }

    if scenario_type == ScenarioType.LOW_AND_SLOW:
        # Low & Slow (Slowloris): Low PPS, tiny fragments, huge idle & active durations
        avg_pkt_len = 120.0
        flow_bps = total_pps * avg_pkt_len

        return {
            "Total Length of Fwd Packets": round(flow_bps * 0.5, 2),
            "Bwd Packet Length Max": 100.0,
            "Flow Bytes/s": round(flow_bps, 2),
            "Fwd IAT Total": 40000.0,
            "Bwd IAT Total": 50000.0,
            "Fwd PSH Flags": 2.0,
            "Fwd Packets/s": round(total_pps, 2),
            "FIN Flag Count": 0.0,
            "Fwd Avg Bytes/Bulk": 0.0,
            "Bwd Avg Bulk Rate": 0.0,
            "Subflow Fwd Packets": round(total_pps * 0.5, 2),
            "Init_Win_bytes_forward": 29200.0,
            "Active Mean": 80000.0,  # Extremely long connection hold
            "Idle Mean": 95000.0,  # Idle keepalives
        }

    # Mixed Attack default fallback
    avg_pkt_len = 450.0
    flow_bps = total_pps * avg_pkt_len
    return {
        "Total Length of Fwd Packets": round(flow_bps * 1.4, 2),
        "Bwd Packet Length Max": 200.0,
        "Flow Bytes/s": round(flow_bps, 2),
        "Fwd IAT Total": 500.0,
        "Bwd IAT Total": 800.0,
        "Fwd PSH Flags": 5.0,
        "Fwd Packets/s": round(total_pps, 2),
        "FIN Flag Count": 0.0,
        "Fwd Avg Bytes/Bulk": 0.0,
        "Bwd Avg Bulk Rate": 0.0,
        "Subflow Fwd Packets": round(total_pps * 0.85, 2),
        "Init_Win_bytes_forward": 14600.0,
        "Active Mean": 4000.0,
        "Idle Mean": 500.0,
    }
