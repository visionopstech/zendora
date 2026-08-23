import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DefaultCollectionScope(str, enum.Enum):
    """Who owns a default gift collection."""

    ZENDORA = "ZENDORA"
    FUNERAL_HOME = "FUNERAL_HOME"


class DefaultGiftCollection(Base):
    """A reusable gift collection preset owned by Zendora or by a funeral home."""

    __tablename__ = "default_gift_collections"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_scope: Mapped[str] = mapped_column(
        String(50),
        default=DefaultCollectionScope.ZENDORA.value,
        nullable=False,
        index=True,
    )
    funeral_home_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("funeral_homes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    collection_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    collection_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    header_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    secondary_color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    delivery_address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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

    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_default_gift_collections",
    )
    funeral_home: Mapped[Optional["FuneralHome"]] = relationship(
        "FuneralHome",
        back_populates="default_gift_collections",
    )
    products: Mapped[List["DefaultGiftCollectionProduct"]] = relationship(
        "DefaultGiftCollectionProduct",
        back_populates="default_collection",
        cascade="all, delete-orphan",
    )
    derived_collections: Mapped[List["GiftCollection"]] = relationship(
        "GiftCollection",
        back_populates="source_default_collection",
    )

    @property
    def is_zendora_default(self) -> bool:
        return self.owner_scope == DefaultCollectionScope.ZENDORA.value

    def __repr__(self) -> str:
        return (
            f"<DefaultGiftCollection(id={self.id}, name={self.name}, "
            f"owner_scope={self.owner_scope}, is_active={self.is_active})>"
        )


class DefaultGiftCollectionProduct(Base):
    """Many-to-many relationship between default collections and gifts."""

    __tablename__ = "default_gift_collection_products"

    default_collection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("default_gift_collections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    default_collection: Mapped["DefaultGiftCollection"] = relationship(
        "DefaultGiftCollection",
        back_populates="products",
    )
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="default_collection_associations",
    )

    def __repr__(self) -> str:
        return (
            f"<DefaultGiftCollectionProduct(default_collection_id={self.default_collection_id}, "
            f"product_id={self.product_id}, quantity={self.quantity})>"
        )


Index("idx_default_gift_collections_name", DefaultGiftCollection.name)
Index("idx_default_gift_collections_created_by", DefaultGiftCollection.created_by)
