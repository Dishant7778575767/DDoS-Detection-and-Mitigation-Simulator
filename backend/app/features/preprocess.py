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


def derive_missing_features_if_possible(cleaned: dict[str, Any]) -> dict[str, Any]:
    """Derive standard Schema 1.0.0 features if raw flow attributes are present."""
    augmented = dict(cleaned)

    # 1. Total Length of Fwd Packets
    if "Total Length of Fwd Packets" not in augmented:
        if "Total Fwd Packets" in augmented and "Fwd Packet Length Mean" in augmented:
            augmented["Total Length of Fwd Packets"] = float(
                augmented["Total Fwd Packets"]
            ) * float(augmented["Fwd Packet Length Mean"])
        elif "Flow Bytes/s" in augmented and "Flow Duration" in augmented:
            duration_s = max(0.001, float(augmented["Flow Duration"]) / 1_000_000.0)
            augmented["Total Length of Fwd Packets"] = (
                float(augmented["Flow Bytes/s"]) * duration_s * 0.6
            )

    # 2. Flow Bytes/s
    if (
        "Flow Bytes/s" not in augmented
        and "Flow Duration" in augmented
        and "Total Length of Fwd Packets" in augmented
    ):
        duration_s = max(0.001, float(augmented["Flow Duration"]) / 1_000_000.0)
        augmented["Flow Bytes/s"] = (
            float(augmented["Total Length of Fwd Packets"]) / duration_s
        )

    # 3. Fwd Packets/s
    if "Fwd Packets/s" not in augmented:
        if "Flow Packets/s" in augmented:
            augmented["Fwd Packets/s"] = float(augmented["Flow Packets/s"]) * 0.9
        elif "Total Fwd Packets" in augmented and "Flow Duration" in augmented:
            duration_s = max(0.001, float(augmented["Flow Duration"]) / 1_000_000.0)
            augmented["Fwd Packets/s"] = (
                float(augmented["Total Fwd Packets"]) / duration_s
            )

    # 4. Subflow Fwd Packets
    if "Subflow Fwd Packets" not in augmented and "Total Fwd Packets" in augmented:
        augmented["Subflow Fwd Packets"] = float(augmented["Total Fwd Packets"])

    # 5. Fwd IAT Total
    if "Fwd IAT Total" not in augmented and "Flow Duration" in augmented:
        augmented["Fwd IAT Total"] = float(augmented["Flow Duration"])

    # 6. Bwd IAT Total
    if (
        "Bwd IAT Total" not in augmented
        and "Total Backward Packets" in augmented
        and float(augmented["Total Backward Packets"]) == 0
    ):
        augmented["Bwd IAT Total"] = 0.0

    return augmented


def prepare_feature_vector(record: dict[str, Any]) -> np.ndarray:
    """Convert a single flow observation dictionary into a strict, ordered 1D NumPy array."""
    cleaned_record = {normalize_feature_name(k): v for k, v in record.items()}
    cleaned_record = derive_missing_features_if_possible(cleaned_record)

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
