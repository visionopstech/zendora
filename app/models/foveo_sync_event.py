import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FoveoSyncEvent(Base):
    """Idempotency and audit record for a Foveo sync push."""

    __tablename__ = "foveo_sync_events"

    event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    foveo_stream_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)

    def __repr__(self) -> str:
        return f"<FoveoSyncEvent(event_id={self.event_id})>"
