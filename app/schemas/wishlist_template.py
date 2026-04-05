from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.inspection import inspect as sa_inspect

from app.schemas.wishlist import DeliveryAddress


class WishlistTemplateProductInput(BaseModel):
    """Product input for a wishlist template."""

    product_id: UUID
    quantity: int = Field(default=1, ge=1)


class WishlistTemplateBase(BaseModel):
    """Base schema for reusable wishlist templates."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    wishlist_title: Optional[str] = Field(None, max_length=255)
    wishlist_description: Optional[str] = None
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    delivery_address: Optional[DeliveryAddress] = None
    is_active: bool = True


class WishlistTemplateCreate(WishlistTemplateBase):
    """Schema for creating a wishlist template."""

    products: List[WishlistTemplateProductInput] = Field(default_factory=list)


class WishlistTemplateUpdate(BaseModel):
    """Schema for updating a wishlist template."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    wishlist_title: Optional[str] = Field(None, max_length=255)
    wishlist_description: Optional[str] = None
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    delivery_address: Optional[DeliveryAddress] = None
    is_active: Optional[bool] = None
    products: Optional[List[WishlistTemplateProductInput]] = None


class TemplateProductResponse(BaseModel):
    """Product representation for wishlist template responses."""

    id: UUID
    name: str
    description: Optional[str]
    price: float
    images: List[str] = Field(default_factory=list)
    quantity: int

    @classmethod
    def from_template_product(cls, template_product):
        """Build a response object from a template association."""

        return cls(
            id=template_product.product.id,
            name=template_product.product.name,
            description=template_product.product.description,
            price=float(template_product.product.price),
            images=template_product.product.images if isinstance(template_product.product.images, list) else [],
            quantity=template_product.quantity,
        )

    class Config:
        from_attributes = True


class WishlistTemplateResponse(WishlistTemplateBase):
    """Wishlist template response schema."""

    id: UUID
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    products: List[TemplateProductResponse] = Field(default_factory=list)

    @field_validator("products", mode="before")
    @classmethod
    def transform_products(cls, value):
        """Transform template product associations into API-friendly objects."""

        if not value:
            return []

        if value and isinstance(value[0], (dict, TemplateProductResponse)):
            return value

        result = []
        for template_product in value:
            state = sa_inspect(template_product)
            if "product" not in state.unloaded and getattr(template_product, "product", None):
                result.append(TemplateProductResponse.from_template_product(template_product))

        return result

    class Config:
        from_attributes = True
