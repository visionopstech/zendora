import enum
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from app.core.database import Base


class GiftCollectionStatus(str, enum.Enum):
    """Gift collection status enumeration."""
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class GiftCollection(Base):
    """A gift collection owned by a family, hosted by a funeral home."""
    
    __tablename__ = "gift_collections"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Ownership
    family_admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    director_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    funeral_home_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("funeral_homes.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Provenance: the default collection this one was copied from, if any
    source_default_collection_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("default_gift_collections.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Public access
    public_slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default=GiftCollectionStatus.DRAFT.value,
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
    family_admin: Mapped["User"] = relationship(
        "User",
        foreign_keys=[family_admin_id],
        back_populates="owned_gift_collections"
    )
    
    director: Mapped["User"] = relationship(
        "User",
        foreign_keys=[director_id],
        back_populates="directed_gift_collections"
    )
    
    funeral_home: Mapped[Optional["FuneralHome"]] = relationship(
        "FuneralHome",
        back_populates="gift_collections"
    )
    
    source_default_collection: Mapped[Optional["DefaultGiftCollection"]] = relationship(
        "DefaultGiftCollection",
        back_populates="derived_collections"
    )
    
    products: Mapped[List["GiftCollectionProduct"]] = relationship(
        "GiftCollectionProduct",
        back_populates="gift_collection",
        cascade="all, delete-orphan"
    )
    
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        back_populates="gift_collection"
    )
    
    # Collection-specific settings
    settings: Mapped[Optional["GiftCollectionSettings"]] = relationship(
        "GiftCollectionSettings",
        back_populates="gift_collection",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<GiftCollection(id={self.id}, title={self.title}, status={self.status})>"


class GiftCollectionProduct(Base):
    """Many-to-many relationship between gift collections and gifts (products)."""
    
    __tablename__ = "gift_collection_products"
    
    # Composite primary key
    gift_collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gift_collections.id", ondelete="CASCADE"),
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
    gift_collection: Mapped["GiftCollection"] = relationship("GiftCollection", back_populates="products")
    product: Mapped["Product"] = relationship("Product", back_populates="gift_collection_associations")
    
    def __repr__(self) -> str:
        return (
            f"<GiftCollectionProduct(gift_collection_id={self.gift_collection_id}, "
            f"product_id={self.product_id}, quantity={self.quantity})>"
        )


# A partial unique index enforcing one published collection per family admin is
# created in the migrations (idx_one_published_per_family_admin).
Index("idx_gift_collections_family_admin_status", GiftCollection.family_admin_id, GiftCollection.status)
Index("idx_gift_collections_director_id", GiftCollection.director_id)
Index("idx_gift_collections_public_slug", GiftCollection.public_slug)
