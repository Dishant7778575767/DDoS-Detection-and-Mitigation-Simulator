"""Inference engine for flow detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.detection.model_loader import load_runtime_model
from app.features.definitions import FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from app.features.preprocess import prepare_feature_vector


@dataclass
class FlowPrediction:
    """Detection result for a single network observation."""

    prediction: str  # "normal" or "suspicious"
    score: float
    score_type: str
    model_version: str
    feature_schema_version: str


def run_flow_inference(
    features_dict: dict[str, Any],
    model: Any | None = None,
) -> FlowPrediction:
    """Execute prediction on a dictionary of flow features."""
    if model is None:
        model = load_runtime_model()

    # Preprocess features into (1, 14) dataframe matching fitted schema
    vector = prepare_feature_vector(features_dict)
    features_df = pd.DataFrame(vector, columns=FEATURE_NAMES)

    # Determine model type and score convention
    if hasattr(model, "predict_proba"):
        # Supervised Random Forest Classifier
        proba = float(model.predict_proba(features_df)[0, 1])
        prediction = "suspicious" if proba >= 0.50 else "normal"
        score = proba
        score_type = "random_forest_probability"
        model_version = "rf-1.0.0"
    elif hasattr(model, "decision_function"):
        # Unsupervised Isolation Forest Anomaly Detector
        score = float(model.decision_function(features_df)[0])
        # By convention from Phase 2 calibration, score < threshold indicates anomaly
        prediction = "suspicious" if score < 0.2664 else "normal"
        score_type = "isolation_forest_anomaly_score"
        model_version = "iforest-1.0.0"
    else:
        pred_val = int(model.predict(features_df)[0])
        prediction = "suspicious" if pred_val == 1 else "normal"
        score = float(pred_val)
        score_type = "binary_prediction"
        model_version = "generic-1.0.0"

    return FlowPrediction(
        prediction=prediction,
        score=score,
        score_type=score_type,
        model_version=model_version,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
    )
