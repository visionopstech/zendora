"""Move director commission rate to funeral homes

Revision ID: 019_funeral_home_commission
Revises: 018_product_funeral_home
Create Date: 2026-10-22 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "019_funeral_home_commission"
down_revision: Union[str, None] = "018_product_funeral_home"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "funeral_homes",
        sa.Column(
            "profit_percentage",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="0.00",
        ),
    )
    op.execute(
        """
        UPDATE funeral_homes AS fh
        SET profit_percentage = COALESCE(
            (
                SELECT dc.profit_percentage
                FROM director_commissions AS dc
                WHERE dc.director_id = fh.director_id
            ),
            (
                SELECT dc.profit_percentage
                FROM director_commissions AS dc
                JOIN users AS u ON u.id = dc.director_id
                WHERE u.funeral_home_id = fh.id
                  AND u.role = 'DIRECTOR'
                ORDER BY dc.updated_at DESC NULLS LAST, dc.created_at DESC
                LIMIT 1
            ),
            0.00
        )
        """
    )
    op.drop_table("director_commissions")


def downgrade() -> None:
    op.create_table(
        "director_commissions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("director_id", sa.UUID(), nullable=False),
        sa.Column(
            "profit_percentage",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["director_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("director_id"),
    )
    op.create_index(
        "idx_director_commissions_director_id",
        "director_commissions",
        ["director_id"],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO director_commissions (director_id, profit_percentage, created_at)
        SELECT fh.director_id, fh.profit_percentage, NOW()
        FROM funeral_homes AS fh
        WHERE fh.director_id IS NOT NULL
        """
    )
    op.drop_column("funeral_homes", "profit_percentage")
