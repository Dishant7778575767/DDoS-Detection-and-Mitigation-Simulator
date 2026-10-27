"""Persist target IP addresses on observations."""

import sqlalchemy as sa
from alembic import op

revision = "0002_observation_target_ip"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "observations",
        sa.Column("target_ip", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("observations", "target_ip")
