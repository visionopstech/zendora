"""Seed order status-change email templates

Revision ID: 021_order_status_emails
Revises: 020_foveo_link
Create Date: 2026-11-04 14:55:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

from app.services.email_template_defaults import (
    DEFAULT_EMAIL_TEMPLATES,
    ORDER_STATUS_EMAIL_SLUGS,
)

# revision identifiers, used by Alembic.
revision: str = "021_order_status_emails"
down_revision: Union[str, None] = "020_foveo_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    existing = {
        row[0]
        for row in connection.execute(sa.text("SELECT slug FROM email_templates"))
    }
    rows = [
        {
            **row,
            "is_active": True,
            "created_at": datetime.utcnow(),
        }
        for row in DEFAULT_EMAIL_TEMPLATES
        if row["slug"] in ORDER_STATUS_EMAIL_SLUGS and row["slug"] not in existing
    ]
    if not rows:
        return

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
    op.bulk_insert(templates_table, rows)


def downgrade() -> None:
    templates = sa.table("email_templates", sa.column("slug", sa.String))
    op.execute(
        templates.delete().where(templates.c.slug.in_(sorted(ORDER_STATUS_EMAIL_SLUGS)))
    )
