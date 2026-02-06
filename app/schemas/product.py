from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class ProductBase(BaseModel):
    """Base product schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: Decimal = Field(..., gt=0)
    images: Optional[List[str]] = Field(default_factory=list)


class ProductCreate(ProductBase):
    """Schema for creating a product."""
    vendor_ids: Optional[List[UUID]] = Field(default_factory=list, description="Optional list of vendor IDs to associate with the product")


class ProductUpdate(BaseModel):
    """Schema for updating a product."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0)
    images: Optional[List[str]] = None
    is_active: Optional[bool] = None
    vendor_ids: Optional[List[UUID]] = Field(None, description="Optional list of vendor IDs to associate with the product")


class ProductResponse(ProductBase):
    """Schema for product response."""
    id: UUID
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProductWithVendors(ProductResponse):
    """Product response with vendor information."""
    vendor_ids: List[UUID] = Field(default_factory=list)


class AssociateVendorsRequest(BaseModel):
    """Schema for associating vendors with a product."""
    vendor_ids: List[UUID]
