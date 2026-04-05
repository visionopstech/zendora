import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WishlistTemplate(Base):
    """Reusable wishlist template created by a super admin."""

    __tablename__ = "wishlist_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    wishlist_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    wishlist_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
        back_populates="created_wishlist_templates",
    )
    products: Mapped[List["WishlistTemplateProduct"]] = relationship(
        "WishlistTemplateProduct",
        back_populates="template",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<WishlistTemplate(id={self.id}, name={self.name}, is_active={self.is_active})>"


class WishlistTemplateProduct(Base):
    """Many-to-many relationship between templates and products."""

    __tablename__ = "wishlist_template_products"

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wishlist_templates.id", ondelete="CASCADE"),
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

    template: Mapped["WishlistTemplate"] = relationship("WishlistTemplate", back_populates="products")
    product: Mapped["Product"] = relationship("Product", back_populates="wishlist_template_associations")

    def __repr__(self) -> str:
        return (
            f"<WishlistTemplateProduct(template_id={self.template_id}, "
            f"product_id={self.product_id}, quantity={self.quantity})>"
        )


Index("idx_wishlist_templates_name", WishlistTemplate.name)
Index("idx_wishlist_templates_created_by", WishlistTemplate.created_by)
