"""Track visits to public gift collection pages

Revision ID: 016_collection_visit_count
Revises: 015_default_collection_owner
Create Date: 2026-10-10 21:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "016_collection_visit_count"
down_revision: Union[str, None] = "015_default_collection_owner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_collections",
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("gift_collections", "visit_count")
