import enum
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from app.core.database import Base


class WishlistStatus(str, enum.Enum):
    """Wishlist status enumeration."""
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class Wishlist(Base):
    """Wishlist model representing a collection of products for gifting."""
    
    __tablename__ = "wishlists"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Ownership
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    manager_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Public access
    public_slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default=WishlistStatus.DRAFT.value,
        nullable=False,
        index=True
    )
    
    # Customization
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    header_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color
    secondary_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # Hex color
    delivery_address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
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
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    admin: Mapped["User"] = relationship(
        "User",
        foreign_keys=[admin_id],
        back_populates="owned_wishlists"
    )
    
    manager: Mapped["User"] = relationship(
        "User",
        foreign_keys=[manager_id],
        back_populates="managed_wishlists"
    )
    
    products: Mapped[List["WishlistProduct"]] = relationship(
        "WishlistProduct",
        back_populates="wishlist",
        cascade="all, delete-orphan"
    )
    
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        back_populates="wishlist"
    )
    
    def __repr__(self) -> str:
        return f"<Wishlist(id={self.id}, title={self.title}, status={self.status})>"


class WishlistProduct(Base):
    """Many-to-many relationship between wishlists and products."""
    
    __tablename__ = "wishlist_products"
    
    # Composite primary key
    wishlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wishlists.id", ondelete="CASCADE"),
        primary_key=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True
    )
    
    # Quantity
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    wishlist: Mapped["Wishlist"] = relationship("Wishlist", back_populates="products")
    product: Mapped["Product"] = relationship("Product", back_populates="wishlist_associations")
    
    def __repr__(self) -> str:
        return f"<WishlistProduct(wishlist_id={self.wishlist_id}, product_id={self.product_id}, quantity={self.quantity})>"


# Critical: Partial unique index to enforce one published wishlist per admin
# This will be created manually in a migration
Index("idx_wishlists_admin_status", Wishlist.admin_id, Wishlist.status)
Index("idx_wishlists_manager_id", Wishlist.manager_id)
Index("idx_wishlists_public_slug", Wishlist.public_slug)
