from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DirectorSettingsBase(BaseModel):
    """Base schema for director settings."""
    logo_url: Optional[str] = None
    banner_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    custom_message: Optional[str] = None


class DirectorSettingsCreate(DirectorSettingsBase):
    """Schema for creating director settings."""
    pass


class DirectorSettingsUpdate(BaseModel):
    """Schema for updating director settings (all fields optional)."""
    logo_url: Optional[str] = None
    banner_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    custom_message: Optional[str] = None


class DirectorSettingsResponse(DirectorSettingsBase):
    """Schema for director settings response."""
    id: UUID
    director_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GiftCollectionSettingsBase(BaseModel):
    """Base schema for gift collection settings."""
    banner_image_url: Optional[str] = None
    custom_message: Optional[str] = None


class GiftCollectionSettingsCreate(GiftCollectionSettingsBase):
    """Schema for creating gift collection settings."""
    pass


class GiftCollectionSettingsUpdate(BaseModel):
    """Schema for updating gift collection settings (all fields optional)."""
    banner_image_url: Optional[str] = None
    custom_message: Optional[str] = None


class GiftCollectionSettingsResponse(GiftCollectionSettingsBase):
    """Schema for gift collection settings response."""
    id: UUID
    gift_collection_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CombinedSettingsResponse(BaseModel):
    """Combined settings response with director and collection settings."""
    director: Optional[DirectorSettingsResponse] = None
    gift_collection: Optional[GiftCollectionSettingsResponse] = None

    class Config:
        from_attributes = True
