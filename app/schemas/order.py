from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.models.order import OrderStatus
from app.schemas.common import FuneralHomeRef, GiftCollectionRef, UserRef


class CheckoutRequest(BaseModel):
    """Schema for initiating a checkout."""
    visitor_first_name: str = Field(..., min_length=1)
    visitor_last_name: str = Field(..., min_length=1)
    visitor_email: EmailStr
    product_ids: List[UUID] = Field(..., min_length=1)


class CheckoutResponse(BaseModel):
    """Schema for checkout response."""
    order_id: UUID
    checkout_url: str
    total_amount: Decimal


class OrderProductResponse(BaseModel):
    """Gift in an order."""
    product_id: UUID
    product_name: str
    product_price: Decimal
    quantity: int


class OrderResponse(BaseModel):
    """Schema for order response."""
    id: UUID
    visitor_id: UUID
    gift_collection_id: UUID
    family_admin_id: UUID
    funeral_home_id: Optional[UUID] = None
    status: OrderStatus
    total_amount: Decimal
    currency: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    products: List[OrderProductResponse] = Field(default_factory=list)
    # Enriched context, populated on list and detail endpoints
    visitor: Optional[UserRef] = None
    family_admin: Optional[UserRef] = None
    funeral_home: Optional[FuneralHomeRef] = None
    gift_collection: Optional[GiftCollectionRef] = None
    # Vendor-specific: gifts from their vendor and total for those gifts
    vendor_products: Optional[List[OrderProductResponse]] = None
    vendor_sales_amount: Optional[Decimal] = None
    
    class Config:
        from_attributes = True


class OrderUpdate(BaseModel):
    """Schema for updating an order."""
    status: Optional[OrderStatus] = None
    total_amount: Optional[Decimal] = Field(None, gt=0)
    paid_at: Optional[datetime] = None


class OrderStatusEmailRequest(BaseModel):
    """Optional note included in a manually sent order status email."""
    note: Optional[str] = Field(None, max_length=2000)


class OrderStatusEmailRecipient(BaseModel):
    """One attempted recipient of a status email."""
    audience: str
    email: str
    sent: bool


class OrderStatusEmailResponse(BaseModel):
    """Result of a manual order status email send."""
    order_id: UUID
    status: OrderStatus
    sent_count: int
    recipients: List[OrderStatusEmailRecipient] = Field(default_factory=list)
