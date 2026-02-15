"""Add manager_settings and wishlist_settings tables

Revision ID: 002_add_settings
Revises: 001_initial
Create Date: 2026-02-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_add_settings'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create manager_settings table
    op.create_table(
        'manager_settings',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('manager_id', sa.UUID(), nullable=False),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('banner_image_url', sa.String(length=500), nullable=True),
        sa.Column('primary_color', sa.String(length=7), nullable=True),
        sa.Column('secondary_color', sa.String(length=7), nullable=True),
        sa.Column('custom_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['manager_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_manager_settings_manager_id', 'manager_settings', ['manager_id'], unique=True)

    # Create wishlist_settings table
    op.create_table(
        'wishlist_settings',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('wishlist_id', sa.UUID(), nullable=False),
        sa.Column('banner_image_url', sa.String(length=500), nullable=True),
        sa.Column('custom_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['wishlist_id'], ['wishlists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_wishlist_settings_wishlist_id', 'wishlist_settings', ['wishlist_id'], unique=True)


def downgrade() -> None:
    op.drop_index('idx_wishlist_settings_wishlist_id', table_name='wishlist_settings')
    op.drop_table('wishlist_settings')
    op.drop_index('idx_manager_settings_manager_id', table_name='manager_settings')
    op.drop_table('manager_settings')
