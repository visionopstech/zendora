"""Allow gift collections (and order commissions) without a director

Revision ID: 013_optional_collection_director
Revises: 012_deceased_names_product_details
Create Date: 2026-09-17 17:16:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "013_optional_collection_director"
down_revision: Union[str, None] = "012_deceased_names_product_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _recreate_director_fk(table: str, new_name: str, ondelete: str, nullable: bool) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table):
        if fk["constrained_columns"] == ["director_id"]:
            op.drop_constraint(fk["name"], table, type_="foreignkey")
            break
    op.alter_column(table, "director_id", existing_type=sa.UUID(), nullable=nullable)
    op.create_foreign_key(
        new_name,
        table,
        "users",
        ["director_id"],
        ["id"],
        ondelete=ondelete,
    )


def upgrade() -> None:
    _recreate_director_fk(
        "gift_collections",
        "gift_collections_director_id_fkey",
        "SET NULL",
        nullable=True,
    )
    _recreate_director_fk(
        "order_commissions",
        "order_commissions_director_id_fkey",
        "SET NULL",
        nullable=True,
    )


def downgrade() -> None:
    _recreate_director_fk(
        "order_commissions",
        "order_commissions_director_id_fkey",
        "CASCADE",
        nullable=False,
    )
    _recreate_director_fk(
        "gift_collections",
        "gift_collections_director_id_fkey",
        "CASCADE",
        nullable=False,
    )
