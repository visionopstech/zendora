from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    role: UserRole
    manager_id: Optional[UUID] = None


class UserRegister(BaseModel):
    """Schema for user registration."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserResponse(UserBase):
    """Schema for user response."""
    id: UUID
    role: UserRole
    is_active: bool
    manager_id: Optional[UUID] = None
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
    manager_id: Optional[UUID] = None
    password: Optional[str] = Field(None, min_length=8, description="New password (optional)")
