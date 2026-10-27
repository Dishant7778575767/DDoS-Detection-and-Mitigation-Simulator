"""Unit tests for Phase 7: Scenario Engine, Determinism, and Ground Truth."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.detection.predictor import run_flow_inference
from app.features.definitions import FEATURE_NAMES
from app.features.preprocess import prepare_feature_vector
from app.simulator.engine import ScenarioEngine
from app.simulator.scenarios import GroundTruth, ScenarioConfig, ScenarioType

# ==============================================================================
# 7.1: Scenario Definitions & Range Validation
# ==============================================================================


def test_scenario_config_defaults() -> None:
    """Ensure default ScenarioConfig conforms to documented bounds."""
    config = ScenarioConfig()
    assert config.scenario_type == ScenarioType.SYN_FLOOD
    assert config.scenario_version == "1.0.0"
    assert config.seed == 42
    assert config.duration_seconds == 60
    assert config.total_ticks == 60
    assert config.baseline_pps == 200.0
    assert config.attack_peak_pps == 10000.0


def test_scenario_config_rejects_invalid_inputs() -> None:
    """Validate that out-of-range, malformed, or inverted inputs are rejected."""
    # 1. Invalid IP
    with pytest.raises(ValidationError, match="not a valid IPv4 or IPv6"):
        ScenarioConfig(target_ip="999.999.999.999")

    # 2. Inverted attack ticks (start > end)
    with pytest.raises(ValidationError, match="cannot be greater than attack_end_tick"):
        ScenarioConfig(attack_start_tick=40, attack_end_tick=20)

    # 3. Attack end tick exceeds duration
    with pytest.raises(ValidationError, match="exceeds total run ticks"):
        ScenarioConfig(duration_seconds=30, attack_end_tick=50)

    # 4. Out of range duration (max 300)
    with pytest.raises(ValidationError):
        ScenarioConfig(duration_seconds=500)

    # 5. Out of range seed
    with pytest.raises(ValidationError):
        ScenarioConfig(seed=-1)


# ==============================================================================
# 7.2: Deterministic PRNG Generation & Repeatability
# ==============================================================================


@pytest.mark.parametrize(
    "scen_type",
    [
        ScenarioType.SYN_FLOOD,
        ScenarioType.UDP_FLOOD,
        ScenarioType.HTTP_FLOOD,
        ScenarioType.LOW_AND_SLOW,
        ScenarioType.MIXED,
        ScenarioType.FLASH_CROWD,
    ],
)
def test_all_scenario_types_deterministic_reproducibility(
    scen_type: ScenarioType,
) -> None:
    """Golden Test: Two separate engines with the same seed produce byte-identical values."""
    config1 = ScenarioConfig(
        scenario_type=scen_type,
        seed=12345,
        duration_seconds=20,
        attack_start_tick=5,
        attack_end_tick=15,
    )
    config2 = ScenarioConfig(
        scenario_type=scen_type,
        seed=12345,
        duration_seconds=20,
        attack_start_tick=5,
        attack_end_tick=15,
    )

    engine1 = ScenarioEngine(config1)
    engine2 = ScenarioEngine(config2)

    ticks1 = engine1.generate_all()
    ticks2 = engine2.generate_all()

    assert len(ticks1) == len(ticks2) == 21  # 0 to 20 inclusive
    for (feat1, gt1), (feat2, gt2) in zip(ticks1, ticks2, strict=True):
        assert feat1 == feat2
        assert gt1 == gt2


def test_different_seeds_produce_different_traffic() -> None:
    """Varying the seed produces expected statistical variation."""
    config1 = ScenarioConfig(seed=100)
    config2 = ScenarioConfig(seed=200)

    engine1 = ScenarioEngine(config1)
    engine2 = ScenarioEngine(config2)

    feat1, _ = engine1.generate_tick(15)
    feat2, _ = engine2.generate_tick(15)

    assert feat1 != feat2


def test_tick_bounds_check() -> None:
    """Requesting negative tick or tick beyond total_ticks raises ValueError."""
    config = ScenarioConfig(
        duration_seconds=30, attack_start_tick=5, attack_end_tick=25
    )
    engine = ScenarioEngine(config)

    with pytest.raises(ValueError, match="out of bounds"):
        engine.generate_tick(-1)

    with pytest.raises(ValueError, match="out of bounds"):
        engine.generate_tick(31)


# ==============================================================================
# 7.3: Schema 1.0.0 Contract, Zero Label Leakage, & Inference Compatibility
# ==============================================================================


def test_schema_contract_and_zero_label_leakage() -> None:
    """Ensure generated features match Schema 1.0.0 and contain ZERO ground truth labels."""
    config = ScenarioConfig(scenario_type=ScenarioType.SYN_FLOOD, seed=999)
    engine = ScenarioEngine(config)

    features, ground_truth = engine.generate_tick(15)

    # 1. Exact 14 Schema features
    assert len(features) == len(FEATURE_NAMES) == 14
    for name in FEATURE_NAMES:
        assert name in features
        assert isinstance(features[name], float | int)

    # 2. Invariant: Ground truth is never leaked into features
    assert "label" not in features
    assert "is_attack" not in features
    assert "attack_type" not in features
    assert "ground_truth" not in features

    # 3. Ground truth object is typed and separated
    assert isinstance(ground_truth, GroundTruth)
    assert ground_truth.is_attack is True
    assert ground_truth.label == "SynFlood"


def test_flash_crowd_legitimate_ground_truth() -> None:
    """Flash crowd must exhibit high traffic volume while ground truth is strictly BENIGN."""
    config = ScenarioConfig(
        scenario_type=ScenarioType.FLASH_CROWD,
        baseline_pps=200.0,
        attack_peak_pps=8000.0,
        attack_start_tick=5,
        attack_end_tick=15,
        duration_seconds=20,
    )
    engine = ScenarioEngine(config)

    features, ground_truth = engine.generate_tick(10)

    assert features["Fwd Packets/s"] > 4000.0
    assert ground_truth.is_attack is False
    assert ground_truth.label == "BENIGN"
    assert ground_truth.attack_type is None
    assert ground_truth.attack_pps == 0.0


def test_model_inference_compatibility() -> None:
    """Ensure generated synthetic features can be cleanly preprocessed and inferred by runtime model."""
    config = ScenarioConfig(scenario_type=ScenarioType.SYN_FLOOD, seed=42)
    engine = ScenarioEngine(config)

    features, _ = engine.generate_tick(15)

    # 1. Preprocess feature vector
    vector = prepare_feature_vector(features)
    assert vector.shape == (1, 14)

    # 2. Run approved model inference
    flow_pred = run_flow_inference(features)

    assert flow_pred.prediction in ("normal", "suspicious")
    assert isinstance(flow_pred.score, float)
