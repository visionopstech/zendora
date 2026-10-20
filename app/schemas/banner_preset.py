from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.banner_preset import BannerPresetScope


class BannerPresetCreate(BaseModel):
    """Create a default banner. Scope is forced from the caller."""

    name: str = Field(..., min_length=1, max_length=255)
    image_url: str = Field(..., min_length=1, max_length=500)
    sort_order: int = 0
    is_active: bool = True


class BannerPresetUpdate(BaseModel):
    """Update a default banner. All fields optional."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    image_url: Optional[str] = Field(None, min_length=1, max_length=500)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class BannerPresetResponse(BaseModel):
    """Default banner returned to the API."""

    id: UUID
    name: str
    image_url: str
    owner_scope: BannerPresetScope
    funeral_home_id: Optional[UUID] = None
    created_by: Optional[UUID] = None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    can_edit: bool = False

    class Config:
        from_attributes = True
