from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import DeliveryAddress, UserRef


class FuneralHomeBase(BaseModel):
    """Shared funeral home fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[DeliveryAddress] = None
    logo_url: Optional[str] = None


class FuneralHomeCreate(FuneralHomeBase):
    """Schema for creating a funeral home (SUPER_ADMIN)."""

    director_id: Optional[UUID] = Field(
        None,
        description="Optionally assign a DIRECTOR user at creation time",
    )


class FuneralHomeUpdate(BaseModel):
    """Schema for updating a funeral home."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[DeliveryAddress] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None


class AssignDirectorRequest(BaseModel):
    """Schema for assigning a director to a funeral home."""

    user_id: UUID


class FuneralHomeResponse(FuneralHomeBase):
    """Funeral home response."""

    id: UUID
    director_id: Optional[UUID] = None
    director: Optional[UserRef] = None
    is_active: bool
    family_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
