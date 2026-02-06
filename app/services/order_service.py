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
            status=OrderStatus.PENDING.value,
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
        
        order.status = OrderStatus.PAID.value
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
        
        order.status = OrderStatus.FAILED.value
        
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
    
    async def get_all(
        self,
        status: Optional[OrderStatus] = None
    ) -> List[Order]:
        """Get all orders, optionally filtered by status."""
        query = select(Order)
        
        if status:
            query = query.where(Order.status == status.value)
        
        query = query.order_by(Order.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_admin_orders(
        self,
        admin_id: UUID
    ) -> List[Order]:
        """Get all orders for an admin's wishlists."""
        result = await self.db.execute(
            select(Order)
            .where(Order.admin_id == admin_id)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_manager_orders(
        self,
        manager_id: UUID
    ) -> List[Order]:
        """Get all orders for wishlists managed by a manager."""
        result = await self.db.execute(
            select(Order)
            .join(Wishlist, Order.wishlist_id == Wishlist.id)
            .where(Wishlist.manager_id == manager_id)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def update(
        self,
        order_id: UUID,
        status: Optional[OrderStatus] = None,
        total_amount: Optional[Decimal] = None,
        paid_at: Optional[datetime] = None
    ) -> Order:
        """Update order details."""
        order = await self.get_by_id(order_id)
        
        if not order:
            raise NotFoundException("Order not found")
        
        if status is not None:
            order.status = status.value if isinstance(status, OrderStatus) else status
            
            # Auto-set paid_at when marking as paid
            if status == OrderStatus.PAID and not order.paid_at:
                order.paid_at = datetime.utcnow()
        
        if total_amount is not None:
            order.total_amount = total_amount
        
        if paid_at is not None:
            order.paid_at = paid_at
        
        await self.db.flush()
        await self.db.refresh(order)
        
        return order
    
    async def delete(self, order_id: UUID) -> None:
        """Delete an order."""
        order = await self.get_by_id(order_id)
        
        if not order:
            raise NotFoundException("Order not found")
        
        await self.db.delete(order)
        await self.db.flush()
