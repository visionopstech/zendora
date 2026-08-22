"""Create funeral homes and rename users.manager_id

Revision ID: 007_funeral_homes
Revises: 006_rename_roles
Create Date: 2026-08-22 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "007_funeral_homes"
down_revision: Union[str, None] = "006_rename_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "funeral_homes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("address", sa.JSON(), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("director_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["director_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("director_id"),
    )
    op.create_index("idx_funeral_homes_name", "funeral_homes", ["name"], unique=False)
    op.create_index("idx_funeral_homes_is_active", "funeral_homes", ["is_active"], unique=False)

    op.alter_column("users", "manager_id", new_column_name="director_id")
    op.execute("ALTER INDEX IF EXISTS idx_users_manager_id RENAME TO idx_users_director_id")
    op.execute(
        "ALTER TABLE users RENAME CONSTRAINT users_manager_id_fkey TO users_director_id_fkey"
    )

    op.add_column("users", sa.Column("funeral_home_id", sa.UUID(), nullable=True))
    op.create_index("idx_users_funeral_home_id", "users", ["funeral_home_id"], unique=False)
    op.create_foreign_key(
        "users_funeral_home_id_fkey",
        "users",
        "funeral_homes",
        ["funeral_home_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("users_funeral_home_id_fkey", "users", type_="foreignkey")
    op.drop_index("idx_users_funeral_home_id", table_name="users")
    op.drop_column("users", "funeral_home_id")

    op.execute(
        "ALTER TABLE users RENAME CONSTRAINT users_director_id_fkey TO users_manager_id_fkey"
    )
    op.execute("ALTER INDEX IF EXISTS idx_users_director_id RENAME TO idx_users_manager_id")
    op.alter_column("users", "director_id", new_column_name="manager_id")

    op.drop_index("idx_funeral_homes_is_active", table_name="funeral_homes")
    op.drop_index("idx_funeral_homes_name", table_name="funeral_homes")
    op.drop_table("funeral_homes")
