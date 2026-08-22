from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.dependencies.auth import get_current_user, require_super_admin
from app.models.order import Order, OrderStatus
from app.models.user import User, UserRole
from app.schemas.common import (
    FuneralHomeRef,
    GiftCollectionRef,
    PaginatedResponse,
    PaginationParams,
    UserRef,
)
from app.schemas.order import OrderProductResponse, OrderResponse, OrderUpdate
from app.schemas.vendor import VendorDashboardStats
from app.services.order_service import OrderService

router = APIRouter()


def _order_products(order: Order) -> list[OrderProductResponse]:
    return [
        OrderProductResponse(
            product_id=op.product_id,
            product_name=op.product_name,
            product_price=op.product_price,
            quantity=op.quantity,
        )
        for op in order.products
    ]


def _build_response(order: Order) -> OrderResponse:
    """Serialize an order with its gifts and enriched context blocks."""
    return OrderResponse(
        id=order.id,
        visitor_id=order.visitor_id,
        gift_collection_id=order.gift_collection_id,
        family_admin_id=order.family_admin_id,
        funeral_home_id=order.funeral_home_id,
        status=order.status,
        total_amount=order.total_amount,
        currency=order.currency,
        created_at=order.created_at,
        paid_at=order.paid_at,
        products=_order_products(order),
        visitor=UserRef.model_validate(order.visitor) if order.visitor else None,
        family_admin=(
            UserRef.model_validate(order.family_admin) if order.family_admin else None
        ),
        funeral_home=(
            FuneralHomeRef.model_validate(order.funeral_home) if order.funeral_home else None
        ),
        gift_collection=(
            GiftCollectionRef.model_validate(order.gift_collection)
            if order.gift_collection
            else None
        ),
    )


async def _attach_vendor_context(
    order_service: OrderService,
    response: OrderResponse,
    vendor_id: UUID,
) -> OrderResponse:
    vendor_products, vendor_amount = await order_service.get_order_vendor_products(
        response.id, vendor_id
    )
    response.vendor_products = [
        OrderProductResponse(
            product_id=op.product_id,
            product_name=op.product_name,
            product_price=op.product_price,
            quantity=op.quantity,
        )
        for op in vendor_products
    ]
    response.vendor_sales_amount = vendor_amount
    return response


@router.get("/vendor/dashboard", response_model=VendorDashboardStats)
async def get_vendor_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get vendor dashboard stats: gift count, total sales, order count.
    VENDOR role only.
    """
    if current_user.role != UserRole.VENDOR.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for vendor users only"
        )
    if not current_user.vendor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vendor user must be linked to a vendor entity"
        )
    
    order_service = OrderService(db)
    product_count, total_sales = await order_service.get_vendor_order_stats(
        current_user.vendor_id
    )
    orders = await order_service.get_vendor_orders(current_user.vendor_id)
    order_count = len(orders)
    
    return VendorDashboardStats(
        product_count=product_count,
        total_sales_amount=total_sales,
        order_count=order_count
    )


@router.get("", response_model=PaginatedResponse[OrderResponse])
async def list_orders(
    order_status: Optional[OrderStatus] = Query(
        None, alias="status", description="Filter by order status"
    ),
    funeral_home_id: Optional[UUID] = Query(
        None, description="Filter by funeral home (SUPER_ADMIN)"
    ),
    family_admin_id: Optional[UUID] = Query(None, description="Filter by family admin"),
    director_id: Optional[UUID] = Query(None, description="Filter by director (SUPER_ADMIN)"),
    gift_collection_id: Optional[UUID] = Query(None, description="Filter by gift collection"),
    date_from: Optional[datetime] = Query(None, description="Orders created at or after"),
    date_to: Optional[datetime] = Query(None, description="Orders created at or before"),
    search: Optional[str] = Query(
        None, description="Search Stripe session id, collection title and slug"
    ),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List orders, scoped by role.
    
    - SUPER_ADMIN: all orders, filterable by funeral home, family admin and director
    - DIRECTOR: only their own funeral home's orders
    - FAMILY_ADMIN: only orders on their own collections
    - VISITOR: only their own orders
    - VENDOR: only orders containing their gifts, enriched with vendor totals
    """
    order_service = OrderService(db)

    scoped: dict = {
        "funeral_home_id": None,
        "family_admin_id": family_admin_id,
        "director_id": None,
        "visitor_id": None,
        "vendor_id": None,
    }

    if current_user.role == UserRole.SUPER_ADMIN.value:
        scoped["funeral_home_id"] = funeral_home_id
        scoped["director_id"] = director_id
    elif current_user.role == UserRole.DIRECTOR.value:
        if current_user.funeral_home_id:
            scoped["funeral_home_id"] = current_user.funeral_home_id
        else:
            # Not assigned to a funeral home yet: fall back to their own collections.
            scoped["director_id"] = current_user.id
    elif current_user.role == UserRole.FAMILY_ADMIN.value:
        scoped["family_admin_id"] = current_user.id
    elif current_user.role == UserRole.VISITOR.value:
        scoped["visitor_id"] = current_user.id
    elif current_user.role == UserRole.VENDOR.value:
        if not current_user.vendor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vendor user must be linked to a vendor entity"
            )
        scoped["vendor_id"] = current_user.vendor_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view orders"
        )

    orders, total = await order_service.list_orders(
        funeral_home_id=scoped["funeral_home_id"],
        family_admin_id=scoped["family_admin_id"],
        director_id=scoped["director_id"],
        gift_collection_id=gift_collection_id,
        visitor_id=scoped["visitor_id"],
        vendor_id=scoped["vendor_id"],
        status=order_status,
        date_from=date_from,
        date_to=date_to,
        search=search,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    items = []
    for order in orders:
        response = _build_response(order)
        if current_user.role == UserRole.VENDOR.value and current_user.vendor_id:
            response = await _attach_vendor_context(
                order_service, response, current_user.vendor_id
            )
        items.append(response)

    return PaginatedResponse.build(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get order by ID.
    
    - SUPER_ADMIN: any order
    - DIRECTOR: orders on collections in their funeral home
    - FAMILY_ADMIN: orders on their own collections
    - VISITOR: their own orders
    - VENDOR: orders containing their gifts
    """
    order_service = OrderService(db)
    order = await order_service.get_by_id(order_id, load_products=True)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    if current_user.role == UserRole.SUPER_ADMIN.value:
        pass
    elif current_user.role == UserRole.DIRECTOR.value:
        same_funeral_home = (
            current_user.funeral_home_id is not None
            and order.funeral_home_id == current_user.funeral_home_id
        )
        owns_collection = (
            order.gift_collection is not None
            and order.gift_collection.director_id == current_user.id
        )
        if not (same_funeral_home or owns_collection):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view orders for your own funeral home"
            )
    elif current_user.role == UserRole.FAMILY_ADMIN.value:
        if order.family_admin_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view orders for your own gift collections"
            )
    elif current_user.role == UserRole.VISITOR.value:
        if order.visitor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own orders"
            )
    elif current_user.role == UserRole.VENDOR.value:
        if not current_user.vendor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vendor user must be linked to a vendor entity"
            )
        vendor_products, _ = await order_service.get_order_vendor_products(
            order.id, current_user.vendor_id
        )
        if not vendor_products:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or does not contain your vendor's gifts"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this order"
        )
    
    response = _build_response(order)
    
    if current_user.role == UserRole.VENDOR.value and current_user.vendor_id:
        response = await _attach_vendor_context(
            order_service, response, current_user.vendor_id
        )
    
    return response


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: UUID,
    order_data: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Update order (SUPER_ADMIN only).
    
    Can update status, total_amount, and paid_at.
    When status is set to PAID, paid_at is automatically set if not provided.
    """
    order_service = OrderService(db)
    
    try:
        order = await order_service.update(
            order_id=order_id,
            status=order_data.status,
            total_amount=order_data.total_amount,
            paid_at=order_data.paid_at
        )
        
        await db.commit()
        
        order = await order_service.get_by_id(order.id, load_products=True)
        return _build_response(order)
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Delete order (SUPER_ADMIN only).
    
    WARNING: This is a hard delete and will cascade to order gifts.
    """
    order_service = OrderService(db)
    
    try:
        await order_service.delete(order_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
