from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime
from sqlalchemy.inspection import inspect as sa_inspect

from app.models.gift_collection import GiftCollectionStatus
from app.schemas.common import DeliveryAddress, FuneralHomeRef, UserRef
from app.schemas.product import ProductImageResponse
from app.schemas.settings import (
    CombinedSettingsResponse,
    DirectorSettingsResponse,
    GiftCollectionSettingsResponse,
)


class GiftCollectionCustomization(BaseModel):
    """Gift collection customization settings."""
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class GiftCollectionBase(BaseModel):
    """Base gift collection schema."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    delivery_address: Optional[DeliveryAddress] = None


class GiftCollectionProductInput(BaseModel):
    """Schema for gift input when creating/updating a collection."""
    product_id: UUID
    quantity: int = Field(default=1, ge=1)


class GiftCollectionCreate(GiftCollectionBase):
    """Schema for a director or super admin creating a collection for a family."""
    family_admin_email: str
    family_admin_full_name: str
    default_collection_id: Optional[UUID] = Field(
        None,
        description="Copy this default gift collection instead of starting from scratch",
    )
    products: Optional[List[GiftCollectionProductInput]] = Field(
        None,
        description="Optional list of gifts to add to the collection",
    )


class GiftCollectionCreateByFamilyAdmin(GiftCollectionBase):
    """Schema for a family admin creating their own collection."""
    default_collection_id: Optional[UUID] = Field(
        None,
        description="Copy an applicable default gift collection instead of starting from scratch",
    )
    products: Optional[List[GiftCollectionProductInput]] = Field(
        None,
        description="Optional list of gifts to add to the collection",
    )


class GiftCollectionUpdate(BaseModel):
    """Schema for updating a gift collection."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    delivery_address: Optional[DeliveryAddress] = None


class GiftInCollection(BaseModel):
    """A gift as it appears in a collection."""
    id: UUID
    name: str
    description: Optional[str]
    price: float
    images: List[ProductImageResponse] = Field(default_factory=list)
    primary_image_url: Optional[str] = None
    quantity: int
    
    @classmethod
    def from_collection_product(cls, association):
        """Create from a GiftCollectionProduct model."""
        product = association.product
        return cls(
            id=product.id,
            name=product.name,
            description=product.description,
            price=float(product.price),
            images=[ProductImageResponse.model_validate(image) for image in product.images],
            primary_image_url=product.primary_image_url,
            quantity=association.quantity
        )
    
    class Config:
        from_attributes = True


def _build_combined_settings(collection) -> CombinedSettingsResponse:
    """Collect director-level and collection-level settings without lazy loading."""

    director_settings = None
    collection_settings = None

    state = sa_inspect(collection)

    if 'director' not in state.unloaded and getattr(collection, 'director', None):
        director_state = sa_inspect(collection.director)
        if 'director_settings' not in director_state.unloaded and collection.director.director_settings:
            director_settings = DirectorSettingsResponse.model_validate(
                collection.director.director_settings
            )

    if 'settings' not in state.unloaded and getattr(collection, 'settings', None):
        collection_settings = GiftCollectionSettingsResponse.model_validate(collection.settings)

    return CombinedSettingsResponse(
        director=director_settings,
        gift_collection=collection_settings,
    )


class GiftCollectionResponse(GiftCollectionBase):
    """Schema for gift collection response."""
    id: UUID
    family_admin_id: UUID
    director_id: UUID
    funeral_home_id: Optional[UUID] = None
    source_default_collection_id: Optional[UUID] = None
    public_slug: str
    status: GiftCollectionStatus
    created_at: datetime
    published_at: Optional[datetime] = None
    qr_code_url: Optional[str] = None
    family_admin: Optional[UserRef] = None
    funeral_home: Optional[FuneralHomeRef] = None
    products: List[GiftInCollection] = Field(default_factory=list)
    settings: CombinedSettingsResponse = Field(
        default_factory=lambda: CombinedSettingsResponse(director=None, gift_collection=None)
    )
    
    @field_validator('products', mode='before')
    @classmethod
    def transform_products(cls, value):
        """Transform GiftCollectionProduct objects to GiftInCollection."""
        if not value:
            return []
        
        if value and isinstance(value[0], (dict, GiftInCollection)):
            return value
        
        result = []
        for association in value:
            state = sa_inspect(association)
            if 'product' not in state.unloaded and getattr(association, 'product', None):
                result.append(GiftInCollection.from_collection_product(association))
        return result
    
    @model_validator(mode='before')
    @classmethod
    def build_settings(cls, data):
        """Build combined settings from the gift collection model."""
        if isinstance(data, dict):
            return data
        
        if not hasattr(data, '__dict__'):
            return data
        
        try:
            state = sa_inspect(data)
        except Exception:
            result = {
                key: getattr(data, key)
                for key in data.__dict__
                if not key.startswith('_')
            }
            result['settings'] = CombinedSettingsResponse(director=None, gift_collection=None)
            if getattr(data, 'family_admin', None):
                result['family_admin'] = UserRef.model_validate(data.family_admin)
            if getattr(data, 'funeral_home', None):
                result['funeral_home'] = FuneralHomeRef.model_validate(data.funeral_home)
            return result
        
        result = {key: getattr(data, key) for key in data.__dict__ if not key.startswith('_')}
        result['settings'] = _build_combined_settings(data)
        
        if 'family_admin' not in state.unloaded and getattr(data, 'family_admin', None):
            result['family_admin'] = UserRef.model_validate(data.family_admin)
        if 'funeral_home' not in state.unloaded and getattr(data, 'funeral_home', None):
            result['funeral_home'] = FuneralHomeRef.model_validate(data.funeral_home)
        
        return result
    
    class Config:
        from_attributes = True


class GiftCollectionPublicResponse(BaseModel):
    """Public gift collection response (no sensitive data)."""
    id: UUID
    title: Optional[str]
    description: Optional[str]
    customization: GiftCollectionCustomization
    products: List[GiftInCollection]
    qr_code_url: Optional[str] = None
    settings: CombinedSettingsResponse = Field(
        default_factory=lambda: CombinedSettingsResponse(director=None, gift_collection=None)
    )


class AddGiftsRequest(BaseModel):
    """Schema for adding a gift to a collection."""
    product_id: UUID
    quantity: int = Field(default=1, ge=1)


class AddGiftsListRequest(BaseModel):
    """Schema for adding multiple gifts to a collection."""
    products: List[AddGiftsRequest]


class UpdateGiftCollectionProductsRequest(BaseModel):
    """Schema for replacing all gifts in a collection."""
    products: List[GiftCollectionProductInput]
