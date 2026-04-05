from uuid import UUID
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.inspection import inspect as sa_inspect

from app.models.wishlist import WishlistStatus
from app.schemas.settings import CombinedSettingsResponse, ManagerSettingsResponse, WishlistSettingsResponse


class DeliveryAddress(BaseModel):
    """Delivery address schema."""
    street: str
    city: str
    state: str
    zip_code: str
    country: str = "USA"
    additional_info: Optional[str] = None


class WishlistCustomization(BaseModel):
    """Wishlist customization settings."""
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class WishlistBase(BaseModel):
    """Base wishlist schema."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    delivery_address: Optional[DeliveryAddress] = None


class WishlistProductInput(BaseModel):
    """Schema for product input when creating/updating wishlist."""
    product_id: UUID
    quantity: int = Field(default=1, ge=1)


class WishlistCreate(WishlistBase):
    """Schema for creating a wishlist."""
    admin_email: str  # For manager to assign admin
    admin_full_name: str
    template_id: Optional[UUID] = None
    products: Optional[List[WishlistProductInput]] = Field(
        None,
        description="Optional list of products to add to the wishlist",
    )


class WishlistCreateByAdmin(WishlistBase):
    """Schema for admin creating their own wishlist."""
    template_id: Optional[UUID] = None
    products: Optional[List[WishlistProductInput]] = Field(
        None,
        description="Optional list of products to add to the wishlist",
    )


class WishlistUpdate(BaseModel):
    """Schema for updating a wishlist."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    delivery_address: Optional[DeliveryAddress] = None


class ProductInWishlist(BaseModel):
    """Product as it appears in a wishlist."""
    id: UUID
    name: str
    description: Optional[str]
    price: float
    images: List[str] = Field(default_factory=list)
    quantity: int
    
    @classmethod
    def from_wishlist_product(cls, wp):
        """Create from WishlistProduct model."""
        return cls(
            id=wp.product.id,
            name=wp.product.name,
            description=wp.product.description,
            price=float(wp.product.price),
            images=wp.product.images if isinstance(wp.product.images, list) else [],
            quantity=wp.quantity
        )
    
    class Config:
        from_attributes = True


class WishlistResponse(WishlistBase):
    """Schema for wishlist response."""
    id: UUID
    admin_id: UUID
    manager_id: UUID
    public_slug: str
    status: WishlistStatus
    created_at: datetime
    published_at: Optional[datetime] = None
    qr_code_url: Optional[str] = None
    products: List[ProductInWishlist] = Field(default_factory=list)
    settings: CombinedSettingsResponse = Field(default_factory=lambda: CombinedSettingsResponse(manager=None, wishlist=None))
    
    @field_validator('products', mode='before')
    @classmethod
    def transform_products(cls, v):
        """Transform WishlistProduct objects to ProductInWishlist."""
        if not v:
            return []
        
        # If it's already a list of dicts or ProductInWishlist, return as is
        if v and isinstance(v[0], (dict, ProductInWishlist)):
            return v
        
        # Transform from WishlistProduct models
        result = []
        for wp in v:
            # Check if product relationship is loaded to avoid lazy loading
            state = sa_inspect(wp)
            if 'product' not in state.unloaded:
                if hasattr(wp, 'product') and wp.product:
                    result.append(ProductInWishlist.from_wishlist_product(wp))
        return result
    
    @model_validator(mode='before')
    @classmethod
    def build_settings(cls, data):
        """Build combined settings from the wishlist model."""
        # If data is a dict (already validated), return as is
        if isinstance(data, dict):
            return data
        
        # data is a Wishlist model instance
        manager_settings = None
        wishlist_settings = None
        
        # Check if relationships are loaded to avoid lazy loading
        if hasattr(data, '__dict__'):
            # Use SQLAlchemy inspect to check if relationship is loaded
            state = sa_inspect(data)
            
            # Check if manager relationship is loaded
            if 'manager' not in state.unloaded:
                if hasattr(data, 'manager') and data.manager:
                    # Check if manager_settings is loaded on the manager
                    manager_state = sa_inspect(data.manager)
                    if 'manager_settings' not in manager_state.unloaded:
                        if hasattr(data.manager, 'manager_settings') and data.manager.manager_settings:
                            manager_settings = ManagerSettingsResponse.model_validate(data.manager.manager_settings)
            
            # Check if settings relationship is loaded
            if 'settings' not in state.unloaded:
                if hasattr(data, 'settings') and data.settings:
                    wishlist_settings = WishlistSettingsResponse.model_validate(data.settings)
            
            # Convert model to dict and add settings
            result = {key: getattr(data, key) for key in data.__dict__ if not key.startswith('_')}
            result['settings'] = CombinedSettingsResponse(
                manager=manager_settings,
                wishlist=wishlist_settings
            )
            return result
        
        return data
    
    class Config:
        from_attributes = True


class WishlistPublicResponse(BaseModel):
    """Public wishlist response (no sensitive data)."""
    id: UUID
    title: Optional[str]
    description: Optional[str]
    customization: WishlistCustomization
    products: List[ProductInWishlist]
    qr_code_url: Optional[str] = None
    settings: CombinedSettingsResponse = Field(default_factory=lambda: CombinedSettingsResponse(manager=None, wishlist=None))
    
    @model_validator(mode='before')
    @classmethod
    def build_settings(cls, data):
        """Build combined settings from the wishlist model."""
        # If data is a dict (already validated), return as is
        if isinstance(data, dict):
            return data
        
        # data is a Wishlist model instance
        manager_settings = None
        wishlist_settings = None
        
        # Check if relationships are loaded to avoid lazy loading
        if hasattr(data, '__dict__'):
            # Use SQLAlchemy inspect to check if relationship is loaded
            state = sa_inspect(data)
            
            # Check if manager relationship is loaded
            if 'manager' not in state.unloaded:
                if hasattr(data, 'manager') and data.manager:
                    # Check if manager_settings is loaded on the manager
                    manager_state = sa_inspect(data.manager)
                    if 'manager_settings' not in manager_state.unloaded:
                        if hasattr(data.manager, 'manager_settings') and data.manager.manager_settings:
                            manager_settings = ManagerSettingsResponse.model_validate(data.manager.manager_settings)
            
            # Check if settings relationship is loaded
            if 'settings' not in state.unloaded:
                if hasattr(data, 'settings') and data.settings:
                    wishlist_settings = WishlistSettingsResponse.model_validate(data.settings)
            
            # Convert model to dict and add settings
            result = {key: getattr(data, key) for key in data.__dict__ if not key.startswith('_')}
            result['settings'] = CombinedSettingsResponse(
                manager=manager_settings,
                wishlist=wishlist_settings
            )
            return result
        
        return data


class AddProductsRequest(BaseModel):
    """Schema for adding products to a wishlist."""
    product_id: UUID
    quantity: int = Field(default=1, ge=1)


class AddProductsListRequest(BaseModel):
    """Schema for adding multiple products to a wishlist."""
    products: List[AddProductsRequest]


class UpdateWishlistProductsRequest(BaseModel):
    """Schema for updating products in a wishlist (replaces all products)."""
    products: List[WishlistProductInput]
