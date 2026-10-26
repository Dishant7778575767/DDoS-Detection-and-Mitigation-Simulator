"""Model metadata and evaluation metrics endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_api_auth
from app.features.definitions import FEATURE_SCHEMA_VERSION

router = APIRouter(tags=["models"], dependencies=[Depends(require_api_auth)])


class ModelSummary(BaseModel):
    model_version: str
    model_type: str
    status: str
    schema_version: str


class ModelsListResponse(BaseModel):
    approved_model: str
    schema_version: str
    models: list[ModelSummary]


@router.get("/models", response_model=ModelsListResponse)
def get_models() -> ModelsListResponse:
    """Return available candidate models and identify the approved active model."""
    return ModelsListResponse(
        approved_model="rf-1.0.0",
        schema_version=FEATURE_SCHEMA_VERSION,
        models=[
            ModelSummary(
                model_version="rf-1.0.0",
                model_type="RandomForestClassifier",
                status="approved",
                schema_version=FEATURE_SCHEMA_VERSION,
            ),
            ModelSummary(
                model_version="iforest-1.0.0",
                model_type="IsolationForest",
                status="experimental_unapproved",
                schema_version=FEATURE_SCHEMA_VERSION,
            ),
        ],
    )


@router.get("/models/metrics")
def get_model_metrics() -> dict[str, Any]:
    """Return evaluation metrics for candidate models."""
    rf_metrics_path = Path("models/rf-1.0.0/metrics.json")
    if_metrics_path = Path("models/iforest-1.0.0/metrics.json")

    rf_data = (
        json.loads(rf_metrics_path.read_text(encoding="utf-8"))
        if rf_metrics_path.exists()
        else {}
    )
    if_data = (
        json.loads(if_metrics_path.read_text(encoding="utf-8"))
        if if_metrics_path.exists()
        else {}
    )

    return {
        "dataset": "CIC-DDoS2019",
        "schema_version": FEATURE_SCHEMA_VERSION,
        "rf_metrics": rf_data,
        "iforest_metrics": if_data,
    }
