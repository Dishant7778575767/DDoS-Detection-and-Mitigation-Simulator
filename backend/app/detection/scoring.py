"""Score interpretation and threat assessment."""

from __future__ import annotations

from app.detection.predictor import FlowPrediction


def evaluate_ml_threat(
    prediction: FlowPrediction,
    rf_threshold: float = 0.75,
    iforest_threshold: float = 0.2664,
) -> bool:
    """Evaluate whether the ML score indicates an actionable threat.

    - Random Forest: Threat indicated when probability >= rf_threshold.
    - Isolation Forest: Threat indicated when anomaly score < iforest_threshold.
    """
    if prediction.score_type == "random_forest_probability":
        return prediction.score >= rf_threshold
    elif prediction.score_type == "isolation_forest_anomaly_score":
        return prediction.score < iforest_threshold
    else:
        return prediction.prediction == "suspicious"
