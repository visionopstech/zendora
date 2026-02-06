from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.order import OrderStatus
from app.dependencies.auth import get_current_user, require_super_admin
from app.schemas.order import OrderResponse, OrderUpdate, OrderProductResponse
from app.services.order_service import OrderService
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.get("", response_model=List[OrderResponse])
async def list_orders(
    status: Optional[OrderStatus] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List orders with role-based filtering.
    
    - SUPER_ADMIN: Can view all orders
    - MANAGER: Can view orders for their managed wishlists
    - ADMIN: Can view orders for their wishlists
    - VISITOR: Can view their own orders
    """
    order_service = OrderService(db)
    
    # Super admin can see everything
    if current_user.role == UserRole.SUPER_ADMIN.value:
        orders = await order_service.get_all(status=status)
    # Manager can see orders for their managed wishlists
    elif current_user.role == UserRole.MANAGER.value:
        orders = await order_service.get_manager_orders(current_user.id)
        if status:
            orders = [o for o in orders if o.status == status.value]
    # Admin can see orders for their wishlists
    elif current_user.role == UserRole.ADMIN.value:
        orders = await order_service.get_admin_orders(current_user.id)
        if status:
            orders = [o for o in orders if o.status == status.value]
    # Visitor can see their own orders
    elif current_user.role == UserRole.VISITOR.value:
        orders = await order_service.get_visitor_orders(current_user.id)
        if status:
            orders = [o for o in orders if o.status == status.value]
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view orders"
        )
    
    # Load order products and build response
    result = []
    for order in orders:
        order_with_products = await order_service.get_by_id(order.id, load_products=True)
        
        products = [
            OrderProductResponse(
                product_id=op.product_id,
                product_name=op.product_name,
                product_price=op.product_price,
                quantity=op.quantity
            )
            for op in order_with_products.products
        ]
        
        order_data = OrderResponse.model_validate(order_with_products).model_dump()
        order_data["products"] = products
        result.append(OrderResponse(**order_data))
    
    return result


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get order by ID.
    
    - SUPER_ADMIN: Can view any order
    - MANAGER: Can view orders for their managed wishlists
    - ADMIN: Can view orders for their wishlists
    - VISITOR: Can view their own orders
    """
    order_service = OrderService(db)
    order = await order_service.get_by_id(order_id, load_products=True)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN.value:
        # Super admin can see everything
        pass
    elif current_user.role == UserRole.MANAGER.value:
        # Manager can see orders for their managed wishlists
        if order.wishlist.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view orders for your managed wishlists"
            )
    elif current_user.role == UserRole.ADMIN.value:
        # Admin can see orders for their wishlists
        if order.admin_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view orders for your wishlists"
            )
    elif current_user.role == UserRole.VISITOR.value:
        # Visitor can see their own orders
        if order.visitor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own orders"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this order"
        )
    
    # Build response with products
    products = [
        OrderProductResponse(
            product_id=op.product_id,
            product_name=op.product_name,
            product_price=op.product_price,
            quantity=op.quantity
        )
        for op in order.products
    ]
    
    order_data = OrderResponse.model_validate(order).model_dump()
    order_data["products"] = products
    
    return OrderResponse(**order_data)


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
        
        # Load products for response
        order = await order_service.get_by_id(order.id, load_products=True)
        
        products = [
            OrderProductResponse(
                product_id=op.product_id,
                product_name=op.product_name,
                product_price=op.product_price,
                quantity=op.quantity
            )
            for op in order.products
        ]
        
        order_data = OrderResponse.model_validate(order).model_dump()
        order_data["products"] = products
        
        return OrderResponse(**order_data)
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
    
    WARNING: This is a hard delete and will cascade to order products.
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
