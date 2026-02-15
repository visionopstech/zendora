from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ManagerSettingsBase(BaseModel):
    """Base schema for manager settings."""
    logo_url: Optional[str] = None
    banner_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    custom_message: Optional[str] = None


class ManagerSettingsCreate(ManagerSettingsBase):
    """Schema for creating manager settings."""
    pass


class ManagerSettingsUpdate(BaseModel):
    """Schema for updating manager settings (all fields optional)."""
    logo_url: Optional[str] = None
    banner_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    custom_message: Optional[str] = None


class ManagerSettingsResponse(ManagerSettingsBase):
    """Schema for manager settings response."""
    id: UUID
    manager_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WishlistSettingsBase(BaseModel):
    """Base schema for wishlist settings."""
    banner_image_url: Optional[str] = None
    custom_message: Optional[str] = None


class WishlistSettingsCreate(WishlistSettingsBase):
    """Schema for creating wishlist settings."""
    pass


class WishlistSettingsUpdate(BaseModel):
    """Schema for updating wishlist settings (all fields optional)."""
    banner_image_url: Optional[str] = None
    custom_message: Optional[str] = None


class WishlistSettingsResponse(WishlistSettingsBase):
    """Schema for wishlist settings response."""
    id: UUID
    wishlist_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CombinedSettingsResponse(BaseModel):
    """Combined settings response with manager and wishlist settings."""
    manager: Optional[ManagerSettingsResponse] = None
    wishlist: Optional[WishlistSettingsResponse] = None

    class Config:
        from_attributes = True
