"""SQLAlchemy database models for SENTRIX persistence.

Defines tables for observations, detections, alerts, mitigation lifecycle,
threshold configurations, and structured audit logs.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


class ObservationModel(Base):
    """Network flow observations ingested from collectors or generators."""

    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[str] = mapped_column(String(32), index=True)
    window_seconds: Mapped[float] = mapped_column(Float, default=10.0)
    feature_schema_version: Mapped[str] = mapped_column(String(16), default="1.0.0")
    features_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(32))

    detections: Mapped[list[DetectionModel]] = relationship(
        "DetectionModel", back_populates="observation", cascade="all, delete-orphan"
    )


class DetectionModel(Base):
    """Analysis results produced by the ML and detection pipeline."""

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    observation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("observations.id"), nullable=True, index=True
    )
    model_version: Mapped[str] = mapped_column(String(32), default="rf-1.0.0")
    feature_schema_version: Mapped[str] = mapped_column(String(16), default="1.0.0")
    prediction: Mapped[str] = mapped_column(String(32))  # "normal" or "suspicious"
    score_type: Mapped[str] = mapped_column(String(64))
    score: Mapped[float] = mapped_column(Float)
    traffic_threshold_exceeded: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_decision: Mapped[str] = mapped_column(
        String(64)
    )  # "monitor", "alert", "simulate_rate_limit"
    mitigation_mode: Mapped[str] = mapped_column(String(32), default="simulation")
    timestamp: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[str] = mapped_column(String(32))

    observation: Mapped[ObservationModel | None] = relationship(
        "ObservationModel", back_populates="detections"
    )
    alerts: Mapped[list[AlertModel]] = relationship(
        "AlertModel", back_populates="detection", cascade="all, delete-orphan"
    )
    mitigations: Mapped[list[MitigationModel]] = relationship(
        "MitigationModel", back_populates="detection", cascade="all, delete-orphan"
    )


class AlertModel(Base):
    """Alerts emitted when detection or threshold signals detect threats."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    detection_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("detections.id"), nullable=True, index=True
    )
    severity: Mapped[str] = mapped_column(
        String(16), index=True
    )  # "info", "warning", "critical"
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(
        String(32), default="active", index=True
    )  # "active", "resolved"

    detection: Mapped[DetectionModel | None] = relationship(
        "DetectionModel", back_populates="alerts"
    )


class MitigationModel(Base):
    """Mitigation actions tracking the state machine lifecycle."""

    __tablename__ = "mitigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    detection_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("detections.id"), nullable=True, index=True
    )
    target_ip: Mapped[str] = mapped_column(String(64), index=True)
    target_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action_type: Mapped[str] = mapped_column(String(32), default="rate_limit")
    rate_limit_pps: Mapped[int] = mapped_column(Integer, default=1000)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(
        String(32), default="proposed", index=True
    )  # "proposed", "simulated", "applied", "failed", "cancelled", "expired", "recovered"
    mode: Mapped[str] = mapped_column(String(32), default="simulation")
    created_at: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cancelled_at: Mapped[str | None] = mapped_column(String(32), nullable=True)

    detection: Mapped[DetectionModel | None] = relationship(
        "DetectionModel", back_populates="mitigations"
    )


class ThresholdConfigModel(Base):
    """Versioned threshold configuration for rate limits and ML scoring."""

    __tablename__ = "threshold_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(32), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    pps_threshold: Mapped[float] = mapped_column(Float, default=5000.0)
    bps_threshold: Mapped[float] = mapped_column(Float, default=10_000_000.0)
    syn_pps_threshold: Mapped[float] = mapped_column(Float, default=500.0)
    syn_ack_ratio_threshold: Mapped[float] = mapped_column(Float, default=5.0)
    rf_probability_threshold: Mapped[float] = mapped_column(Float, default=0.75)
    iforest_score_threshold: Mapped[float] = mapped_column(Float, default=0.2664)
    updated_by: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[str] = mapped_column(String(32))


class AuditEventModel(Base):
    """Immutable audit records capturing system operations and lifecycle transitions."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(64))
    details_json: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[str] = mapped_column(String(32), index=True)
