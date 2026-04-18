from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

from app.models.order import Order, OrderProduct, OrderStatus
from app.models.product import Product, ProductVendor
from app.models.wishlist import Wishlist
from app.core.exceptions import NotFoundException
from app.services.financial_service import FinancialService


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
        wishlist = await self.db.get(Wishlist, wishlist_id)
        if not wishlist:
            raise NotFoundException("Wishlist not found")

        financial_service = FinancialService(self.db)
        commission_data = await financial_service.calculate_order_commission(
            products=products,
            quantities=quantities,
            manager_profit_percentage=await financial_service.get_manager_profit_percentage(wishlist.manager_id),
        )
        
        # Create order
        order = Order(
            visitor_id=visitor_id,
            wishlist_id=wishlist_id,
            admin_id=admin_id,
            stripe_session_id=stripe_session_id,
            status=OrderStatus.PENDING.value,
            total_amount=commission_data["final_amount"],
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

        await financial_service.create_order_commission_snapshot(
            order_id=order.id,
            manager_id=wishlist.manager_id,
            products=products,
            quantities=quantities,
        )
        
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
    
    async def get_vendor_orders(
        self,
        vendor_id: UUID,
        status: Optional[OrderStatus] = None
    ) -> List[Order]:
        """Get orders that contain at least one product from the vendor."""
        # Subquery: product_ids that belong to this vendor
        vendor_product_ids = (
            select(ProductVendor.product_id)
            .where(ProductVendor.vendor_id == vendor_id)
        )
        # Orders that have order_products with those product_ids
        query = (
            select(Order)
            .join(OrderProduct, Order.id == OrderProduct.order_id)
            .where(OrderProduct.product_id.in_(vendor_product_ids))
            .order_by(Order.created_at.desc())
            .distinct()
        )
        if status:
            query = query.where(Order.status == status.value)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_vendor_order_stats(
        self,
        vendor_id: UUID
    ) -> tuple[int, Decimal]:
        """
        Get vendor sales stats: (product_count, total_sales_amount).
        product_count: number of distinct products from this vendor
        total_sales_amount: sum of (price * quantity) for vendor's products in PAID orders
        """
        from sqlalchemy import func
        
        # Product count: distinct products associated with vendor
        product_count_result = await self.db.execute(
            select(func.count(ProductVendor.product_id))
            .where(ProductVendor.vendor_id == vendor_id)
        )
        product_count = product_count_result.scalar() or 0
        
        # Total sales: sum of (product_price * quantity) for order_products where
        # product belongs to vendor and order is PAID
        vendor_product_ids = (
            select(ProductVendor.product_id)
            .where(ProductVendor.vendor_id == vendor_id)
        )
        sales_result = await self.db.execute(
            select(func.coalesce(func.sum(OrderProduct.product_price * OrderProduct.quantity), 0))
            .join(Order, OrderProduct.order_id == Order.id)
            .where(
                OrderProduct.product_id.in_(vendor_product_ids),
                Order.status == OrderStatus.PAID.value
            )
        )
        total_sales = sales_result.scalar() or 0
        
        return (product_count, total_sales)
    
    async def get_order_vendor_products(
        self,
        order_id: UUID,
        vendor_id: UUID
    ) -> tuple[list[OrderProduct], Decimal]:
        """
        Get order products that belong to a vendor and the total sales amount.
        Returns (list of OrderProduct, total amount for vendor's products).
        """
        result = await self.db.execute(
            select(OrderProduct)
            .join(ProductVendor, OrderProduct.product_id == ProductVendor.product_id)
            .where(
                OrderProduct.order_id == order_id,
                ProductVendor.vendor_id == vendor_id
            )
        )
        vendor_order_products = list(result.scalars().all())
        total = sum(op.product_price * op.quantity for op in vendor_order_products)
        return (vendor_order_products, total)
    
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
