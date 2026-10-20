"""Add banner_presets catalog for default collection banners

Revision ID: 017_banner_presets
Revises: 016_collection_visit_count
Create Date: 2026-10-21 01:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "017_banner_presets"
down_revision: Union[str, None] = "016_collection_visit_count"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "banner_presets",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("owner_scope", sa.String(length=50), nullable=False),
        sa.Column("funeral_home_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["funeral_home_id"],
            ["funeral_homes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_banner_presets_owner_scope", "banner_presets", ["owner_scope"])
    op.create_index("ix_banner_presets_funeral_home_id", "banner_presets", ["funeral_home_id"])
    op.create_index("ix_banner_presets_created_by", "banner_presets", ["created_by"])
    op.create_index("ix_banner_presets_is_active", "banner_presets", ["is_active"])
    op.create_index("idx_banner_presets_name", "banner_presets", ["name"])
    op.create_index("idx_banner_presets_sort_order", "banner_presets", ["sort_order"])


def downgrade() -> None:
    op.drop_index("idx_banner_presets_sort_order", table_name="banner_presets")
    op.drop_index("idx_banner_presets_name", table_name="banner_presets")
    op.drop_index("ix_banner_presets_is_active", table_name="banner_presets")
    op.drop_index("ix_banner_presets_created_by", table_name="banner_presets")
    op.drop_index("ix_banner_presets_funeral_home_id", table_name="banner_presets")
    op.drop_index("ix_banner_presets_owner_scope", table_name="banner_presets")
    op.drop_table("banner_presets")
