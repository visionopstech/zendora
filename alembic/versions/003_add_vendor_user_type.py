"""Add vendor user type - vendor_id on users table

Revision ID: 003_vendor_user
Revises: 002_add_settings
Create Date: 2026-02-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_vendor_user'
down_revision: Union[str, None] = '002_add_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('vendor_id', sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        'fk_users_vendor_id',
        'users',
        'vendors',
        ['vendor_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('idx_users_vendor_id', 'users', ['vendor_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_users_vendor_id', table_name='users')
    op.drop_constraint('fk_users_vendor_id', 'users', type_='foreignkey')
    op.drop_column('users', 'vendor_id')
