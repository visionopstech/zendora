from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class VendorBase(BaseModel):
    """Base vendor schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None


class VendorCreate(VendorBase):
    """Schema for creating a vendor."""
    pass


class VendorUpdate(BaseModel):
    """Schema for updating a vendor."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None
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
