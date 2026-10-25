"""Unit tests for SENTRIX features: definitions, preprocessing, and window aggregation."""

import numpy as np
import pandas as pd
import pytest

from app.features.definitions import (
    FEATURE_DESCRIPTIONS,
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    FEATURE_UNITS,
    get_feature_schema,
)
from app.features.preprocess import (
    prepare_feature_matrix,
    prepare_feature_vector,
    validate_feature_schema,
)
from app.features.windows import SlidingWindowAggregator


def test_feature_schema_contract() -> None:
    """Ensure the versioned schema is v1.0.0 and defines exactly 14 features."""
    assert FEATURE_SCHEMA_VERSION == "1.0.0"
    assert len(FEATURE_NAMES) == 14
    assert len(set(FEATURE_NAMES)) == 14  # No duplicate names

    # Every feature has a unit and description
    for name in FEATURE_NAMES:
        assert name in FEATURE_UNITS
        assert name in FEATURE_DESCRIPTIONS

    schema = get_feature_schema()
    assert schema["schema_version"] == "1.0.0"
    assert schema["feature_count"] == 14
    assert schema["features"] == FEATURE_NAMES

    # Validate schema validator
    validate_feature_schema(FEATURE_NAMES)
    with pytest.raises(ValueError, match="Schema mismatch"):
        validate_feature_schema(["wrong_feature"])


def test_prepare_feature_vector_valid() -> None:
    """Ensure a valid observation dictionary produces an ordered 1x14 numpy vector."""
    record = {name: float(i * 10) for i, name in enumerate(FEATURE_NAMES)}
    # Add dummy unneeded column and dirty whitespace
    record[" Extra_Ignored_Column "] = 999.0

    vec = prepare_feature_vector(record)
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (1, 14)
    assert vec[0, 0] == 0.0
    assert vec[0, 1] == 10.0


def test_prepare_feature_vector_handles_non_finite() -> None:
    """Ensure inf and nan values are safely sanitized to 0.0."""
    record = {name: 1.0 for name in FEATURE_NAMES}
    record["Flow Bytes/s"] = np.inf
    record["Fwd Packets/s"] = -np.inf
    record["Idle Mean"] = np.nan

    vec = prepare_feature_vector(record)
    assert vec.shape == (1, 14)
    assert not np.any(np.isinf(vec))
    assert not np.any(np.isnan(vec))


def test_prepare_feature_vector_missing_raises_error() -> None:
    """Ensure missing required features raise a descriptive ValueError."""
    incomplete_record = {"Flow Bytes/s": 100.0}
    with pytest.raises(ValueError, match="Missing required features"):
        prepare_feature_vector(incomplete_record)


def test_prepare_feature_matrix_dataframe() -> None:
    """Ensure DataFrame preprocessing preserves order and sanitizes non-finite values."""
    rows = []
    for _ in range(5):
        row = {f" {name} ": 5.0 for name in FEATURE_NAMES}
        rows.append(row)

    # Insert an infinity
    rows[0][" Flow Bytes/s "] = np.inf

    df = pd.DataFrame(rows)
    mat = prepare_feature_matrix(df)
    assert mat.shape == (5, 14)
    assert np.isfinite(mat).all()


def test_sliding_window_aggregator() -> None:
    """Test rolling window accumulation, rate computation, and expiration."""
    agg = SlidingWindowAggregator(window_duration_seconds=10.0)

    # Add observations at t=0, t=2, t=5
    agg.add_observation(
        timestamp=1000.0,
        packet_count=100,
        byte_count=10000,
        syn_flags=50,
        ack_flags=50,
        source_ip="192.168.1.10",
    )
    agg.add_observation(
        timestamp=1002.0,
        packet_count=200,
        byte_count=20000,
        syn_flags=100,
        ack_flags=50,
        source_ip="192.168.1.20",
    )

    summary = agg.get_summary(current_timestamp=1005.0)
    assert summary.observation_count == 2
    assert summary.unique_sources == 2
    assert summary.packet_rate == 30.0  # 300 packets / 10s
    assert summary.byte_rate == 3000.0  # 30,000 bytes / 10s
    assert summary.syn_rate == 15.0  # 150 syn / 10s
    assert summary.syn_ack_ratio == 1.5  # 150 syn / 100 ack

    # Advance time to t=1015 (old observations expire)
    summary_later = agg.get_summary(current_timestamp=1015.0)
    assert summary_later.observation_count == 0
    assert summary_later.packet_rate == 0.0

    # Reset
    agg.add_observation(timestamp=1020.0, packet_count=50, byte_count=5000)
    agg.reset()
    assert len(agg.buffer) == 0
