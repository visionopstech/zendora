"""Scope products to an optional funeral home

Revision ID: 018_product_funeral_home
Revises: 017_banner_presets
Create Date: 2026-10-21 01:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "018_product_funeral_home"
down_revision: Union[str, None] = "017_banner_presets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("funeral_home_id", sa.UUID(), nullable=True))
    op.add_column("products", sa.Column("created_by", sa.UUID(), nullable=True))
    op.create_index("ix_products_funeral_home_id", "products", ["funeral_home_id"])
    op.create_index("ix_products_created_by", "products", ["created_by"])
    op.create_foreign_key(
        "fk_products_funeral_home_id_funeral_homes",
        "products",
        "funeral_homes",
        ["funeral_home_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_products_created_by_users",
        "products",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_products_created_by_users", "products", type_="foreignkey")
    op.drop_constraint(
        "fk_products_funeral_home_id_funeral_homes", "products", type_="foreignkey"
    )
    op.drop_index("ix_products_created_by", table_name="products")
    op.drop_index("ix_products_funeral_home_id", table_name="products")
    op.drop_column("products", "created_by")
    op.drop_column("products", "funeral_home_id")
