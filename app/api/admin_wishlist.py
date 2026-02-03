from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.user import User
from app.dependencies.auth import require_admin
from app.schemas.wishlist import (
    WishlistCreateByAdmin,
    WishlistUpdate,
    WishlistResponse,
    AddProductsRequest,
    AddProductsListRequest
)
from app.services.wishlist_service import WishlistService
from app.services.user_service import UserService
from app.core.exceptions import NotFoundException, ConflictError, PermissionDenied

router = APIRouter()


@router.get("/wishlists", response_model=List[WishlistResponse])
async def list_my_wishlists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """List all wishlists for the current admin (ADMIN only)."""
    wishlist_service = WishlistService(db)
    wishlists = await wishlist_service.get_admin_wishlists(current_user.id)
    
    return [WishlistResponse.model_validate(w) for w in wishlists]


@router.post("/wishlists", response_model=WishlistResponse, status_code=status.HTTP_201_CREATED)
async def create_my_wishlist(
    wishlist_data: WishlistCreateByAdmin,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create a new wishlist (ADMIN only)."""
    if not current_user.manager_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin must be assigned to a manager"
        )
    
    wishlist_service = WishlistService(db)
    
    # Create wishlist
    address_dict = wishlist_data.delivery_address.model_dump() if wishlist_data.delivery_address else None
    
    wishlist = await wishlist_service.create(
        admin_id=current_user.id,
        manager_id=current_user.manager_id,
        title=wishlist_data.title,
        description=wishlist_data.description,
        logo_url=wishlist_data.logo_url,
        header_image_url=wishlist_data.header_image_url,
        primary_color=wishlist_data.primary_color,
        secondary_color=wishlist_data.secondary_color,
        delivery_address=address_dict
    )
    
    await db.commit()
    
    return WishlistResponse.model_validate(wishlist)


@router.get("/wishlists/{wishlist_id}", response_model=WishlistResponse)
async def get_my_wishlist(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get wishlist details (ADMIN only)."""
    wishlist_service = WishlistService(db)
    
    wishlist = await wishlist_service.get_by_id(wishlist_id, load_products=True)
    
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    if wishlist.admin_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own wishlists"
        )
    
    return WishlistResponse.model_validate(wishlist)


@router.put("/wishlists/{wishlist_id}", response_model=WishlistResponse)
async def update_my_wishlist(
    wishlist_id: UUID,
    wishlist_data: WishlistUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update a wishlist (ADMIN only)."""
    wishlist_service = WishlistService(db)
    
    # Verify wishlist belongs to this admin
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    if wishlist.admin_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own wishlists"
        )
    
    # Update wishlist
    address_dict = wishlist_data.delivery_address.model_dump() if wishlist_data.delivery_address else None
    
    try:
        wishlist = await wishlist_service.update(
            wishlist_id=wishlist_id,
            title=wishlist_data.title,
            description=wishlist_data.description,
            logo_url=wishlist_data.logo_url,
            header_image_url=wishlist_data.header_image_url,
            primary_color=wishlist_data.primary_color,
            secondary_color=wishlist_data.secondary_color,
            delivery_address=address_dict
        )
        
        await db.commit()
        
        return WishlistResponse.model_validate(wishlist)
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/wishlists/{wishlist_id}/products")
async def add_products_to_wishlist(
    wishlist_id: UUID,
    request: AddProductsListRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Add products to a wishlist (ADMIN only)."""
    wishlist_service = WishlistService(db)
    
    # Verify wishlist belongs to this admin
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    if wishlist.admin_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only add products to your own wishlists"
        )
    
    # Add each product
    try:
        for product_request in request.products:
            await wishlist_service.add_product(
                wishlist_id=wishlist_id,
                product_id=product_request.product_id,
                quantity=product_request.quantity
            )
        
        await db.commit()
        
        return {"message": "Products added successfully", "count": len(request.products)}
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/wishlists/{wishlist_id}/products/{product_id}")
async def remove_product_from_wishlist(
    wishlist_id: UUID,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Remove a product from a wishlist (ADMIN only)."""
    wishlist_service = WishlistService(db)
    
    # Verify wishlist belongs to this admin
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    if wishlist.admin_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only remove products from your own wishlists"
        )
    
    try:
        await wishlist_service.remove_product(wishlist_id, product_id)
        await db.commit()
        
        return {"message": "Product removed successfully"}
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/wishlists/{wishlist_id}/publish", response_model=WishlistResponse)
async def publish_wishlist(
    wishlist_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Publish a wishlist (ADMIN only).
    
    This enforces the rule: one published wishlist per admin.
    Sends email to manager upon successful publication.
    """
    wishlist_service = WishlistService(db)
    
    try:
        wishlist = await wishlist_service.publish(wishlist_id, current_user.id)
        await db.commit()
        
        # Reload wishlist with manager relationship
        await db.refresh(wishlist, ['manager'])
        
        # Send email to manager
        from app.services.email_service import EmailService
        email_service = EmailService()
        background_tasks.add_task(
            email_service.send_wishlist_published_email,
            wishlist,
            wishlist.manager
        )
        
        return WishlistResponse.model_validate(wishlist)
    except (NotFoundException, ConflictError, PermissionDenied) as e:
        status_code = e.status_code if hasattr(e, 'status_code') else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=str(e)
        )
