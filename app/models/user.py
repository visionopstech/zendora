import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from app.core.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    SUPER_ADMIN = "SUPER_ADMIN"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"
    VISITOR = "VISITOR"


class User(Base):
    """User model representing all user types in the system."""
    
    __tablename__ = "users"
    
    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()"
    )
    
    # Authentication fields
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Profile fields
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Role and status
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Manager relationship (for ADMIN users only)
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
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
    manager: Mapped[Optional["User"]] = relationship(
        "User",
        remote_side=[id],
        foreign_keys=[manager_id],
        back_populates="admins"
    )
    
    admins: Mapped[List["User"]] = relationship(
        "User",
        back_populates="manager",
        foreign_keys=[manager_id]
    )
    
    # Wishlists managed by this user (if MANAGER)
    managed_wishlists: Mapped[List["Wishlist"]] = relationship(
        "Wishlist",
        foreign_keys="Wishlist.manager_id",
        back_populates="manager"
    )
    
    # Wishlists owned by this user (if ADMIN)
    owned_wishlists: Mapped[List["Wishlist"]] = relationship(
        "Wishlist",
        foreign_keys="Wishlist.admin_id",
        back_populates="admin"
    )
    
    # Orders placed by this user (if VISITOR)
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        foreign_keys="Order.visitor_id",
        back_populates="visitor"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
    
    @property
    def is_super_admin(self) -> bool:
        """Check if user is a super admin."""
        return self.role == UserRole.SUPER_ADMIN
    
    @property
    def is_manager(self) -> bool:
        """Check if user is a manager."""
        return self.role == UserRole.MANAGER
    
    @property
    def is_admin(self) -> bool:
        """Check if user is an admin."""
        return self.role == UserRole.ADMIN
    
    @property
    def is_visitor(self) -> bool:
        """Check if user is a visitor."""
        return self.role == UserRole.VISITOR


# Index for efficient role-based queries
Index("idx_users_role", User.role)
Index("idx_users_email", User.email)
Index("idx_users_manager_id", User.manager_id)
