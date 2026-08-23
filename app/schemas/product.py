from uuid import UUID
from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from datetime import datetime
from decimal import Decimal


class ProductImageInput(BaseModel):
    """A single image submitted for a gift gallery."""

    url: str = Field(..., min_length=1, max_length=1000)
    alt_text: Optional[str] = Field(None, max_length=255)
    is_primary: bool = False
    sort_order: int = Field(default=0, ge=0)


class ProductImageResponse(BaseModel):
    """A single image in a gift gallery."""

    id: UUID
    url: str
    alt_text: Optional[str] = None
    is_primary: bool
    sort_order: int

    class Config:
        from_attributes = True


class ReorderImagesRequest(BaseModel):
    """Schema for reordering a gift gallery. Images are ordered as listed."""

    image_ids: List[UUID] = Field(..., min_length=1)


class ProductBase(BaseModel):
    """Base gift schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    base_price: Decimal = Field(..., ge=0)
    price: Decimal = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_prices(self):
        if self.price < self.base_price:
            raise ValueError("price must be greater than or equal to base_price")
        return self


class ProductCreate(ProductBase):
    """Schema for creating a gift."""
    images: List[ProductImageInput] = Field(
        default_factory=list,
        description="Gallery images. Exactly one may be flagged is_primary; the first image is used otherwise.",
    )
    vendor_ids: Optional[List[UUID]] = Field(default_factory=list, description="Optional list of vendor IDs to associate with the product")


class ProductUpdate(BaseModel):
    """Schema for updating a gift."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    base_price: Optional[Decimal] = Field(None, ge=0)
    price: Optional[Decimal] = Field(None, gt=0)
    images: Optional[List[ProductImageInput]] = Field(
        None,
        description="When provided, replaces the whole gallery",
    )
    is_active: Optional[bool] = None
    vendor_ids: Optional[List[UUID]] = Field(None, description="Optional list of vendor IDs to associate with the product")

    @model_validator(mode="after")
    def validate_prices(self):
        if self.base_price is not None and self.price is not None and self.price < self.base_price:
            raise ValueError("price must be greater than or equal to base_price")
        return self


class ProductResponse(ProductBase):
    """Schema for gift response."""
    id: UUID
    is_active: bool
    created_at: datetime
    images: List[ProductImageResponse] = Field(default_factory=list)
    primary_image_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class ProductWithVendors(ProductResponse):
    """Gift response with vendor information."""
    vendor_ids: List[UUID] = Field(default_factory=list)


class AssociateVendorsRequest(BaseModel):
    """Schema for associating vendors with a gift."""
    vendor_ids: List[UUID]
