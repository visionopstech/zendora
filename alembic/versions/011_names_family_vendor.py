"""Split full_name, add family profile fields and vendor processing time

Revision ID: 011_names_family_vendor
Revises: 010_product_images
Create Date: 2026-09-14 00:21:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "011_names_family_vendor"
down_revision: Union[str, None] = "010_product_images"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("deceased_name", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("address", sa.JSON(), nullable=True))

    op.execute(
        """
        UPDATE users
        SET
            first_name = NULLIF(split_part(btrim(full_name), ' ', 1), ''),
            last_name = NULLIF(
                btrim(substr(btrim(full_name), length(split_part(btrim(full_name), ' ', 1)) + 1)),
                ''
            )
        WHERE full_name IS NOT NULL
        """
    )

    op.drop_column("users", "full_name")

    op.add_column(
        "vendors",
        sa.Column(
            "standard_processing_time",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(length=255), nullable=True))
    op.execute(
        """
        UPDATE users
        SET full_name = NULLIF(btrim(concat_ws(' ', first_name, last_name)), '')
        """
    )
    op.drop_column("users", "address")
    op.drop_column("users", "deceased_name")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("vendors", "standard_processing_time")
