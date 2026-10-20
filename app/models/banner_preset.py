import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BannerPresetScope(str, enum.Enum):
    """Who owns a default banner."""

    ZENDORA = "ZENDORA"
    FUNERAL_HOME = "FUNERAL_HOME"


class BannerPreset(Base):
    """A reusable collection banner owned by Zendora or a funeral home."""

    __tablename__ = "banner_presets"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    owner_scope: Mapped[str] = mapped_column(
        String(50),
        default=BannerPresetScope.ZENDORA.value,
        nullable=False,
        index=True,
    )
    funeral_home_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("funeral_homes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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

    funeral_home: Mapped[Optional["FuneralHome"]] = relationship(
        "FuneralHome",
        back_populates="banner_presets",
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_banner_presets",
    )

    @property
    def is_zendora_banner(self) -> bool:
        return self.owner_scope == BannerPresetScope.ZENDORA.value

    def __repr__(self) -> str:
        return (
            f"<BannerPreset(id={self.id}, name={self.name}, "
            f"owner_scope={self.owner_scope}, is_active={self.is_active})>"
        )


Index("idx_banner_presets_name", BannerPreset.name)
Index("idx_banner_presets_sort_order", BannerPreset.sort_order)
