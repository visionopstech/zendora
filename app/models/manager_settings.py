import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.core.database import Base


class ManagerSettings(Base):
    """Manager settings model for UI customization applied to all wishlists."""
    
    __tablename__ = "manager_settings"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Foreign key to manager (user)
    manager_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Image fields
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    banner_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Color fields
    primary_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color
    secondary_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color
    
    # Text field
    custom_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=datetime.utcnow,
        nullable=True
    )
    
    # Relationship
    manager: Mapped["User"] = relationship(
        "User",
        back_populates="manager_settings"
    )
    
    def __repr__(self) -> str:
        return f"<ManagerSettings(id={self.id}, manager_id={self.manager_id})>"
