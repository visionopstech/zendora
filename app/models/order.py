import enum
import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, ForeignKey, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from app.core.database import Base


class OrderStatus(str, enum.Enum):
    """Order status enumeration."""
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class Order(Base):
    """Order model representing a purchase transaction."""
    
    __tablename__ = "orders"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Relationships
    visitor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    wishlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wishlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True  # Denormalized for reporting
    )
    
    # Stripe information
    stripe_session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    
    # Order details
    status: Mapped[str] = mapped_column(
        String(50),
        default=OrderStatus.PENDING.value,
        nullable=False,
        index=True
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=datetime.utcnow,
        nullable=True
    )
    
    # Relationships
    visitor: Mapped["User"] = relationship(
        "User",
        foreign_keys=[visitor_id],
        back_populates="orders"
    )
    
    wishlist: Mapped["Wishlist"] = relationship(
        "Wishlist",
        back_populates="orders"
    )
    
    admin: Mapped["User"] = relationship(
        "User",
        foreign_keys=[admin_id]
    )
    
    products: Mapped[List["OrderProduct"]] = relationship(
        "OrderProduct",
        back_populates="order",
        cascade="all, delete-orphan"
    )

    commission: Mapped[Optional["OrderCommission"]] = relationship(
        "OrderCommission",
        back_populates="order",
        uselist=False,
        cascade="all, delete-orphan"
    )

    wallet_transactions: Mapped[List["WalletTransaction"]] = relationship(
        "WalletTransaction",
        back_populates="order",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Order(id={self.id}, status={self.status}, total={self.total_amount})>"


class OrderProduct(Base):
    """Order products with snapshot of product details at time of purchase."""
    
    __tablename__ = "order_products"
    
    # Composite primary key
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        primary_key=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True
    )
    
    # Snapshot of product details at time of purchase
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="products")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")
    
    def __repr__(self) -> str:
        return f"<OrderProduct(order_id={self.order_id}, product={self.product_name}, qty={self.quantity})>"
