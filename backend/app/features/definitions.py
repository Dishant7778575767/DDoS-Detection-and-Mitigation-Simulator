"""SENTRIX Feature Definitions and Schema Versioning.

Defines the single source of truth for runtime and training feature schemas.
Enforces feature names, ordering, units, and validation.
"""

from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel, Field


FEATURE_SCHEMA_VERSION: str = "1.0.0"

# Strict ordered list of features expected by models in schema 1.0.0
FEATURE_NAMES: List[str] = [
    "Total Length of Fwd Packets",
    "Bwd Packet Length Max",
    "Flow Bytes/s",
    "Fwd IAT Total",
    "Bwd IAT Total",
    "Fwd PSH Flags",
    "Fwd Packets/s",
    "FIN Flag Count",
    "Fwd Avg Bytes/Bulk",
    "Bwd Avg Bulk Rate",
    "Subflow Fwd Packets",
    "Init_Win_bytes_forward",
    "Active Mean",
    "Idle Mean",
]

FEATURE_UNITS: Dict[str, str] = {
    "Total Length of Fwd Packets": "bytes",
    "Bwd Packet Length Max": "bytes",
    "Flow Bytes/s": "bytes/second",
    "Fwd IAT Total": "microseconds",
    "Bwd IAT Total": "microseconds",
    "Fwd PSH Flags": "count",
    "Fwd Packets/s": "packets/second",
    "FIN Flag Count": "count",
    "Fwd Avg Bytes/Bulk": "bytes",
    "Bwd Avg Bulk Rate": "bytes/second",
    "Subflow Fwd Packets": "count",
    "Init_Win_bytes_forward": "bytes",
    "Active Mean": "microseconds",
    "Idle Mean": "microseconds",
}

FEATURE_DESCRIPTIONS: Dict[str, str] = {
    "Total Length of Fwd Packets": "Cumulative payload length of all forward packets in the flow",
    "Bwd Packet Length Max": "Maximum backward packet length observed in the flow",
    "Flow Bytes/s": "Total flow volume in bytes divided by flow duration",
    "Fwd IAT Total": "Total elapsed time between successive forward packets",
    "Bwd IAT Total": "Total elapsed time between successive backward packets",
    "Fwd PSH Flags": "Number of times the PSH flag was set in forward packets",
    "Fwd Packets/s": "Number of forward packets per second",
    "FIN Flag Count": "Number of packets with the FIN flag set",
    "Fwd Avg Bytes/Bulk": "Average bytes transferred per forward bulk transmission",
    "Bwd Avg Bulk Rate": "Rate of bytes transmitted per backward bulk transmission",
    "Subflow Fwd Packets": "Average number of packets per forward subflow",
    "Init_Win_bytes_forward": "Initial TCP window size advertised in forward direction",
    "Active Mean": "Mean duration the flow was active before going idle",
    "Idle Mean": "Mean duration the flow was idle between active periods",
}


class FeatureSchemaMetadata(BaseModel):
    """Metadata describing the feature schema version and contract."""
    schema_version: str = Field(default=FEATURE_SCHEMA_VERSION, description="Feature schema version string")
    feature_count: int = Field(default=len(FEATURE_NAMES), description="Total count of required features")
    features: List[str] = Field(default_factory=lambda: list(FEATURE_NAMES), description="Ordered feature names")
    units: Dict[str, str] = Field(default_factory=lambda: dict(FEATURE_UNITS), description="Units per feature")
    descriptions: Dict[str, str] = Field(default_factory=lambda: dict(FEATURE_DESCRIPTIONS), description="Descriptions")


def get_feature_schema() -> Dict[str, Any]:
    """Return dictionary representation of the current feature schema."""
    return FeatureSchemaMetadata().model_dump()
