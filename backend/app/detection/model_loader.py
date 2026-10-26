"""Model loader for approved runtime detection artifacts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

from app.core.config import get_settings
from app.features.definitions import FEATURE_NAMES, FEATURE_SCHEMA_VERSION


class IncompatibleModelError(ValueError):
    """Raised when a candidate model does not match the approved feature schema."""


class ModelNotFoundError(FileNotFoundError):
    """Raised when the approved runtime model artifact is missing."""


def _resolve_model_path(path: Path) -> Path:
    """Resolve a model path considering both repo root and backend/ working directory."""
    if path.exists():
        return path
    parent_path = Path("..") / path
    if parent_path.exists():
        return parent_path
    return path


@lru_cache(maxsize=2)
def load_runtime_model(model_path_str: str | None = None) -> Any:
    """Load and validate the approved ML model artifact."""
    if model_path_str is not None:
        model_path = _resolve_model_path(Path(model_path_str))
        if not model_path.exists():
            raise ModelNotFoundError(
                f"Approved runtime model not found at '{model_path}'. Ensure Phase 2 export is complete."
            )
    else:
        configured_path = get_settings().model_path
        model_path = _resolve_model_path(configured_path)
        if not model_path.exists():
            # Fall back to versioned approved candidate if exported link/copy is missing
            candidate = _resolve_model_path(Path("models/rf-1.0.0/model.joblib"))
            if candidate.exists():
                model_path = candidate
            else:
                raise ModelNotFoundError(
                    f"Approved runtime model not found at '{configured_path}'. Ensure Phase 2 export is complete."
                )

    try:
        model = joblib.load(model_path)
    except Exception as exc:
        raise ValueError(
            f"Failed to deserialize model artifact at '{model_path}': {exc}"
        ) from exc

    # Validate feature schema compatibility
    if hasattr(model, "n_features_in_"):
        expected_count = len(FEATURE_NAMES)
        if model.n_features_in_ != expected_count:
            raise IncompatibleModelError(
                f"Model expects {model.n_features_in_} features, but schema {FEATURE_SCHEMA_VERSION} defines {expected_count}."
            )

    return model
