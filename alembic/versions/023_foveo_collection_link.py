"""Link gift collections to Foveo streams

Revision ID: 023_foveo_collection_link
Revises: 022_order_product_base_price
Create Date: 2026-11-10 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "023_foveo_collection_link"
down_revision: Union[str, None] = "022_order_product_base_price"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gift_collections",
        sa.Column("foveo_stream_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_gift_collections_foveo_stream_id",
        "gift_collections",
        ["foveo_stream_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_gift_collections_foveo_stream_id", table_name="gift_collections")
    op.drop_column("gift_collections", "foveo_stream_id")
