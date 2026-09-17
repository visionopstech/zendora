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
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    role: UserRole
    director_id: Optional[UUID] = None
    funeral_home_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    deceased_first_name: Optional[str] = Field(None, min_length=1, max_length=255)
    deceased_last_name: Optional[str] = Field(None, min_length=1, max_length=255)
    profit_percentage: Optional[Decimal] = Field(None, ge=0, le=100)


class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
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
    deceased_first_name: Optional[str] = None
    deceased_last_name: Optional[str] = None
    profit_percentage: Optional[Decimal] = None
    is_main_director: bool = False
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
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None


class ProfileUpdate(BaseModel):
    """Schema for authenticated user to update their own profile."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserManagementUpdate(BaseModel):
    """Schema for updating user (management operations)."""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    director_id: Optional[UUID] = None
    funeral_home_id: Optional[UUID] = None
    vendor_id: Optional[UUID] = None
    deceased_first_name: Optional[str] = Field(None, min_length=1, max_length=255)
    deceased_last_name: Optional[str] = Field(None, min_length=1, max_length=255)
    profit_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    password: Optional[str] = Field(None, min_length=8, description="New password (optional)")


class DirectorStatusUpdate(BaseModel):
    """Schema for toggling a director's active status."""
    is_active: bool


class DirectorStatisticsResponse(BaseModel):
    """Director dashboard statistics, scoped by main vs other director."""

    total_gift_collections: int
    total_families_enrolled: int
    orders_count: int
    sales: Decimal
    total_commissions: Decimal
