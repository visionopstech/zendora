from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import FuneralHomeRef, UserRef


class FamilyResponse(BaseModel):
    """A family admin enriched with funeral home and collection context."""

    id: UUID
    email: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    funeral_home: Optional[FuneralHomeRef] = None
    director: Optional[UserRef] = None
    gift_collection_count: int = 0
    published_collection_id: Optional[UUID] = None
    published_collection_slug: Optional[str] = None

    class Config:
        from_attributes = True
