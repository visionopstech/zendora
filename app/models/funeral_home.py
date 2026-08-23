import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FuneralHome(Base):
    """A funeral home acts as the workspace that scopes directors and families."""

    __tablename__ = "funeral_homes"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # A funeral home has at most one director.
    director_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

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

    director: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="directed_funeral_home",
        foreign_keys=[director_id],
    )

    members: Mapped[List["User"]] = relationship(
        "User",
        back_populates="funeral_home",
        foreign_keys="User.funeral_home_id",
    )

    default_gift_collections: Mapped[List["DefaultGiftCollection"]] = relationship(
        "DefaultGiftCollection",
        back_populates="funeral_home",
    )

    gift_collections: Mapped[List["GiftCollection"]] = relationship(
        "GiftCollection",
        back_populates="funeral_home",
    )

    def __repr__(self) -> str:
        return f"<FuneralHome(id={self.id}, name={self.name}, director_id={self.director_id})>"


Index("idx_funeral_homes_name", FuneralHome.name)
Index("idx_funeral_homes_is_active", FuneralHome.is_active)
