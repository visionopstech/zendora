"""Add email_templates table and seed system templates

Revision ID: 014_email_templates
Revises: 013_optional_collection_director
Create Date: 2026-09-17 17:30:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

from app.services.email_template_defaults import DEFAULT_EMAIL_TEMPLATES

# revision identifiers, used by Alembic.
revision: str = "014_email_templates"
down_revision: Union[str, None] = "013_optional_collection_director"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_templates",
        sa.Column("id", UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("available_variables", JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_email_templates_slug", "email_templates", ["slug"], unique=True)

    templates_table = sa.table(
        "email_templates",
        sa.column("slug", sa.String),
        sa.column("name", sa.String),
        sa.column("subject", sa.Text),
        sa.column("body", sa.Text),
        sa.column("description", sa.Text),
        sa.column("available_variables", JSON),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )
    now = datetime.utcnow()
    op.bulk_insert(
        templates_table,
        [
            {
                **row,
                "is_active": True,
                "created_at": now,
            }
            for row in DEFAULT_EMAIL_TEMPLATES
        ],
    )


def downgrade() -> None:
    op.drop_index("idx_email_templates_slug", table_name="email_templates")
    op.drop_table("email_templates")
