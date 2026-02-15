from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.wishlist import WishlistStatus
from app.dependencies.auth import get_current_user, require_super_admin
from app.schemas.wishlist import (
    WishlistCreate,
    WishlistCreateByAdmin,
    WishlistUpdate,
    WishlistResponse,
    UpdateWishlistProductsRequest,
    ProductInWishlist
)
from app.services.wishlist_service import WishlistService
from app.services.user_service import UserService
from app.services.qr_service import QRCodeService
from app.core.exceptions import NotFoundException, ConflictError, PermissionDenied

router = APIRouter()


@router.post("", response_model=WishlistResponse, status_code=status.HTTP_201_CREATED)
async def create_wishlist(
    wishlist_data: WishlistCreate | WishlistCreateByAdmin,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new wishlist with optional products.
    
    - MANAGER: Creates wishlist for an admin (requires admin_email and admin_full_name)
    - ADMIN: Creates their own wishlist
    - SUPER_ADMIN: Can create for any admin
    """
    wishlist_service = WishlistService(db)
    user_service = UserService(db)
    
    try:
        # Determine admin and manager based on role
        if current_user.role == UserRole.MANAGER.value:
            # Manager creates for an admin
            if not isinstance(wishlist_data, WishlistCreate):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Managers must provide admin_email and admin_full_name"
                )
            
            # Get or create admin user
            admin = await user_service.get_by_email(wishlist_data.admin_email)
            if not admin:
                # Create new admin
                admin, _ = await user_service.create_admin_with_manager(
                    email=wishlist_data.admin_email,
                    full_name=wishlist_data.admin_full_name,
                    manager_id=current_user.id
                )
            elif admin.manager_id != current_user.id:
                raise PermissionDenied("This admin does not belong to you")
            
            admin_id = admin.id
            manager_id = current_user.id
            
        elif current_user.role == UserRole.ADMIN.value:
            # Admin creates their own wishlist
            if not current_user.manager_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Admin user must be assigned to a manager before creating wishlists"
                )
            admin_id = current_user.id
            manager_id = current_user.manager_id
            
        elif current_user.role == UserRole.SUPER_ADMIN.value:
            # Super admin can create for any admin
            if isinstance(wishlist_data, WishlistCreate):
                admin = await user_service.get_by_email(wishlist_data.admin_email)
                if not admin:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Admin user not found"
                    )
                if not admin.manager_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Admin user must be assigned to a manager before creating wishlists"
                    )
                admin_id = admin.id
                manager_id = admin.manager_id
            else:
                # If no admin specified, create for themselves (unusual but allowed)
                admin_id = current_user.id
                manager_id = current_user.id
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create wishlists"
            )
        
        # Prepare delivery address
        delivery_address = None
        if wishlist_data.delivery_address:
            delivery_address = wishlist_data.delivery_address.model_dump()
        
        # Prepare products
        products = []
        if hasattr(wishlist_data, 'products') and wishlist_data.products:
            products = [
                {"product_id": p.product_id, "quantity": p.quantity}
                for p in wishlist_data.products
            ]
        
        # Create wishlist
        if products:
            wishlist = await wishlist_service.create_with_products(
                admin_id=admin_id,
                manager_id=manager_id,
                products=products,
                title=wishlist_data.title,
                description=wishlist_data.description,
                logo_url=wishlist_data.logo_url,
                header_image_url=wishlist_data.header_image_url,
                primary_color=wishlist_data.primary_color,
                secondary_color=wishlist_data.secondary_color,
                delivery_address=delivery_address
            )
        else:
            wishlist = await wishlist_service.create(
                admin_id=admin_id,
                manager_id=manager_id,
                title=wishlist_data.title,
                description=wishlist_data.description,
                logo_url=wishlist_data.logo_url,
                header_image_url=wishlist_data.header_image_url,
                primary_color=wishlist_data.primary_color,
                secondary_color=wishlist_data.secondary_color,
                delivery_address=delivery_address
            )
        
        await db.commit()
        
        # Fetch the wishlist again with all relationships loaded
        wishlist = await wishlist_service.get_by_id(wishlist.id, load_products=True)
        
        response = WishlistResponse.model_validate(wishlist)
        response.qr_code_url = f"/api/wishlists/{wishlist.id}/qr-code"
        return response
        
    except (NotFoundException, ConflictError, PermissionDenied) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", response_model=List[WishlistResponse])
async def list_wishlists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List wishlists with role-based filtering.
    
    - SUPER_ADMIN: Can view all wishlists
    - MANAGER: Can view their managed wishlists
    - ADMIN: Can view their own wishlists
    """
    wishlist_service = WishlistService(db)
    
    if current_user.role == UserRole.SUPER_ADMIN.value:
        wishlists = await wishlist_service.get_all(load_products=True)
    elif current_user.role == UserRole.MANAGER.value:
        wishlists = await wishlist_service.get_manager_wishlists(current_user.id, load_products=True)
    elif current_user.role == UserRole.ADMIN.value:
        wishlists = await wishlist_service.get_admin_wishlists(current_user.id, load_products=True)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view wishlists"
        )
    
    responses = []
    for w in wishlists:
        response = WishlistResponse.model_validate(w)
        response.qr_code_url = f"/api/wishlists/{w.id}/qr-code"
        responses.append(response)
    return responses


@router.get("/{wishlist_id}", response_model=WishlistResponse)
async def get_wishlist(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get wishlist by ID.
    
    - SUPER_ADMIN: Can view any wishlist
    - MANAGER: Can view their managed wishlists
    - ADMIN: Can view their own wishlists
    """
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id, load_products=True)
    
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN.value:
        pass  # Can view any
    elif current_user.role == UserRole.MANAGER.value:
        if wishlist.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view wishlists you manage"
            )
    elif current_user.role == UserRole.ADMIN.value:
        if wishlist.admin_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own wishlists"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this wishlist"
        )
    
    response = WishlistResponse.model_validate(wishlist)
    response.qr_code_url = f"/api/wishlists/{wishlist.id}/qr-code"
    return response


@router.put("/{wishlist_id}", response_model=WishlistResponse)
async def update_wishlist(
    wishlist_id: UUID,
    wishlist_data: WishlistUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update wishlist.
    
    - SUPER_ADMIN: Can update any wishlist
    - MANAGER: Can update their managed wishlists
    - ADMIN: Can update their own wishlists
    """
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN.value:
        pass  # Can update any
    elif current_user.role == UserRole.MANAGER.value:
        if wishlist.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update wishlists you manage"
            )
    elif current_user.role == UserRole.ADMIN.value:
        if wishlist.admin_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own wishlists"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this wishlist"
        )
    
    try:
        # Prepare delivery address
        delivery_address = None
        if wishlist_data.delivery_address:
            delivery_address = wishlist_data.delivery_address.model_dump()
        
        updated_wishlist = await wishlist_service.update(
            wishlist_id=wishlist_id,
            title=wishlist_data.title,
            description=wishlist_data.description,
            logo_url=wishlist_data.logo_url,
            header_image_url=wishlist_data.header_image_url,
            primary_color=wishlist_data.primary_color,
            secondary_color=wishlist_data.secondary_color,
            delivery_address=delivery_address
        )
        
        await db.commit()
        
        # Refresh to load products
        await db.refresh(updated_wishlist, attribute_names=["products"])
        
        response = WishlistResponse.model_validate(updated_wishlist)
        response.qr_code_url = f"/api/wishlists/{updated_wishlist.id}/qr-code"
        return response
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/{wishlist_id}/products", response_model=WishlistResponse)
async def update_wishlist_products(
    wishlist_id: UUID,
    request: UpdateWishlistProductsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update products in a wishlist (replaces all existing products).
    
    - SUPER_ADMIN: Can update any wishlist
    - MANAGER: Can update their managed wishlists
    - ADMIN: Can update their own wishlists
    """
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN.value:
        pass  # Can update any
    elif current_user.role == UserRole.MANAGER.value:
        if wishlist.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update wishlists you manage"
            )
    elif current_user.role == UserRole.ADMIN.value:
        if wishlist.admin_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own wishlists"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this wishlist"
        )
    
    try:
        # Prepare products
        products = [
            {"product_id": p.product_id, "quantity": p.quantity}
            for p in request.products
        ]
        
        updated_wishlist = await wishlist_service.update_products(
            wishlist_id=wishlist_id,
            products=products
        )
        
        await db.commit()
        
        # Refresh to load products (already loaded by update_products)
        await db.refresh(updated_wishlist, attribute_names=["products"])
        
        response = WishlistResponse.model_validate(updated_wishlist)
        response.qr_code_url = f"/api/wishlists/{updated_wishlist.id}/qr-code"
        return response
        
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/{wishlist_id}/publish", response_model=WishlistResponse)
async def publish_wishlist(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Publish a wishlist (ADMIN or SUPER_ADMIN only).
    
    - Enforces one published wishlist per admin
    - Only the admin owner or super admin can publish
    """
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN.value:
        admin_id = wishlist.admin_id
    elif current_user.role == UserRole.ADMIN.value:
        if wishlist.admin_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only publish your own wishlists"
            )
        admin_id = current_user.id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can publish wishlists"
        )
    
    try:
        published_wishlist = await wishlist_service.publish(wishlist_id, admin_id)
        await db.commit()
        
        # Refresh to load products
        await db.refresh(published_wishlist, attribute_names=["products"])
        
        response = WishlistResponse.model_validate(published_wishlist)
        response.qr_code_url = f"/api/wishlists/{published_wishlist.id}/qr-code"
        return response
        
    except (ConflictError, PermissionDenied) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{wishlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wishlist(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete wishlist.
    
    - SUPER_ADMIN: Can delete any wishlist
    - MANAGER: Can delete their managed wishlists
    - ADMIN: Can delete their own wishlists
    
    WARNING: This is a hard delete and will cascade to products and orders.
    """
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN.value:
        pass  # Can delete any
    elif current_user.role == UserRole.MANAGER.value:
        if wishlist.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete wishlists you manage"
            )
    elif current_user.role == UserRole.ADMIN.value:
        if wishlist.admin_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own wishlists"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this wishlist"
        )
    
    try:
        await wishlist_service.delete(wishlist_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{wishlist_id}/qr-code")
async def get_wishlist_qr_code(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get QR code for a wishlist.
    
    - SUPER_ADMIN: Can get QR for any wishlist
    - MANAGER: Can get QR for their managed wishlists
    - ADMIN: Can get QR for their own wishlists
    
    Returns a PNG image that redirects to the frontend URL.
    """
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.SUPER_ADMIN.value:
        pass  # Can view any
    elif current_user.role == UserRole.MANAGER.value:
        if wishlist.manager_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view wishlists you manage"
            )
    elif current_user.role == UserRole.ADMIN.value:
        if wishlist.admin_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own wishlists"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this wishlist"
        )
    
    # Generate QR code for frontend URL
    frontend_url = f"{settings.frontend_url}/w/{wishlist.public_slug}"
    qr_buffer = QRCodeService.generate_qr_code(frontend_url)
    
    return StreamingResponse(
        qr_buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename=wishlist-{wishlist.public_slug}-qr.png"
        }
    )
