import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.core.database import Base


class DirectorSettings(Base):
    """Director settings for UI customization applied to all their gift collections."""
    
    __tablename__ = "director_settings"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Foreign key to director (user)
    director_id: Mapped[uuid.UUID] = mapped_column(
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
    director: Mapped["User"] = relationship(
        "User",
        back_populates="director_settings"
    )
    
    def __repr__(self) -> str:
        return f"<DirectorSettings(id={self.id}, director_id={self.director_id})>"
