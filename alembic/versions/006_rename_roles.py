"""Rename MANAGER/ADMIN roles and MANAGER wallet type

Revision ID: 006_rename_roles
Revises: 005_commission_wallets
Create Date: 2026-08-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006_rename_roles"
down_revision: Union[str, None] = "005_commission_wallets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET role = 'DIRECTOR' WHERE role = 'MANAGER'")
    op.execute("UPDATE users SET role = 'FAMILY_ADMIN' WHERE role = 'ADMIN'")
    op.execute("UPDATE wallets SET wallet_type = 'DIRECTOR' WHERE wallet_type = 'MANAGER'")

    op.execute("DROP INDEX IF EXISTS uq_wallets_manager")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_wallets_director
        ON wallets (manager_id)
        WHERE wallet_type = 'DIRECTOR'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_wallets_director")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_wallets_manager
        ON wallets (manager_id)
        WHERE wallet_type = 'MANAGER'
        """
    )

    op.execute("UPDATE wallets SET wallet_type = 'MANAGER' WHERE wallet_type = 'DIRECTOR'")
    op.execute("UPDATE users SET role = 'ADMIN' WHERE role = 'FAMILY_ADMIN'")
    op.execute("UPDATE users SET role = 'MANAGER' WHERE role = 'DIRECTOR'")
