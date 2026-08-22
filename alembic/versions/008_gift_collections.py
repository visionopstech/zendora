"""Rename wishlists, settings, orders and finance to gift collections / directors

Revision ID: 008_gift_collections
Revises: 007_funeral_homes
Create Date: 2026-08-22 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "008_gift_collections"
down_revision: Union[str, None] = "007_funeral_homes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- gift collections ---
    op.rename_table("wishlists", "gift_collections")
    op.alter_column("gift_collections", "admin_id", new_column_name="family_admin_id")
    op.alter_column("gift_collections", "manager_id", new_column_name="director_id")
    op.add_column("gift_collections", sa.Column("funeral_home_id", sa.UUID(), nullable=True))
    op.create_index(
        "idx_gift_collections_funeral_home_id",
        "gift_collections",
        ["funeral_home_id"],
        unique=False,
    )
    op.create_foreign_key(
        "gift_collections_funeral_home_id_fkey",
        "gift_collections",
        "funeral_homes",
        ["funeral_home_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("ALTER INDEX IF EXISTS idx_wishlists_admin_id RENAME TO idx_gift_collections_family_admin_id")
    op.execute("ALTER INDEX IF EXISTS idx_wishlists_manager_id RENAME TO idx_gift_collections_director_id")
    op.execute("ALTER INDEX IF EXISTS idx_wishlists_public_slug RENAME TO idx_gift_collections_public_slug")
    op.execute("ALTER INDEX IF EXISTS idx_wishlists_admin_status RENAME TO idx_gift_collections_family_admin_status")
    op.execute("DROP INDEX IF EXISTS idx_one_published_per_admin")
    op.execute(
        """
        CREATE UNIQUE INDEX idx_one_published_per_family_admin
        ON gift_collections (family_admin_id)
        WHERE status = 'PUBLISHED'
        """
    )
    op.execute(
        """
        UPDATE gift_collections AS gc
        SET funeral_home_id = u.funeral_home_id
        FROM users AS u
        WHERE gc.director_id = u.id
        """
    )

    # --- collection products ---
    op.rename_table("wishlist_products", "gift_collection_products")
    op.alter_column("gift_collection_products", "wishlist_id", new_column_name="gift_collection_id")

    # --- collection settings ---
    op.rename_table("wishlist_settings", "gift_collection_settings")
    op.alter_column("gift_collection_settings", "wishlist_id", new_column_name="gift_collection_id")
    op.execute(
        "ALTER INDEX IF EXISTS idx_wishlist_settings_wishlist_id RENAME TO idx_gift_collection_settings_gift_collection_id"
    )

    # --- director settings ---
    op.rename_table("manager_settings", "director_settings")
    op.alter_column("director_settings", "manager_id", new_column_name="director_id")
    op.execute(
        "ALTER INDEX IF EXISTS idx_manager_settings_manager_id RENAME TO idx_director_settings_director_id"
    )

    # --- orders ---
    op.alter_column("orders", "wishlist_id", new_column_name="gift_collection_id")
    op.alter_column("orders", "admin_id", new_column_name="family_admin_id")
    op.add_column("orders", sa.Column("funeral_home_id", sa.UUID(), nullable=True))
    op.create_index("idx_orders_funeral_home_id", "orders", ["funeral_home_id"], unique=False)
    op.create_foreign_key(
        "orders_funeral_home_id_fkey",
        "orders",
        "funeral_homes",
        ["funeral_home_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("ALTER INDEX IF EXISTS idx_orders_wishlist_id RENAME TO idx_orders_gift_collection_id")
    op.execute("ALTER INDEX IF EXISTS idx_orders_admin_id RENAME TO idx_orders_family_admin_id")
    op.execute(
        """
        UPDATE orders AS o
        SET funeral_home_id = gc.funeral_home_id
        FROM gift_collections AS gc
        WHERE o.gift_collection_id = gc.id
        """
    )

    # --- finance ---
    op.rename_table("manager_commissions", "director_commissions")
    op.alter_column("director_commissions", "manager_id", new_column_name="director_id")
    op.execute(
        "ALTER INDEX IF EXISTS idx_manager_commissions_manager_id RENAME TO idx_director_commissions_director_id"
    )

    op.alter_column("wallets", "manager_id", new_column_name="director_id")
    op.execute("ALTER INDEX IF EXISTS idx_wallets_manager_id RENAME TO idx_wallets_director_id")
    op.execute("DROP INDEX IF EXISTS uq_wallets_director")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_wallets_director
        ON wallets (director_id)
        WHERE wallet_type = 'DIRECTOR'
        """
    )

    op.alter_column("order_commissions", "manager_id", new_column_name="director_id")
    op.alter_column(
        "order_commissions",
        "manager_profit_percentage",
        new_column_name="director_profit_percentage",
    )
    op.alter_column(
        "order_commissions",
        "manager_profit_amount",
        new_column_name="director_profit_amount",
    )
    op.execute(
        "ALTER INDEX IF EXISTS idx_order_commissions_manager_id RENAME TO idx_order_commissions_director_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX IF EXISTS idx_order_commissions_director_id RENAME TO idx_order_commissions_manager_id"
    )
    op.alter_column(
        "order_commissions",
        "director_profit_amount",
        new_column_name="manager_profit_amount",
    )
    op.alter_column(
        "order_commissions",
        "director_profit_percentage",
        new_column_name="manager_profit_percentage",
    )
    op.alter_column("order_commissions", "director_id", new_column_name="manager_id")

    op.execute("DROP INDEX IF EXISTS uq_wallets_director")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_wallets_director
        ON wallets (manager_id)
        WHERE wallet_type = 'DIRECTOR'
        """
    )
    op.execute("ALTER INDEX IF EXISTS idx_wallets_director_id RENAME TO idx_wallets_manager_id")
    op.alter_column("wallets", "director_id", new_column_name="manager_id")

    op.execute(
        "ALTER INDEX IF EXISTS idx_director_commissions_director_id RENAME TO idx_manager_commissions_manager_id"
    )
    op.alter_column("director_commissions", "director_id", new_column_name="manager_id")
    op.rename_table("director_commissions", "manager_commissions")

    op.drop_constraint("orders_funeral_home_id_fkey", "orders", type_="foreignkey")
    op.drop_index("idx_orders_funeral_home_id", table_name="orders")
    op.drop_column("orders", "funeral_home_id")
    op.execute("ALTER INDEX IF EXISTS idx_orders_family_admin_id RENAME TO idx_orders_admin_id")
    op.execute("ALTER INDEX IF EXISTS idx_orders_gift_collection_id RENAME TO idx_orders_wishlist_id")
    op.alter_column("orders", "family_admin_id", new_column_name="admin_id")
    op.alter_column("orders", "gift_collection_id", new_column_name="wishlist_id")

    op.execute(
        "ALTER INDEX IF EXISTS idx_director_settings_director_id RENAME TO idx_manager_settings_manager_id"
    )
    op.alter_column("director_settings", "director_id", new_column_name="manager_id")
    op.rename_table("director_settings", "manager_settings")

    op.execute(
        "ALTER INDEX IF EXISTS idx_gift_collection_settings_gift_collection_id RENAME TO idx_wishlist_settings_wishlist_id"
    )
    op.alter_column("gift_collection_settings", "gift_collection_id", new_column_name="wishlist_id")
    op.rename_table("gift_collection_settings", "wishlist_settings")

    op.alter_column("gift_collection_products", "gift_collection_id", new_column_name="wishlist_id")
    op.rename_table("gift_collection_products", "wishlist_products")

    op.execute("DROP INDEX IF EXISTS idx_one_published_per_family_admin")
    op.execute(
        """
        CREATE UNIQUE INDEX idx_one_published_per_admin
        ON gift_collections (family_admin_id)
        WHERE status = 'PUBLISHED'
        """
    )
    op.execute("ALTER INDEX IF EXISTS idx_gift_collections_family_admin_status RENAME TO idx_wishlists_admin_status")
    op.execute("ALTER INDEX IF EXISTS idx_gift_collections_public_slug RENAME TO idx_wishlists_public_slug")
    op.execute("ALTER INDEX IF EXISTS idx_gift_collections_director_id RENAME TO idx_wishlists_manager_id")
    op.execute("ALTER INDEX IF EXISTS idx_gift_collections_family_admin_id RENAME TO idx_wishlists_admin_id")
    op.drop_constraint("gift_collections_funeral_home_id_fkey", "gift_collections", type_="foreignkey")
    op.drop_index("idx_gift_collections_funeral_home_id", table_name="gift_collections")
    op.drop_column("gift_collections", "funeral_home_id")
    op.alter_column("gift_collections", "director_id", new_column_name="manager_id")
    op.alter_column("gift_collections", "family_admin_id", new_column_name="admin_id")
    op.rename_table("gift_collections", "wishlists")
