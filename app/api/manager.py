from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.user import User
from app.dependencies.auth import require_manager
from app.schemas.wishlist import (
    WishlistCreate,
    WishlistUpdate,
    WishlistResponse
)
from app.services.wishlist_service import WishlistService
from app.services.user_service import UserService
from app.core.exceptions import NotFoundException, ConflictError

router = APIRouter()


@router.post("/wishlists", response_model=WishlistResponse, status_code=status.HTTP_201_CREATED)
async def create_wishlist(
    wishlist_data: WishlistCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """
    Create a wishlist and assign an admin (MANAGER only).
    
    This endpoint:
    1. Creates or gets the admin user
    2. Generates a password for new admins
    3. Creates the wishlist in DRAFT status
    4. Sends credentials email to admin
    """
    user_service = UserService(db)
    wishlist_service = WishlistService(db)
    
    # Check if admin user already exists
    admin = await user_service.get_by_email(wishlist_data.admin_email)
    
    if admin:
        # Verify admin belongs to this manager
        if admin.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This admin belongs to another manager"
            )
    else:
        # Create new admin user
        admin, password = await user_service.create_admin_with_manager(
            email=wishlist_data.admin_email,
            full_name=wishlist_data.admin_full_name,
            manager_id=current_user.id
        )
        
        await db.commit()
        
        # Send credentials email via SendGrid
        from app.services.email_service import EmailService
        email_service = EmailService()
        background_tasks.add_task(
            email_service.send_admin_credentials_email,
            admin,
            password
        )
    
    # Create wishlist
    address_dict = wishlist_data.delivery_address.model_dump() if wishlist_data.delivery_address else None
    
    wishlist = await wishlist_service.create(
        admin_id=admin.id,
        manager_id=current_user.id,
        title=wishlist_data.title,
        description=wishlist_data.description,
        logo_url=wishlist_data.logo_url,
        header_image_url=wishlist_data.header_image_url,
        primary_color=wishlist_data.primary_color,
        secondary_color=wishlist_data.secondary_color,
        delivery_address=address_dict
    )
    
    await db.commit()
    
    response = WishlistResponse.model_validate(wishlist)
    response.qr_code_url = f"/api/wishlists/{wishlist.id}/qr-code"
    return response


@router.get("/wishlists", response_model=List[WishlistResponse])
async def list_wishlists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """List all wishlists for the current manager (MANAGER only)."""
    wishlist_service = WishlistService(db)
    wishlists = await wishlist_service.get_manager_wishlists(current_user.id)
    
    responses = []
    for w in wishlists:
        response = WishlistResponse.model_validate(w)
        response.qr_code_url = f"/api/wishlists/{w.id}/qr-code"
        responses.append(response)
    return responses


@router.put("/wishlists/{wishlist_id}", response_model=WishlistResponse)
async def update_wishlist(
    wishlist_id: UUID,
    wishlist_data: WishlistUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Update a wishlist (MANAGER only)."""
    wishlist_service = WishlistService(db)
    
    # Verify wishlist belongs to this manager
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    if wishlist.manager_id != current_user.id:
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
        
        response = WishlistResponse.model_validate(wishlist)
        response.qr_code_url = f"/api/wishlists/{wishlist.id}/qr-code"
        return response
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/wishlists/{wishlist_id}", response_model=WishlistResponse)
async def get_wishlist(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Get wishlist details (MANAGER only)."""
    wishlist_service = WishlistService(db)
    
    wishlist = await wishlist_service.get_by_id(wishlist_id, load_products=True)
    
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    if wishlist.manager_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own wishlists"
        )
    
    response = WishlistResponse.model_validate(wishlist)
    response.qr_code_url = f"/api/wishlists/{wishlist.id}/qr-code"
    return response
