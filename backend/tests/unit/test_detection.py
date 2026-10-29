"""Unit tests for detection model loading and flow inference."""

from pathlib import Path

import pytest

from app.detection.model_loader import ModelNotFoundError, load_runtime_model
from app.detection.predictor import FlowPrediction, run_flow_inference
from app.detection.scoring import evaluate_ml_threat
from app.features.definitions import FEATURE_NAMES, FEATURE_SCHEMA_VERSION


def test_model_loader_finds_approved_artifact() -> None:
    """Ensure the approved model artifact from Phase 2 loads and matches schema."""
    load_runtime_model.cache_clear()
    model = load_runtime_model()
    assert model is not None
    assert hasattr(model, "predict")
    if hasattr(model, "n_features_in_"):
        assert model.n_features_in_ == len(FEATURE_NAMES)


def test_model_loader_cwd_independence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ensure load_runtime_model succeeds regardless of process working directory."""
    monkeypatch.chdir(tmp_path)
    load_runtime_model.cache_clear()
    model = load_runtime_model()
    assert model is not None
    assert hasattr(model, "predict")


def test_model_loader_missing_raises_error() -> None:
    """Ensure a non-existent path raises ModelNotFoundError."""
    load_runtime_model.cache_clear()
    with pytest.raises(ModelNotFoundError):
        load_runtime_model("models/non_existent_model.joblib")


def test_run_flow_inference_valid() -> None:
    """Ensure flow inference returns valid FlowPrediction with proper score convention."""
    flow = {name: 10.0 for name in FEATURE_NAMES}
    result = run_flow_inference(flow)

    assert isinstance(result, FlowPrediction)
    assert result.prediction in ("normal", "suspicious")
    assert result.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert result.model_version == "rf-1.0.0"
    assert result.score_type == "random_forest_probability"
    assert 0.0 <= result.score <= 1.0


def test_evaluate_ml_threat_scoring() -> None:
    """Ensure score evaluation correctly flags threat based on configured threshold."""
    low_threat = FlowPrediction(
        prediction="normal",
        score=0.20,
        score_type="random_forest_probability",
        model_version="rf-1.0.0",
        feature_schema_version="1.0.0",
    )
    assert evaluate_ml_threat(low_threat, rf_threshold=0.75) is False

    high_threat = FlowPrediction(
        prediction="suspicious",
        score=0.92,
        score_type="random_forest_probability",
        model_version="rf-1.0.0",
        feature_schema_version="1.0.0",
    )
    assert evaluate_ml_threat(high_threat, rf_threshold=0.75) is True
