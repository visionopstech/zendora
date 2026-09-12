import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index, inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, List

from app.core.database import Base


class UserRole(str, enum.Enum):
    """User role enumeration."""
    SUPER_ADMIN = "SUPER_ADMIN"
    DIRECTOR = "DIRECTOR"
    FAMILY_ADMIN = "FAMILY_ADMIN"
    VISITOR = "VISITOR"
    VENDOR = "VENDOR"


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
    role: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Director relationship (for FAMILY_ADMIN users only)
    director_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Funeral home the user belongs to (DIRECTOR and FAMILY_ADMIN users)
    funeral_home_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("funeral_homes.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    # Vendor relationship (for VENDOR users only)
    vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("vendors.id", ondelete="SET NULL"),
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
    director: Mapped[Optional["User"]] = relationship(
        "User",
        remote_side=[id],
        foreign_keys=[director_id],
        back_populates="family_admins"
    )
    
    family_admins: Mapped[List["User"]] = relationship(
        "User",
        back_populates="director",
        foreign_keys=[director_id]
    )
    
    # Funeral home this user belongs to
    funeral_home: Mapped[Optional["FuneralHome"]] = relationship(
        "FuneralHome",
        back_populates="members",
        foreign_keys=[funeral_home_id]
    )
    
    # Funeral home this user is the director of (DIRECTOR users)
    directed_funeral_home: Mapped[Optional["FuneralHome"]] = relationship(
        "FuneralHome",
        back_populates="director",
        foreign_keys="FuneralHome.director_id",
        uselist=False
    )
    
    # Vendor relationship (for VENDOR users only)
    vendor: Mapped[Optional["Vendor"]] = relationship(
        "Vendor",
        back_populates="vendor_users",
        foreign_keys=[vendor_id]
    )
    
    # Gift collections overseen by this user (if DIRECTOR)
    directed_gift_collections: Mapped[List["GiftCollection"]] = relationship(
        "GiftCollection",
        foreign_keys="GiftCollection.director_id",
        back_populates="director",
        # Avoid ORM SET NULL on NOT NULL FKs; the DB already ON DELETE CASCADEs.
        passive_deletes=True,
    )
    
    # Gift collections owned by this user (if FAMILY_ADMIN)
    owned_gift_collections: Mapped[List["GiftCollection"]] = relationship(
        "GiftCollection",
        foreign_keys="GiftCollection.family_admin_id",
        back_populates="family_admin",
        passive_deletes=True,
    )
    
    # Orders placed by this user (if VISITOR)
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        foreign_keys="Order.visitor_id",
        back_populates="visitor",
        passive_deletes=True,
    )
    
    # Director settings (if DIRECTOR)
    director_settings: Mapped[Optional["DirectorSettings"]] = relationship(
        "DirectorSettings",
        back_populates="director",
        uselist=False,
        cascade="all, delete-orphan"
    )

    director_commission: Mapped[Optional["DirectorCommission"]] = relationship(
        "DirectorCommission",
        back_populates="director",
        uselist=False,
        cascade="all, delete-orphan"
    )

    wallet: Mapped[Optional["Wallet"]] = relationship(
        "Wallet",
        back_populates="director",
        uselist=False,
        passive_deletes=True,
    )

    order_commissions: Mapped[List["OrderCommission"]] = relationship(
        "OrderCommission",
        back_populates="director",
        passive_deletes=True,
    )

    created_default_gift_collections: Mapped[List["DefaultGiftCollection"]] = relationship(
        "DefaultGiftCollection",
        foreign_keys="DefaultGiftCollection.created_by",
        back_populates="creator"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
    
    @property
    def is_super_admin(self) -> bool:
        """Check if user is a super admin."""
        return self.role == UserRole.SUPER_ADMIN.value
    
    @property
    def is_director(self) -> bool:
        """Check if user is a funeral home director."""
        return self.role == UserRole.DIRECTOR.value
    
    @property
    def is_family_admin(self) -> bool:
        """Check if user is a family admin."""
        return self.role == UserRole.FAMILY_ADMIN.value
    
    @property
    def is_visitor(self) -> bool:
        """Check if user is a visitor."""
        return self.role == UserRole.VISITOR.value
    
    @property
    def is_vendor(self) -> bool:
        """Check if user is a vendor."""
        return self.role == UserRole.VENDOR.value

    @property
    def profit_percentage(self) -> Optional[Decimal]:
        """Expose commission config on API responses when already loaded."""
        state = inspect(self)
        if "director_commission" in state.unloaded:
            return None
        if not self.director_commission:
            return None
        return self.director_commission.profit_percentage


# Index for efficient role-based queries
Index("idx_users_role", User.role)
Index("idx_users_email", User.email)
Index("idx_users_director_id", User.director_id)
Index("idx_users_funeral_home_id", User.funeral_home_id)
Index("idx_users_vendor_id", User.vendor_id)
