from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.wishlist import WishlistStatus


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
    products: Optional[List[WishlistProductInput]] = Field(default_factory=list, description="Optional list of products to add to the wishlist")


class WishlistCreateByAdmin(WishlistBase):
    """Schema for admin creating their own wishlist."""
    products: Optional[List[WishlistProductInput]] = Field(default_factory=list, description="Optional list of products to add to the wishlist")


class WishlistUpdate(BaseModel):
    """Schema for updating a wishlist."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    logo_url: Optional[str] = None
    header_image_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    secondary_color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    delivery_address: Optional[DeliveryAddress] = None


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
    
    class Config:
        from_attributes = True


class ProductInWishlist(BaseModel):
    """Product as it appears in a wishlist."""
    id: UUID
    name: str
    description: Optional[str]
    price: float
    images: List[str]
    quantity: int
    
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
