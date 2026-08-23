from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.inspection import inspect as sa_inspect

from app.models.default_gift_collection import DefaultCollectionScope
from app.schemas.common import DeliveryAddress
from app.schemas.product import ProductImageResponse


class DefaultGiftCollectionProductInput(BaseModel):
    """Gift input for a default gift collection."""

    product_id: UUID
    quantity: int = Field(default=1, ge=1)


class DefaultGiftCollectionBase(BaseModel):
    """Base schema for reusable default gift collections."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    collection_title: Optional[str] = Field(None, max_length=255)
    collection_description: Optional[str] = None
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    delivery_address: Optional[DeliveryAddress] = None
    is_active: bool = True


class DefaultGiftCollectionCreate(DefaultGiftCollectionBase):
    """Schema for creating a default gift collection.

    The owner scope is derived from the caller: a super admin always creates
    ZENDORA defaults, a director always creates FUNERAL_HOME defaults for their
    own funeral home.
    """

    products: List[DefaultGiftCollectionProductInput] = Field(default_factory=list)


class DefaultGiftCollectionUpdate(BaseModel):
    """Schema for updating a default gift collection."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    collection_title: Optional[str] = Field(None, max_length=255)
    collection_description: Optional[str] = None
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    delivery_address: Optional[DeliveryAddress] = None
    is_active: Optional[bool] = None
    products: Optional[List[DefaultGiftCollectionProductInput]] = None


class DefaultCollectionProductResponse(BaseModel):
    """Gift representation for default gift collection responses."""

    id: UUID
    name: str
    description: Optional[str]
    price: float
    images: List[ProductImageResponse] = Field(default_factory=list)
    primary_image_url: Optional[str] = None
    quantity: int

    @classmethod
    def from_association(cls, association):
        """Build a response object from a default collection association."""

        product = association.product
        return cls(
            id=product.id,
            name=product.name,
            description=product.description,
            price=float(product.price),
            images=[ProductImageResponse.model_validate(image) for image in product.images],
            primary_image_url=product.primary_image_url,
            quantity=association.quantity,
        )

    class Config:
        from_attributes = True


class DefaultGiftCollectionResponse(DefaultGiftCollectionBase):
    """Default gift collection response schema."""

    id: UUID
    owner_scope: DefaultCollectionScope
    funeral_home_id: Optional[UUID] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    products: List[DefaultCollectionProductResponse] = Field(default_factory=list)

    @field_validator("products", mode="before")
    @classmethod
    def transform_products(cls, value):
        """Transform default collection associations into API-friendly objects."""

        if not value:
            return []

        if value and isinstance(value[0], (dict, DefaultCollectionProductResponse)):
            return value

        result = []
        for association in value:
            state = sa_inspect(association)
            if "product" not in state.unloaded and getattr(association, "product", None):
                result.append(DefaultCollectionProductResponse.from_association(association))

        return result

    class Config:
        from_attributes = True
