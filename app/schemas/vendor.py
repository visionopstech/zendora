from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class VendorBase(BaseModel):
    """Base vendor schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    standard_processing_time: int = Field(0, ge=0)


class VendorCreate(VendorBase):
    """Schema for creating a vendor and its login user."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    standard_processing_time: int = Field(..., ge=0)


class VendorUpdate(BaseModel):
    """Schema for updating a vendor."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    standard_processing_time: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class VendorResponse(VendorBase):
    """Schema for vendor response."""
    id: UUID
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class VendorDashboardStats(BaseModel):
    """Schema for vendor dashboard statistics."""
    product_count: int
    total_sales_amount: Decimal
    order_count: int
