"""Initial schema with all models

Revision ID: 001_initial
Revises: 
Create Date: 2026-02-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('manager_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['manager_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_users_email', 'users', ['email'], unique=True)
    op.create_index('idx_users_role', 'users', ['role'], unique=False)
    op.create_index('idx_users_manager_id', 'users', ['manager_id'], unique=False)

    # Create vendors table
    op.create_table(
        'vendors',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create products table
    op.create_table(
        'products',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('images', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create product_vendors junction table
    op.create_table(
        'product_vendors',
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('vendor_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('product_id', 'vendor_id')
    )

    # Create wishlists table
    op.create_table(
        'wishlists',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('admin_id', sa.UUID(), nullable=False),
        sa.Column('manager_id', sa.UUID(), nullable=False),
        sa.Column('public_slug', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='DRAFT'),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('header_image_url', sa.String(length=500), nullable=True),
        sa.Column('primary_color', sa.String(length=7), nullable=True),
        sa.Column('secondary_color', sa.String(length=7), nullable=True),
        sa.Column('delivery_address', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['manager_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_wishlists_admin_id', 'wishlists', ['admin_id'], unique=False)
    op.create_index('idx_wishlists_manager_id', 'wishlists', ['manager_id'], unique=False)
    op.create_index('idx_wishlists_public_slug', 'wishlists', ['public_slug'], unique=True)
    op.create_index('idx_wishlists_admin_status', 'wishlists', ['admin_id', 'status'], unique=False)
    
    # CRITICAL: Create partial unique index for one published wishlist per admin
    op.execute("""
        CREATE UNIQUE INDEX idx_one_published_per_admin 
        ON wishlists(admin_id) 
        WHERE status = 'PUBLISHED'
    """)

    # Create wishlist_products junction table
    op.create_table(
        'wishlist_products',
        sa.Column('wishlist_id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['wishlist_id'], ['wishlists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('wishlist_id', 'product_id')
    )

    # Create orders table
    op.create_table(
        'orders',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('visitor_id', sa.UUID(), nullable=False),
        sa.Column('wishlist_id', sa.UUID(), nullable=False),
        sa.Column('admin_id', sa.UUID(), nullable=False),
        sa.Column('stripe_session_id', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='PENDING'),
        sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['visitor_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['wishlist_id'], ['wishlists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_orders_visitor_id', 'orders', ['visitor_id'], unique=False)
    op.create_index('idx_orders_wishlist_id', 'orders', ['wishlist_id'], unique=False)
    op.create_index('idx_orders_admin_id', 'orders', ['admin_id'], unique=False)
    op.create_index('idx_orders_status', 'orders', ['status'], unique=False)
    op.create_index('idx_orders_stripe_session_id', 'orders', ['stripe_session_id'], unique=True)

    # Create order_products table
    op.create_table(
        'order_products',
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('product_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('order_id', 'product_id')
    )


def downgrade() -> None:
    op.drop_table('order_products')
    op.drop_index('idx_orders_stripe_session_id', table_name='orders')
    op.drop_index('idx_orders_status', table_name='orders')
    op.drop_index('idx_orders_admin_id', table_name='orders')
    op.drop_index('idx_orders_wishlist_id', table_name='orders')
    op.drop_index('idx_orders_visitor_id', table_name='orders')
    op.drop_table('orders')
    op.drop_table('wishlist_products')
    op.execute('DROP INDEX IF EXISTS idx_one_published_per_admin')
    op.drop_index('idx_wishlists_admin_status', table_name='wishlists')
    op.drop_index('idx_wishlists_public_slug', table_name='wishlists')
    op.drop_index('idx_wishlists_manager_id', table_name='wishlists')
    op.drop_index('idx_wishlists_admin_id', table_name='wishlists')
    op.drop_table('wishlists')
    op.drop_table('product_vendors')
    op.drop_table('products')
    op.drop_table('vendors')
    op.drop_index('idx_users_manager_id', table_name='users')
    op.drop_index('idx_users_role', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_table('users')
