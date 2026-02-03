from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.models.order import OrderStatus


class CheckoutRequest(BaseModel):
    """Schema for initiating a checkout."""
    visitor_name: str = Field(..., min_length=1)
    visitor_email: EmailStr
    product_ids: List[UUID] = Field(..., min_items=1)


class CheckoutResponse(BaseModel):
    """Schema for checkout response."""
    order_id: UUID
    checkout_url: str
    total_amount: Decimal


class OrderProductResponse(BaseModel):
    """Product in an order."""
    product_id: UUID
    product_name: str
    product_price: Decimal
    quantity: int


class OrderResponse(BaseModel):
    """Schema for order response."""
    id: UUID
    visitor_id: UUID
    wishlist_id: UUID
    admin_id: UUID
    status: OrderStatus
    total_amount: Decimal
    currency: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    products: List[OrderProductResponse] = Field(default_factory=list)
    
    class Config:
        from_attributes = True
