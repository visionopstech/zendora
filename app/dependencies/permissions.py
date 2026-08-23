from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.gift_collection import GiftCollection
from app.dependencies.auth import get_current_user
from app.services.gift_collection_service import GiftCollectionService
from app.core.exceptions import PermissionDenied, NotFoundException


async def verify_gift_collection_ownership(
    gift_collection_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> GiftCollection:
    """
    Verify that the current user has permission to access the gift collection.
    
    Rules:
    - FAMILY_ADMIN: Can only access their own collections
    - DIRECTOR: Can only access collections in their funeral home
    - SUPER_ADMIN: Can access any collection
    
    Returns:
        GiftCollection: The collection if user has permission
        
    Raises:
        PermissionDenied: If user lacks permission
        NotFoundException: If collection not found
    """
    collection_service = GiftCollectionService(db)
    collection = await collection_service.get_by_id(gift_collection_id)
    
    if not collection:
        raise NotFoundException("Gift collection not found")
    
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return collection
    
    if current_user.role == UserRole.FAMILY_ADMIN.value:
        if collection.family_admin_id != current_user.id:
            raise PermissionDenied("You can only access your own gift collections")
        return collection
    
    if current_user.role == UserRole.DIRECTOR.value:
        if collection.director_id != current_user.id:
            raise PermissionDenied("You can only access gift collections you oversee")
        return collection
    
    raise PermissionDenied("You do not have permission to access this gift collection")


async def verify_family_admin_belongs_to_director(
    family_admin_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Verify that the family admin belongs to the current director.
    
    Raises:
        PermissionDenied: If the family admin belongs to another director
        NotFoundException: If the family admin is not found
    """
    if current_user.role != UserRole.DIRECTOR.value:
        raise PermissionDenied("Only directors can verify family admin ownership")
    
    from app.services.user_service import UserService
    user_service = UserService(db)
    
    family_admin = await user_service.get_by_id(family_admin_id)
    
    if not family_admin:
        raise NotFoundException("Family admin not found")
    
    if family_admin.director_id != current_user.id:
        raise PermissionDenied("This family admin does not belong to you")
    
    return family_admin


def require_roles(*allowed_roles: UserRole):
    """
    Dependency factory that requires one of the specified roles.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(user: User = Depends(require_roles(UserRole.FAMILY_ADMIN, UserRole.DIRECTOR))):
            pass
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        allowed_role_values = [role.value for role in allowed_roles]
        if current_user.role not in allowed_role_values:
            raise PermissionDenied(
                f"Access denied. Required roles: {', '.join(allowed_role_values)}"
            )
        return current_user
    
    return role_checker
