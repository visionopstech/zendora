from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import DeliveryAddress, FuneralHomeRef, UserRef


class FamilyCreate(BaseModel):
    """Schema for a director creating a family admin account."""

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    deceased_first_name: str = Field(..., min_length=1, max_length=255)
    deceased_last_name: str = Field(..., min_length=1, max_length=255)
    address: DeliveryAddress


class FamilyUpdate(BaseModel):
    """Schema for a partial family admin update."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=255)
    last_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    deceased_first_name: Optional[str] = Field(None, min_length=1, max_length=255)
    deceased_last_name: Optional[str] = Field(None, min_length=1, max_length=255)
    address: Optional[DeliveryAddress] = None
    is_active: Optional[bool] = None


class FamilyResponse(BaseModel):
    """A family admin enriched with funeral home and collection context."""

    id: UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    deceased_first_name: Optional[str] = None
    deceased_last_name: Optional[str] = None
    address: Optional[DeliveryAddress] = None
    is_active: bool
    created_at: datetime
    funeral_home: Optional[FuneralHomeRef] = None
    director: Optional[UserRef] = None
    gift_collection_count: int = 0
    published_collection_id: Optional[UUID] = None
    published_collection_slug: Optional[str] = None

    class Config:
        from_attributes = True
