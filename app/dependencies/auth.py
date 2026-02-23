from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.exceptions import UnauthorizedError, PermissionDenied
from app.models.user import User, UserRole
from app.services.user_service import UserService


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        db: Database session
        
    Returns:
        User: Current authenticated user
        
    Raises:
        UnauthorizedError: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise UnauthorizedError("Invalid authentication token")
    
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")
    
    user_service = UserService(db)
    user = await user_service.get_by_id(UUID(user_id))
    
    if not user:
        raise UnauthorizedError("User not found")
    
    if not user.is_active:
        raise UnauthorizedError("User account is inactive")
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise UnauthorizedError("User account is inactive")
    return current_user


def require_role(*allowed_roles: UserRole):
    """
    Dependency factory to require specific roles.
    
    Usage:
        @router.get("/admin-only")
        async def admin_route(user: User = Depends(require_role(UserRole.SUPER_ADMIN))):
            pass
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        allowed_role_values = [r.value for r in allowed_roles]
        if current_user.role not in allowed_role_values:
            raise PermissionDenied(
                f"This action requires one of the following roles: {', '.join(allowed_role_values)}"
            )
        return current_user
    
    return role_checker


# Convenience dependencies for specific roles
require_super_admin = require_role(UserRole.SUPER_ADMIN)
require_manager = require_role(UserRole.MANAGER)
require_admin = require_role(UserRole.ADMIN)
require_manager_or_admin = require_role(UserRole.MANAGER, UserRole.ADMIN)
require_vendor = require_role(UserRole.VENDOR)


async def require_vendor_with_entity(current_user: User = Depends(require_vendor)) -> User:
    """
    Dependency that requires VENDOR role and ensures the user has a vendor_id.
    Use for endpoints that need to access the vendor entity.
    """
    if not current_user.vendor_id:
        raise PermissionDenied("Vendor user must be linked to a vendor entity")
    return current_user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Dependency to optionally get the current user.
    Returns None if no valid token is provided.
    Useful for endpoints that work with or without authentication.
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except UnauthorizedError:
        return None
