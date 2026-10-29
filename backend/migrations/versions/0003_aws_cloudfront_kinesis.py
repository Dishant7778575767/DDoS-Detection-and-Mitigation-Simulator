"""Add AWS CloudFront and Kinesis ingestion and checkpoint tables.

Revision ID: 0003_aws_cloudfront_kinesis
Revises: 0002_observation_target_ip
Create Date: 2026-10-29 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_aws_cloudfront_kinesis"
down_revision: str | None = "0002_observation_target_ip"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cloudfront_kinesis_events",
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("timestamp", sa.String(length=40), nullable=False),
        sa.Column("received_at", sa.String(length=40), nullable=False),
        sa.Column("stream_name", sa.String(length=128), nullable=False),
        sa.Column("shard_id", sa.String(length=128), nullable=False),
        sa.Column("sequence_number", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("request_id"),
    )
    op.create_index(
        "ix_cloudfront_kinesis_events_timestamp",
        "cloudfront_kinesis_events",
        ["timestamp"],
        unique=False,
    )
    op.create_index(
        "ix_cloudfront_kinesis_events_received_at",
        "cloudfront_kinesis_events",
        ["received_at"],
        unique=False,
    )
    op.create_index(
        "ix_cloudfront_kinesis_events_stream_name",
        "cloudfront_kinesis_events",
        ["stream_name"],
        unique=False,
    )
    op.create_index(
        "ix_cloudfront_kinesis_events_shard_id",
        "cloudfront_kinesis_events",
        ["shard_id"],
        unique=False,
    )
    op.create_index(
        "ix_cloudfront_kinesis_events_sequence_number",
        "cloudfront_kinesis_events",
        ["sequence_number"],
        unique=False,
    )

    op.create_table(
        "kinesis_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stream_name", sa.String(length=128), nullable=False),
        sa.Column("shard_id", sa.String(length=128), nullable=False),
        sa.Column("last_sequence_number", sa.String(length=128), nullable=False),
        sa.Column(
            "records_processed",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("updated_at", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_kinesis_checkpoints_stream_name",
        "kinesis_checkpoints",
        ["stream_name"],
        unique=False,
    )
    op.create_index(
        "ix_kinesis_checkpoints_shard_id",
        "kinesis_checkpoints",
        ["shard_id"],
        unique=False,
    )
    op.create_index(
        "ix_kinesis_checkpoints_updated_at",
        "kinesis_checkpoints",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_kinesis_checkpoints_updated_at", table_name="kinesis_checkpoints")
    op.drop_index("ix_kinesis_checkpoints_shard_id", table_name="kinesis_checkpoints")
    op.drop_index(
        "ix_kinesis_checkpoints_stream_name", table_name="kinesis_checkpoints"
    )
    op.drop_table("kinesis_checkpoints")

    op.drop_index(
        "ix_cloudfront_kinesis_events_sequence_number",
        table_name="cloudfront_kinesis_events",
    )
    op.drop_index(
        "ix_cloudfront_kinesis_events_shard_id",
        table_name="cloudfront_kinesis_events",
    )
    op.drop_index(
        "ix_cloudfront_kinesis_events_stream_name",
        table_name="cloudfront_kinesis_events",
    )
    op.drop_index(
        "ix_cloudfront_kinesis_events_received_at",
        table_name="cloudfront_kinesis_events",
    )
    op.drop_index(
        "ix_cloudfront_kinesis_events_timestamp",
        table_name="cloudfront_kinesis_events",
    )
    op.drop_table("cloudfront_kinesis_events")
