"""Input validation logic for traffic ingestion."""

from __future__ import annotations

import datetime
import math
from typing import Any

from app.features.definitions import FEATURE_NAMES, FEATURE_SCHEMA_VERSION


def validate_iso8601_timestamp(value: str) -> str:
    """Validate that the string is a valid ISO 8601 UTC timestamp."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Timestamp must not be empty.")
    try:
        dt = datetime.datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"Invalid ISO 8601 timestamp '{value}'. Expected UTC format (e.g., 2026-10-25T10:00:00Z)."
        ) from exc

    if dt.tzinfo is None:
        raise ValueError(
            f"Timestamp '{value}' must include explicit UTC timezone offset (Z or +00:00)."
        )
    return cleaned


def validate_flow_features(features: dict[str, Any], schema_version: str) -> None:
    """Validate that features match the expected schema version and contain valid finite numbers."""
    if schema_version != FEATURE_SCHEMA_VERSION:
        raise ValueError(
            f"Feature schema version '{schema_version}' is unsupported. Current active version is '{FEATURE_SCHEMA_VERSION}'."
        )

    from app.features.preprocess import derive_missing_features_if_possible

    features_derived = derive_missing_features_if_possible(features)
    for k, v in features_derived.items():
        if k not in features:
            features[k] = v

    # Check for missing features
    missing = [name for name in FEATURE_NAMES if name not in features]
    if missing:
        raise ValueError(
            f"Missing required features for schema {FEATURE_SCHEMA_VERSION}: {missing}"
        )

    # Check for extraneous / unexpected features
    unexpected = [name for name in features if name not in FEATURE_NAMES]
    if unexpected:
        raise ValueError(
            f"Extraneous unexpected features for schema {FEATURE_SCHEMA_VERSION}: {unexpected[:5]}"
        )

    # Check that values are finite numbers
    for name, val in features.items():
        if not isinstance(val, (int, float)):
            raise TypeError(
                f"Feature '{name}' must be a numeric value, got {type(val).__name__}."
            )
        if math.isinf(val) or math.isnan(val):
            raise ValueError(
                f"Feature '{name}' contains non-finite value (inf or nan)."
            )
