import enum
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime

from app.models.user import UserRole


class RegistrableRole(str, enum.Enum):
    """Roles a visitor may pick when self-registering. SUPER_ADMIN is excluded."""

    DIRECTOR = UserRole.DIRECTOR.value
    FAMILY_ADMIN = UserRole.FAMILY_ADMIN.value
    VISITOR = UserRole.VISITOR.value
    VENDOR = UserRole.VENDOR.value


class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    role: UserRole
    director_id: Optional[UUID] = None
    funeral_home_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    profit_percentage: Optional[Decimal] = Field(None, ge=0, le=100)


class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: Optional[str] = None
    role: RegistrableRole = Field(
        default=RegistrableRole.VISITOR,
        description="Role to register as. SUPER_ADMIN cannot be self-assigned.",
    )


class RegistrableRoleOption(BaseModel):
    """A role the signup form may offer."""

    value: RegistrableRole
    label: str
    description: str


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(UserBase):
    """Schema for user response."""
    id: UUID
    role: UserRole
    is_active: bool
    director_id: Optional[UUID] = None
    funeral_home_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    profit_percentage: Optional[Decimal] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MagicLinkRequest(BaseModel):
    """Schema for requesting a magic link."""
    email: EmailStr


class MagicLinkVerify(BaseModel):
    """Schema for verifying a magic link token."""
    token: str


class ThirdPartyLoginRequest(BaseModel):
    """Schema for third-party redirect login."""
    token: str
    

class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class ProfileUpdate(BaseModel):
    """Schema for authenticated user to update their own profile. Only full_name is updatable via this endpoint."""
    full_name: Optional[str] = None


class UserManagementUpdate(BaseModel):
    """Schema for updating user (management operations)."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    director_id: Optional[UUID] = None
    funeral_home_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    profit_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    password: Optional[str] = Field(None, min_length=8, description="New password (optional)")
