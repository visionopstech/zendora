import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from app.core.database import Base


class WishlistSettings(Base):
    """Wishlist-specific settings model for UI customization."""
    
    __tablename__ = "wishlist_settings"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Foreign key to wishlist
    wishlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wishlists.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    
    # Image field
    banner_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
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
    wishlist: Mapped["Wishlist"] = relationship(
        "Wishlist",
        back_populates="settings"
    )
    
    def __repr__(self) -> str:
        return f"<WishlistSettings(id={self.id}, wishlist_id={self.wishlist_id})>"
