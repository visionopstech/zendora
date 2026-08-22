import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from app.core.database import Base


class Product(Base):
    """Gift model for items that can be added to gift collections."""
    
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= base_price", name="ck_products_price_gte_base_price"),
    )
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Product information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
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
    
    # Relationships
    # Eagerly loaded: every serialized gift exposes its gallery.
    images: Mapped[List["ProductImage"]] = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.sort_order",
        lazy="selectin"
    )
    
    vendor_associations: Mapped[List["ProductVendor"]] = relationship(
        "ProductVendor",
        back_populates="product",
        cascade="all, delete-orphan"
    )
    
    gift_collection_associations: Mapped[List["GiftCollectionProduct"]] = relationship(
        "GiftCollectionProduct",
        back_populates="product"
    )
    
    default_collection_associations: Mapped[List["DefaultGiftCollectionProduct"]] = relationship(
        "DefaultGiftCollectionProduct",
        back_populates="product"
    )
    
    order_items: Mapped[List["OrderProduct"]] = relationship(
        "OrderProduct",
        back_populates="product"
    )
    
    @property
    def primary_image_url(self) -> Optional[str]:
        """URL of the gallery image flagged as primary, falling back to the first one."""
        if not self.images:
            return None
        for image in self.images:
            if image.is_primary:
                return image.url
        return self.images[0].url

    def __repr__(self) -> str:
        return (
            f"<Product(id={self.id}, name={self.name}, "
            f"base_price={self.base_price}, price={self.price})>"
        )


class ProductImage(Base):
    """A single image in a gift's gallery. Exactly one image can be primary."""
    
    __tablename__ = "product_images"
    
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    alt_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    
    product: Mapped["Product"] = relationship("Product", back_populates="images")
    
    def __repr__(self) -> str:
        return f"<ProductImage(id={self.id}, product_id={self.product_id}, is_primary={self.is_primary})>"


class ProductVendor(Base):
    """Many-to-many relationship between products and vendors."""
    
    __tablename__ = "product_vendors"
    
    # Composite primary key
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"),
        primary_key=True
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="vendor_associations")
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="product_associations")
    
    def __repr__(self) -> str:
        return f"<ProductVendor(product_id={self.product_id}, vendor_id={self.vendor_id})>"


Index("idx_product_images_product_id", ProductImage.product_id)
