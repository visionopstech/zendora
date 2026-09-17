"""Split deceased_name and add products.details

Revision ID: 012_deceased_names_product_details
Revises: 011_names_family_vendor
Create Date: 2026-09-17 16:52:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "012_deceased_names_product_details"
down_revision: Union[str, None] = "011_names_family_vendor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("deceased_first_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("deceased_last_name", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE users
        SET
            deceased_first_name = NULLIF(split_part(btrim(deceased_name), ' ', 1), ''),
            deceased_last_name = NULLIF(
                btrim(substr(btrim(deceased_name), length(split_part(btrim(deceased_name), ' ', 1)) + 1)),
                ''
            )
        WHERE deceased_name IS NOT NULL
        """
    )
    op.drop_column("users", "deceased_name")

    op.add_column(
        "products",
        sa.Column(
            "details",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "details")

    op.add_column(
        "users",
        sa.Column("deceased_name", sa.String(length=255), nullable=True),
    )
    op.execute(
        """
        UPDATE users
        SET deceased_name = NULLIF(btrim(concat_ws(' ', deceased_first_name, deceased_last_name)), '')
        """
    )
    op.drop_column("users", "deceased_last_name")
    op.drop_column("users", "deceased_first_name")
