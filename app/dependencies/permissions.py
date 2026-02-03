from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.wishlist import Wishlist
from app.dependencies.auth import get_current_user
from app.services.wishlist_service import WishlistService
from app.core.exceptions import PermissionDenied, NotFoundException


async def verify_wishlist_ownership(
    wishlist_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Wishlist:
    """
    Verify that the current user has permission to access the wishlist.
    
    Rules:
    - ADMIN: Can only access their own wishlists
    - MANAGER: Can only access wishlists they manage
    - SUPER_ADMIN: Can access any wishlist
    
    Returns:
        Wishlist: The wishlist if user has permission
        
    Raises:
        PermissionDenied: If user lacks permission
        NotFoundException: If wishlist not found
    """
    wishlist_service = WishlistService(db)
    wishlist = await wishlist_service.get_by_id(wishlist_id)
    
    if not wishlist:
        raise NotFoundException("Wishlist not found")
    
    # Super admin can access everything
    if current_user.role == UserRole.SUPER_ADMIN:
        return wishlist
    
    # Admin can only access their own wishlists
    if current_user.role == UserRole.ADMIN:
        if wishlist.admin_id != current_user.id:
            raise PermissionDenied("You can only access your own wishlists")
        return wishlist
    
    # Manager can only access wishlists they manage
    if current_user.role == UserRole.MANAGER:
        if wishlist.manager_id != current_user.id:
            raise PermissionDenied("You can only access wishlists you manage")
        return wishlist
    
    # Other roles cannot access wishlists
    raise PermissionDenied("You do not have permission to access this wishlist")


async def verify_admin_belongs_to_manager(
    admin_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Verify that the admin belongs to the current manager.
    
    Args:
        admin_id: ID of the admin to verify
        current_user: Current authenticated user (must be MANAGER)
        db: Database session
        
    Returns:
        User: The admin user if they belong to the manager
        
    Raises:
        PermissionDenied: If admin doesn't belong to manager
        NotFoundException: If admin not found
    """
    if current_user.role != UserRole.MANAGER:
        raise PermissionDenied("Only managers can verify admin ownership")
    
    from app.services.user_service import UserService
    user_service = UserService(db)
    
    admin = await user_service.get_by_id(admin_id)
    
    if not admin:
        raise NotFoundException("Admin not found")
    
    if admin.manager_id != current_user.id:
        raise PermissionDenied("This admin does not belong to you")
    
    return admin


def require_roles(*allowed_roles: UserRole):
    """
    Dependency factory that requires one of the specified roles.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))):
            pass
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            role_names = [role.value for role in allowed_roles]
            raise PermissionDenied(
                f"Access denied. Required roles: {', '.join(role_names)}"
            )
        return current_user
    
    return role_checker
