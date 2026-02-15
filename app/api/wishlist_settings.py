from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.models.user import User
from app.dependencies.auth import require_manager, require_admin, require_manager_or_admin
from app.schemas.settings import (
    WishlistSettingsCreate,
    WishlistSettingsUpdate,
    WishlistSettingsResponse
)
from app.services.wishlist_settings_service import WishlistSettingsService
from app.services.wishlist_service import WishlistService
from app.core.exceptions import NotFoundException, ConflictError, PermissionDenied

router = APIRouter()


# Manager endpoints
@router.get("/manager/wishlists/{wishlist_id}/settings", response_model=Optional[WishlistSettingsResponse])
async def get_wishlist_settings_manager(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Get wishlist settings (MANAGER only)."""
    # Verify manager owns this wishlist
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    
    if wishlist.manager_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to access this wishlist")
    
    settings_service = WishlistSettingsService(db)
    settings = await settings_service.get_by_wishlist_id(wishlist_id)
    return settings


@router.post("/manager/wishlists/{wishlist_id}/settings", response_model=WishlistSettingsResponse, status_code=status.HTTP_201_CREATED)
async def create_wishlist_settings_manager(
    wishlist_id: UUID,
    settings_data: WishlistSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Create wishlist settings (MANAGER only)."""
    # Verify manager owns this wishlist
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    
    if wishlist.manager_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to modify this wishlist")
    
    settings_service = WishlistSettingsService(db)
    
    try:
        settings = await settings_service.create(
            wishlist_id=wishlist_id,
            banner_image_url=settings_data.banner_image_url,
            custom_message=settings_data.custom_message
        )
        await db.commit()
        return settings
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.put("/manager/wishlists/{wishlist_id}/settings", response_model=WishlistSettingsResponse)
async def update_wishlist_settings_manager(
    wishlist_id: UUID,
    settings_data: WishlistSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Update wishlist settings (MANAGER only)."""
    # Verify manager owns this wishlist
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    
    if wishlist.manager_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to modify this wishlist")
    
    settings_service = WishlistSettingsService(db)
    
    try:
        settings = await settings_service.update(
            wishlist_id=wishlist_id,
            banner_image_url=settings_data.banner_image_url,
            custom_message=settings_data.custom_message
        )
        await db.commit()
        return settings
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/manager/wishlists/{wishlist_id}/settings", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wishlist_settings_manager(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Delete wishlist settings (MANAGER only)."""
    # Verify manager owns this wishlist
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    
    if wishlist.manager_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to modify this wishlist")
    
    settings_service = WishlistSettingsService(db)
    
    try:
        await settings_service.delete(wishlist_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# Admin endpoints
@router.get("/admin/wishlists/{wishlist_id}/settings", response_model=Optional[WishlistSettingsResponse])
async def get_wishlist_settings_admin(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get wishlist settings (ADMIN only)."""
    # Verify admin owns this wishlist
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    
    if wishlist.admin_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to access this wishlist")
    
    settings_service = WishlistSettingsService(db)
    settings = await settings_service.get_by_wishlist_id(wishlist_id)
    return settings


@router.post("/admin/wishlists/{wishlist_id}/settings", response_model=WishlistSettingsResponse, status_code=status.HTTP_201_CREATED)
async def create_wishlist_settings_admin(
    wishlist_id: UUID,
    settings_data: WishlistSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Create wishlist settings (ADMIN only)."""
    # Verify admin owns this wishlist
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    
    if wishlist.admin_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to modify this wishlist")
    
    settings_service = WishlistSettingsService(db)
    
    try:
        settings = await settings_service.create(
            wishlist_id=wishlist_id,
            banner_image_url=settings_data.banner_image_url,
            custom_message=settings_data.custom_message
        )
        await db.commit()
        return settings
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.put("/admin/wishlists/{wishlist_id}/settings", response_model=WishlistSettingsResponse)
async def update_wishlist_settings_admin(
    wishlist_id: UUID,
    settings_data: WishlistSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Update wishlist settings (ADMIN only)."""
    # Verify admin owns this wishlist
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    
    if wishlist.admin_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to modify this wishlist")
    
    settings_service = WishlistSettingsService(db)
    
    try:
        settings = await settings_service.update(
            wishlist_id=wishlist_id,
            banner_image_url=settings_data.banner_image_url,
            custom_message=settings_data.custom_message
        )
        await db.commit()
        return settings
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/admin/wishlists/{wishlist_id}/settings", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wishlist_settings_admin(
    wishlist_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete wishlist settings (ADMIN only)."""
    # Verify admin owns this wishlist
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist not found")
    
    if wishlist.admin_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to modify this wishlist")
    
    settings_service = WishlistSettingsService(db)
    
    try:
        await settings_service.delete(wishlist_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
