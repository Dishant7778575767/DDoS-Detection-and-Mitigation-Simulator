"""SENTRIX Reusable Feature Preprocessing.

Ensures strict parity between training-time and runtime inference preprocessing:
- Strips whitespace from column / key names
- Enforces feature schema ordering
- Sanitizes non-finite values (inf / -inf / NaN)
- Excludes target labels and identifier leakage
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from app.features.definitions import FEATURE_NAMES, FEATURE_SCHEMA_VERSION

# Excluded identifiers, timestamps, and target labels
PROHIBITED_COLUMNS = {
    "flow_id",
    "source_ip",
    "destination_ip",
    "source_port",
    "destination_port",
    "protocol",
    "timestamp",
    "label",
    "target",
    "simillarhttp",
    "inbound",
    "unnamed",
}


def normalize_feature_name(name: str) -> str:
    """Normalize a feature name for lookup."""
    return str(name).strip()


def validate_feature_schema(columns: Sequence[str]) -> None:
    """Validate that the provided column set satisfies the versioned feature schema."""
    normalized_provided = {normalize_feature_name(c): c for c in columns}
    missing = [f for f in FEATURE_NAMES if f not in normalized_provided]
    if missing:
        raise ValueError(
            f"Schema mismatch: missing {len(missing)} required features for schema {FEATURE_SCHEMA_VERSION}: {missing}"
        )


def sanitize_numeric_value(val: Any, default: float = 0.0) -> float:
    """Sanitize individual numeric values, converting inf/nan to default."""
    try:
        f = float(val)
        if np.isneginf(f) or np.isposinf(f) or np.isnan(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def prepare_feature_vector(record: dict[str, Any]) -> np.ndarray:
    """Convert a single flow observation dictionary into a strict, ordered 1D NumPy array."""
    # Strip whitespace from keys
    cleaned_record = {normalize_feature_name(k): v for k, v in record.items()}

    vector: list[float] = []
    missing_keys: list[str] = []

    for name in FEATURE_NAMES:
        if name in cleaned_record:
            raw_val = cleaned_record[name]
            val = sanitize_numeric_value(raw_val)
            vector.append(val)
        else:
            missing_keys.append(name)

    if missing_keys:
        raise ValueError(
            f"Cannot extract feature vector. Missing required features for schema {FEATURE_SCHEMA_VERSION}: {missing_keys}"
        )

    return np.array(vector, dtype=np.float64).reshape(1, -1)


def prepare_feature_matrix(df: pd.DataFrame) -> np.ndarray:
    """Extract and validate the ordered feature matrix (N, 14) from a DataFrame."""
    # Normalize column names by stripping whitespace
    df_clean = df.copy()
    df_clean.columns = [normalize_feature_name(c) for c in df_clean.columns]

    validate_feature_schema(df_clean.columns)

    # Select only the required features in the exact specified order
    feature_df = df_clean[FEATURE_NAMES].copy()

    # Convert to numeric, replace inf with NaN, fillna with 0.0
    for col in FEATURE_NAMES:
        feature_df[col] = pd.to_numeric(feature_df[col], errors="coerce")

    feature_df = feature_df.replace([np.inf, -np.inf], np.nan)
    feature_df = feature_df.fillna(0.0)

    return feature_df.to_numpy(dtype=np.float64)
