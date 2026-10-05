"""Give default gift collections a per-user owner

Revision ID: 015_default_collection_owner
Revises: 014_email_templates
Create Date: 2026-10-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "015_default_collection_owner"
down_revision: Union[str, None] = "014_email_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "default_gift_collections",
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "idx_default_gift_collections_owner_user_id",
        "default_gift_collections",
        ["owner_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "default_gift_collections_owner_user_id_fkey",
        "default_gift_collections",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Funeral-home defaults become the personal defaults of the director who
    # created them.
    op.execute(
        """
        UPDATE default_gift_collections AS d
        SET owner_user_id = d.created_by
        FROM users AS u
        WHERE d.owner_scope = 'FUNERAL_HOME'
          AND d.created_by = u.id
          AND u.role = 'DIRECTOR'
          AND (d.funeral_home_id IS NULL OR u.funeral_home_id = d.funeral_home_id)
        """
    )

    # Anything left without a usable creator falls to the main director.
    op.execute(
        """
        UPDATE default_gift_collections AS d
        SET owner_user_id = f.director_id
        FROM funeral_homes AS f
        WHERE d.owner_scope = 'FUNERAL_HOME'
          AND d.owner_user_id IS NULL
          AND d.funeral_home_id = f.id
          AND f.director_id IS NOT NULL
        """
    )

    # The Zendora pool is shared by all super admins, so it has no owner.
    op.execute(
        "UPDATE default_gift_collections SET owner_user_id = NULL WHERE owner_scope = 'ZENDORA'"
    )

    # Keep the funeral home in sync with whoever ended up owning the default.
    op.execute(
        """
        UPDATE default_gift_collections AS d
        SET funeral_home_id = u.funeral_home_id
        FROM users AS u
        WHERE d.owner_user_id = u.id
          AND d.funeral_home_id IS DISTINCT FROM u.funeral_home_id
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "default_gift_collections_owner_user_id_fkey",
        "default_gift_collections",
        type_="foreignkey",
    )
    op.drop_index(
        "idx_default_gift_collections_owner_user_id",
        table_name="default_gift_collections",
    )
    op.drop_column("default_gift_collections", "owner_user_id")
