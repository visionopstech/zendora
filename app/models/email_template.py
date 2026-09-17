import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmailTemplateSlug(str, enum.Enum):
    """Stable slugs used in code to look up email templates."""

    ORDER_CREATED_VENDOR = "order_created_vendor"
    ORDER_CREATED_FAMILY_ADMIN = "order_created_family_admin"
    ORDER_CREATED_BUYER = "order_created_buyer"
    ORDER_CREATED_SUPER_ADMIN = "order_created_super_admin"
    COLLECTION_CREATED_FAMILY_ADMIN = "collection_created_family_admin"
    COLLECTION_CREATED_DIRECTOR = "collection_created_director"
    COLLECTION_CREATED_SUPER_ADMIN = "collection_created_super_admin"


class EmailTemplate(Base):
    """A super-admin-editable email subject and body, looked up by slug."""

    __tablename__ = "email_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    available_variables: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=datetime.utcnow,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<EmailTemplate(slug={self.slug}, name={self.name})>"
