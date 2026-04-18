"""Add commission and wallet tables

Revision ID: 005_commission_wallets
Revises: 004_wishlist_templates
Create Date: 2026-04-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005_commission_wallets"
down_revision: Union[str, None] = "004_wishlist_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("base_price", sa.Numeric(precision=10, scale=2), nullable=True))
    op.execute("UPDATE products SET base_price = price WHERE base_price IS NULL")
    op.alter_column("products", "base_price", nullable=False)
    op.create_check_constraint(
        "ck_products_price_gte_base_price",
        "products",
        "price >= base_price",
    )

    op.create_table(
        "manager_commissions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("manager_id", sa.UUID(), nullable=False),
        sa.Column("profit_percentage", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manager_id"),
    )
    op.create_index("idx_manager_commissions_manager_id", "manager_commissions", ["manager_id"], unique=False)

    op.create_table(
        "wallets",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("wallet_type", sa.String(length=50), nullable=False),
        sa.Column("manager_id", sa.UUID(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("balance", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0.00"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_wallets_manager_id", "wallets", ["manager_id"], unique=False)
    op.create_index("idx_wallets_wallet_type", "wallets", ["wallet_type"], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_wallets_platform
        ON wallets (wallet_type)
        WHERE wallet_type = 'PLATFORM'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_wallets_manager
        ON wallets (manager_id)
        WHERE wallet_type = 'MANAGER'
        """
    )

    op.create_table(
        "order_commissions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("manager_id", sa.UUID(), nullable=False),
        sa.Column("base_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("final_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("raw_benefit_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("manager_profit_percentage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("manager_profit_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("platform_profit_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["manager_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index("idx_order_commissions_manager_id", "order_commissions", ["manager_id"], unique=False)
    op.create_index("idx_order_commissions_order_id", "order_commissions", ["order_id"], unique=False)

    op.create_table(
        "wallet_transactions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("wallet_id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("transaction_type", sa.String(length=50), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("wallet_id", "order_id", "transaction_type", name="uq_wallet_order_transaction"),
    )
    op.create_index("idx_wallet_transactions_wallet_id", "wallet_transactions", ["wallet_id"], unique=False)
    op.create_index("idx_wallet_transactions_order_id", "wallet_transactions", ["order_id"], unique=False)

    op.execute(
        """
        INSERT INTO wallets (wallet_type, currency, balance)
        VALUES ('PLATFORM', 'USD', 0.00)
        """
    )


def downgrade() -> None:
    op.drop_index("idx_wallet_transactions_order_id", table_name="wallet_transactions")
    op.drop_index("idx_wallet_transactions_wallet_id", table_name="wallet_transactions")
    op.drop_table("wallet_transactions")

    op.drop_index("idx_order_commissions_order_id", table_name="order_commissions")
    op.drop_index("idx_order_commissions_manager_id", table_name="order_commissions")
    op.drop_table("order_commissions")

    op.execute("DROP INDEX IF EXISTS uq_wallets_manager")
    op.execute("DROP INDEX IF EXISTS uq_wallets_platform")
    op.drop_index("idx_wallets_wallet_type", table_name="wallets")
    op.drop_index("idx_wallets_manager_id", table_name="wallets")
    op.drop_table("wallets")

    op.drop_index("idx_manager_commissions_manager_id", table_name="manager_commissions")
    op.drop_table("manager_commissions")

    op.drop_constraint("ck_products_price_gte_base_price", "products", type_="check")
    op.drop_column("products", "base_price")
