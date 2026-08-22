from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

from app.models.order import Order, OrderProduct, OrderStatus
from app.models.product import Product, ProductVendor
from app.models.gift_collection import GiftCollection
from app.core.exceptions import NotFoundException
from app.services.financial_service import FinancialService


class OrderService:
    """Service for order-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _detail_options(self, load_products: bool = False) -> list:
        options = [
            selectinload(Order.visitor),
            selectinload(Order.family_admin),
            selectinload(Order.funeral_home),
            selectinload(Order.gift_collection),
        ]
        if load_products:
            options.append(selectinload(Order.products))
        return options
    
    async def get_by_id(
        self,
        order_id: UUID,
        load_products: bool = False
    ) -> Optional[Order]:
        """Get order by ID."""
        query = (
            select(Order)
            .where(Order.id == order_id)
            .options(*self._detail_options(load_products))
        )
        
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
        gift_collection_id: UUID,
        family_admin_id: UUID,
        stripe_session_id: str,
        products: List[Product],
        quantities: dict[UUID, int]
    ) -> Order:
        """
        Create a new order with gifts.
        
        Args:
            visitor_id: ID of the visitor placing the order
            gift_collection_id: ID of the gift collection
            family_admin_id: ID of the family admin (denormalized for reporting)
            stripe_session_id: Stripe checkout session ID
            products: List of Product objects
            quantities: Dict mapping product_id to quantity
            
        Returns:
            Order: Created order
        """
        collection = await self.db.get(GiftCollection, gift_collection_id)
        if not collection:
            raise NotFoundException("Gift collection not found")

        financial_service = FinancialService(self.db)
        commission_data = await financial_service.calculate_order_commission(
            products=products,
            quantities=quantities,
            director_profit_percentage=await financial_service.get_director_profit_percentage(
                collection.director_id
            ),
        )
        
        order = Order(
            visitor_id=visitor_id,
            gift_collection_id=gift_collection_id,
            family_admin_id=family_admin_id,
            funeral_home_id=collection.funeral_home_id,
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
            director_id=collection.director_id,
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
    
    async def list_orders(
        self,
        funeral_home_id: Optional[UUID] = None,
        family_admin_id: Optional[UUID] = None,
        director_id: Optional[UUID] = None,
        gift_collection_id: Optional[UUID] = None,
        visitor_id: Optional[UUID] = None,
        vendor_id: Optional[UUID] = None,
        status: Optional[OrderStatus] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[List[Order], int]:
        """List orders with filters, returning the page and the total count."""
        filters = []
        
        if funeral_home_id is not None:
            filters.append(Order.funeral_home_id == funeral_home_id)
        if family_admin_id is not None:
            filters.append(Order.family_admin_id == family_admin_id)
        if gift_collection_id is not None:
            filters.append(Order.gift_collection_id == gift_collection_id)
        if visitor_id is not None:
            filters.append(Order.visitor_id == visitor_id)
        if status is not None:
            filters.append(Order.status == (status.value if isinstance(status, OrderStatus) else status))
        if date_from is not None:
            filters.append(Order.created_at >= date_from)
        if date_to is not None:
            filters.append(Order.created_at <= date_to)
        if director_id is not None:
            director_collection_ids = select(GiftCollection.id).where(
                GiftCollection.director_id == director_id
            )
            filters.append(Order.gift_collection_id.in_(director_collection_ids))
        if vendor_id is not None:
            vendor_product_ids = select(ProductVendor.product_id).where(
                ProductVendor.vendor_id == vendor_id
            )
            vendor_order_ids = select(OrderProduct.order_id).where(
                OrderProduct.product_id.in_(vendor_product_ids)
            )
            filters.append(Order.id.in_(vendor_order_ids))
        if search:
            pattern = f"%{search}%"
            searched_collection_ids = select(GiftCollection.id).where(
                or_(
                    GiftCollection.title.ilike(pattern),
                    GiftCollection.public_slug.ilike(pattern),
                )
            )
            filters.append(
                or_(
                    Order.stripe_session_id.ilike(pattern),
                    Order.gift_collection_id.in_(searched_collection_ids),
                )
            )
        
        count_query = select(func.count()).select_from(Order)
        if filters:
            count_query = count_query.where(*filters)
        total = (await self.db.execute(count_query)).scalar() or 0
        
        query = select(Order).options(*self._detail_options(load_products=True))
        if filters:
            query = query.where(*filters)
        query = query.order_by(Order.created_at.desc()).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all()), total
    
    async def get_visitor_orders(
        self,
        visitor_id: UUID
    ) -> List[Order]:
        """Get all orders for a visitor."""
        result = await self.db.execute(
            select(Order)
            .options(*self._detail_options(load_products=True))
            .where(Order.visitor_id == visitor_id)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_collection_orders(
        self,
        gift_collection_id: UUID
    ) -> List[Order]:
        """Get all orders for a gift collection."""
        result = await self.db.execute(
            select(Order)
            .options(*self._detail_options(load_products=True))
            .where(Order.gift_collection_id == gift_collection_id)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_all(
        self,
        status: Optional[OrderStatus] = None
    ) -> List[Order]:
        """Get all orders, optionally filtered by status."""
        query = select(Order).options(*self._detail_options(load_products=True))
        
        if status:
            query = query.where(Order.status == status.value)
        
        query = query.order_by(Order.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_family_admin_orders(
        self,
        family_admin_id: UUID
    ) -> List[Order]:
        """Get all orders for a family admin's collections."""
        result = await self.db.execute(
            select(Order)
            .options(*self._detail_options(load_products=True))
            .where(Order.family_admin_id == family_admin_id)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_director_orders(
        self,
        director_id: UUID
    ) -> List[Order]:
        """Get all orders for collections overseen by a director."""
        result = await self.db.execute(
            select(Order)
            .options(*self._detail_options(load_products=True))
            .join(GiftCollection, Order.gift_collection_id == GiftCollection.id)
            .where(GiftCollection.director_id == director_id)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_vendor_orders(
        self,
        vendor_id: UUID,
        status: Optional[OrderStatus] = None
    ) -> List[Order]:
        """Get orders that contain at least one gift from the vendor."""
        vendor_product_ids = (
            select(ProductVendor.product_id)
            .where(ProductVendor.vendor_id == vendor_id)
        )
        vendor_order_ids = select(OrderProduct.order_id).where(
            OrderProduct.product_id.in_(vendor_product_ids)
        )
        query = (
            select(Order)
            .options(*self._detail_options(load_products=True))
            .where(Order.id.in_(vendor_order_ids))
            .order_by(Order.created_at.desc())
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
        product_count: number of distinct gifts from this vendor
        total_sales_amount: sum of (price * quantity) for vendor's gifts in PAID orders
        """
        product_count_result = await self.db.execute(
            select(func.count(ProductVendor.product_id))
            .where(ProductVendor.vendor_id == vendor_id)
        )
        product_count = product_count_result.scalar() or 0
        
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
        Get order gifts that belong to a vendor and the total sales amount.
        Returns (list of OrderProduct, total amount for vendor's gifts).
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
