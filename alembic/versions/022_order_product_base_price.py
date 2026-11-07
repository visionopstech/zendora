"""Snapshot gift base price on order line items

Revision ID: 022_order_product_base_price
Revises: 021_order_status_emails
Create Date: 2026-11-07 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "022_order_product_base_price"
down_revision: Union[str, None] = "021_order_status_emails"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "order_products",
        sa.Column("base_price", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.execute(
        """
        UPDATE order_products AS op
        SET base_price = p.base_price
        FROM products AS p
        WHERE p.id = op.product_id
          AND op.base_price IS NULL
        """
    )
    op.execute(
        """
        UPDATE order_products
        SET base_price = product_price
        WHERE base_price IS NULL
        """
    )
    op.alter_column("order_products", "base_price", nullable=False)


def downgrade() -> None:
    op.drop_column("order_products", "base_price")
