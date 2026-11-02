"""Link Foveo identities on users and funeral homes

Revision ID: 020_foveo_link
Revises: 019_funeral_home_commission
Create Date: 2026-11-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "020_foveo_link"
down_revision: Union[str, None] = "019_funeral_home_commission"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("foveo_user_id", sa.Integer(), nullable=True))
    op.create_index("ix_users_foveo_user_id", "users", ["foveo_user_id"], unique=True)

    op.add_column(
        "funeral_homes",
        sa.Column("foveo_funeral_home_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_funeral_homes_foveo_funeral_home_id",
        "funeral_homes",
        ["foveo_funeral_home_id"],
        unique=True,
    )

    op.create_table(
        "foveo_sync_events",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("foveo_stream_id", sa.Integer(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("foveo_sync_events")
    op.drop_index("ix_funeral_homes_foveo_funeral_home_id", table_name="funeral_homes")
    op.drop_column("funeral_homes", "foveo_funeral_home_id")
    op.drop_index("ix_users_foveo_user_id", table_name="users")
    op.drop_column("users", "foveo_user_id")
