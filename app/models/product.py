import enum
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Enum, ForeignKey, Numeric, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from app.core.database import Base


class Product(Base):
    """Product model for items that can be added to wishlists."""
    
    __tablename__ = "products"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Product information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    images: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=list)
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
    vendor_associations: Mapped[List["ProductVendor"]] = relationship(
        "ProductVendor",
        back_populates="product",
        cascade="all, delete-orphan"
    )
    
    wishlist_associations: Mapped[List["WishlistProduct"]] = relationship(
        "WishlistProduct",
        back_populates="product"
    )
    
    wishlist_template_associations: Mapped[List["WishlistTemplateProduct"]] = relationship(
        "WishlistTemplateProduct",
        back_populates="product"
    )
    
    order_items: Mapped[List["OrderProduct"]] = relationship(
        "OrderProduct",
        back_populates="product"
    )
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, name={self.name}, price={self.price})>"


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
