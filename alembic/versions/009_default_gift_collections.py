"""Rename wishlist templates to default gift collections

Revision ID: 009_default_gift_collections
Revises: 008_gift_collections
Create Date: 2026-08-22 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "009_default_gift_collections"
down_revision: Union[str, None] = "008_gift_collections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("wishlist_templates", "default_gift_collections")
    op.alter_column(
        "default_gift_collections",
        "wishlist_title",
        new_column_name="collection_title",
    )
    op.alter_column(
        "default_gift_collections",
        "wishlist_description",
        new_column_name="collection_description",
    )
    op.add_column(
        "default_gift_collections",
        sa.Column(
            "owner_scope",
            sa.String(length=50),
            nullable=False,
            server_default="ZENDORA",
        ),
    )
    op.add_column(
        "default_gift_collections",
        sa.Column("funeral_home_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "idx_default_gift_collections_owner_scope",
        "default_gift_collections",
        ["owner_scope"],
        unique=False,
    )
    op.create_index(
        "idx_default_gift_collections_funeral_home_id",
        "default_gift_collections",
        ["funeral_home_id"],
        unique=False,
    )
    op.create_foreign_key(
        "default_gift_collections_funeral_home_id_fkey",
        "default_gift_collections",
        "funeral_homes",
        ["funeral_home_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute("ALTER INDEX IF EXISTS idx_wishlist_templates_created_by RENAME TO idx_default_gift_collections_created_by")
    op.execute("ALTER INDEX IF EXISTS idx_wishlist_templates_is_active RENAME TO idx_default_gift_collections_is_active")
    op.execute("ALTER INDEX IF EXISTS idx_wishlist_templates_name RENAME TO idx_default_gift_collections_name")
    op.execute("UPDATE default_gift_collections SET owner_scope = 'ZENDORA'")

    op.rename_table("wishlist_template_products", "default_gift_collection_products")
    op.alter_column(
        "default_gift_collection_products",
        "template_id",
        new_column_name="default_collection_id",
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_wishlist_template_products_product_id RENAME TO idx_default_gift_collection_products_product_id"
    )

    op.add_column(
        "gift_collections",
        sa.Column("source_default_collection_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "idx_gift_collections_source_default_collection_id",
        "gift_collections",
        ["source_default_collection_id"],
        unique=False,
    )
    op.create_foreign_key(
        "gift_collections_source_default_collection_id_fkey",
        "gift_collections",
        "default_gift_collections",
        ["source_default_collection_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "gift_collections_source_default_collection_id_fkey",
        "gift_collections",
        type_="foreignkey",
    )
    op.drop_index(
        "idx_gift_collections_source_default_collection_id",
        table_name="gift_collections",
    )
    op.drop_column("gift_collections", "source_default_collection_id")

    op.execute(
        "ALTER INDEX IF EXISTS idx_default_gift_collection_products_product_id RENAME TO idx_wishlist_template_products_product_id"
    )
    op.alter_column(
        "default_gift_collection_products",
        "default_collection_id",
        new_column_name="template_id",
    )
    op.rename_table("default_gift_collection_products", "wishlist_template_products")

    op.drop_constraint(
        "default_gift_collections_funeral_home_id_fkey",
        "default_gift_collections",
        type_="foreignkey",
    )
    op.drop_index(
        "idx_default_gift_collections_funeral_home_id",
        table_name="default_gift_collections",
    )
    op.drop_index(
        "idx_default_gift_collections_owner_scope",
        table_name="default_gift_collections",
    )
    op.drop_column("default_gift_collections", "funeral_home_id")
    op.drop_column("default_gift_collections", "owner_scope")
    op.execute("ALTER INDEX IF EXISTS idx_default_gift_collections_name RENAME TO idx_wishlist_templates_name")
    op.execute("ALTER INDEX IF EXISTS idx_default_gift_collections_is_active RENAME TO idx_wishlist_templates_is_active")
    op.execute("ALTER INDEX IF EXISTS idx_default_gift_collections_created_by RENAME TO idx_wishlist_templates_created_by")
    op.alter_column(
        "default_gift_collections",
        "collection_description",
        new_column_name="wishlist_description",
    )
    op.alter_column(
        "default_gift_collections",
        "collection_title",
        new_column_name="wishlist_title",
    )
    op.rename_table("default_gift_collections", "wishlist_templates")
