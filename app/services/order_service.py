from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

from app.models.order import Order, OrderProduct, OrderStatus
from app.models.product import Product
from app.models.wishlist import Wishlist
from app.core.exceptions import NotFoundException


class OrderService:
    """Service for order-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(
        self,
        order_id: UUID,
        load_products: bool = False
    ) -> Optional[Order]:
        """Get order by ID."""
        query = select(Order).where(Order.id == order_id)
        
        if load_products:
            query = query.options(selectinload(Order.products))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_stripe_session_id(
        self,
        stripe_session_id: str
    ) -> Optional[Order]:
        """Get order by Stripe session ID."""
        result = await self.db.execute(
            select(Order).where(Order.stripe_session_id == stripe_session_id)
        )
        return result.scalar_one_or_none()
    
    async def create_order(
        self,
        visitor_id: UUID,
        wishlist_id: UUID,
        admin_id: UUID,
        stripe_session_id: str,
        products: List[Product],
        quantities: dict[UUID, int]
    ) -> Order:
        """
        Create a new order with products.
        
        Args:
            visitor_id: ID of the visitor placing the order
            wishlist_id: ID of the wishlist
            admin_id: ID of the admin (denormalized for reporting)
            stripe_session_id: Stripe checkout session ID
            products: List of Product objects
            quantities: Dict mapping product_id to quantity
            
        Returns:
            Order: Created order
        """
        # Calculate total amount
        total_amount = sum(
            product.price * quantities.get(product.id, 1)
            for product in products
        )
        
        # Create order
        order = Order(
            visitor_id=visitor_id,
            wishlist_id=wishlist_id,
            admin_id=admin_id,
            stripe_session_id=stripe_session_id,
            status=OrderStatus.PENDING,
            total_amount=total_amount,
            currency="USD"
        )
        
        self.db.add(order)
        await self.db.flush()
        
        # Add order products with snapshots
        for product in products:
            quantity = quantities.get(product.id, 1)
            order_product = OrderProduct(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                product_price=product.price,
                quantity=quantity
            )
            self.db.add(order_product)
        
        await self.db.flush()
        await self.db.refresh(order)
        
        return order
    
    async def mark_as_paid(
        self,
        order_id: UUID
    ) -> Order:
        """Mark an order as paid."""
        order = await self.get_by_id(order_id)
        
        if not order:
            raise NotFoundException("Order not found")
        
        order.status = OrderStatus.PAID
        order.paid_at = datetime.utcnow()
        
        await self.db.flush()
        await self.db.refresh(order)
        
        return order
    
    async def mark_as_failed(
        self,
        order_id: UUID
    ) -> Order:
        """Mark an order as failed."""
        order = await self.get_by_id(order_id)
        
        if not order:
            raise NotFoundException("Order not found")
        
        order.status = OrderStatus.FAILED
        
        await self.db.flush()
        await self.db.refresh(order)
        
        return order
    
    async def get_visitor_orders(
        self,
        visitor_id: UUID
    ) -> List[Order]:
        """Get all orders for a visitor."""
        result = await self.db.execute(
            select(Order)
            .where(Order.visitor_id == visitor_id)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_wishlist_orders(
        self,
        wishlist_id: UUID
    ) -> List[Order]:
        """Get all orders for a wishlist."""
        result = await self.db.execute(
            select(Order)
            .where(Order.wishlist_id == wishlist_id)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
