"""Add wishlist template tables

Revision ID: 004_wishlist_templates
Revises: 003_vendor_user
Create Date: 2026-03-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004_wishlist_templates"
down_revision: Union[str, None] = "003_vendor_user"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wishlist_templates",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("wishlist_title", sa.String(length=255), nullable=True),
        sa.Column("wishlist_description", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("header_image_url", sa.String(length=500), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=True),
        sa.Column("secondary_color", sa.String(length=7), nullable=True),
        sa.Column("delivery_address", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_wishlist_templates_created_by", "wishlist_templates", ["created_by"], unique=False)
    op.create_index("idx_wishlist_templates_is_active", "wishlist_templates", ["is_active"], unique=False)
    op.create_index("idx_wishlist_templates_name", "wishlist_templates", ["name"], unique=False)

    op.create_table(
        "wishlist_template_products",
        sa.Column("template_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["wishlist_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("template_id", "product_id"),
    )
    op.create_index(
        "idx_wishlist_template_products_product_id",
        "wishlist_template_products",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_wishlist_template_products_product_id", table_name="wishlist_template_products")
    op.drop_table("wishlist_template_products")
    op.drop_index("idx_wishlist_templates_name", table_name="wishlist_templates")
    op.drop_index("idx_wishlist_templates_is_active", table_name="wishlist_templates")
    op.drop_index("idx_wishlist_templates_created_by", table_name="wishlist_templates")
    op.drop_table("wishlist_templates")
