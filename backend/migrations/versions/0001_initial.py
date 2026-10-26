"""Initialize database schema for observations, detections, alerts, mitigations, thresholds, and audit.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Observations
    op.create_table(
        "observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(64), nullable=False, index=True),
        sa.Column("timestamp", sa.String(32), nullable=False, index=True),
        sa.Column("window_seconds", sa.Float(), nullable=False, server_default="10.0"),
        sa.Column(
            "feature_schema_version",
            sa.String(16),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column("features_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
    )

    # 2. Detections
    op.create_table(
        "detections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column(
            "observation_id",
            sa.Integer(),
            sa.ForeignKey("observations.id"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "model_version", sa.String(32), nullable=False, server_default="rf-1.0.0"
        ),
        sa.Column(
            "feature_schema_version",
            sa.String(16),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column("prediction", sa.String(32), nullable=False),
        sa.Column("score_type", sa.String(64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column(
            "traffic_threshold_exceeded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("policy_decision", sa.String(64), nullable=False),
        sa.Column(
            "mitigation_mode",
            sa.String(32),
            nullable=False,
            server_default="simulation",
        ),
        sa.Column("timestamp", sa.String(32), nullable=False, index=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )

    # 3. Alerts
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alert_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column(
            "detection_id",
            sa.Integer(),
            sa.ForeignKey("detections.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("severity", sa.String(16), nullable=False, index=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False, index=True),
        sa.Column("timestamp", sa.String(32), nullable=False, index=True),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="active", index=True
        ),
    )

    # 4. Mitigations
    op.create_table(
        "mitigations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("action_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column(
            "detection_id",
            sa.Integer(),
            sa.ForeignKey("detections.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("target_ip", sa.String(64), nullable=False, index=True),
        sa.Column("target_port", sa.Integer(), nullable=True),
        sa.Column(
            "action_type", sa.String(32), nullable=False, server_default="rate_limit"
        ),
        sa.Column(
            "rate_limit_pps", sa.Integer(), nullable=False, server_default="1000"
        ),
        sa.Column(
            "duration_seconds", sa.Integer(), nullable=False, server_default="60"
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="proposed",
            index=True,
        ),
        sa.Column("mode", sa.String(32), nullable=False, server_default="simulation"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("cancelled_at", sa.String(32), nullable=True),
    )

    # 5. Threshold Configs
    op.create_table(
        "threshold_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(32), nullable=False, unique=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("pps_threshold", sa.Float(), nullable=False, server_default="5000.0"),
        sa.Column(
            "bps_threshold", sa.Float(), nullable=False, server_default="10000000.0"
        ),
        sa.Column(
            "syn_pps_threshold", sa.Float(), nullable=False, server_default="500.0"
        ),
        sa.Column(
            "syn_ack_ratio_threshold", sa.Float(), nullable=False, server_default="5.0"
        ),
        sa.Column(
            "rf_probability_threshold",
            sa.Float(),
            nullable=False,
            server_default="0.75",
        ),
        sa.Column(
            "iforest_score_threshold",
            sa.Float(),
            nullable=False,
            server_default="0.2664",
        ),
        sa.Column("updated_by", sa.String(64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.String(32), nullable=False),
    )

    # 6. Audit Events
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("event_type", sa.String(64), nullable=False, index=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.String(32), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("threshold_configs")
    op.drop_table("mitigations")
    op.drop_table("alerts")
    op.drop_table("detections")
    op.drop_table("observations")
