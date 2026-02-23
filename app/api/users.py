from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional

from app.core.database import get_db
from app.models.user import User, UserRole
from app.dependencies.auth import get_current_user, require_super_admin
from app.schemas.user import UserCreate, UserManagementUpdate, UserResponse, ProfileUpdate
from app.services.user_management_service import UserManagementService
from app.core.exceptions import NotFoundException, ConflictError, PermissionDenied

router = APIRouter()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Create a new user (SUPER_ADMIN only).
    
    - ADMIN users must have a manager_id
    - Password must be at least 8 characters
    """
    user_service = UserManagementService(db)
    
    try:
        user = await user_service.create(
            email=user_data.email,
            password=user_data.password,
            role=user_data.role,
            full_name=user_data.full_name,
            manager_id=user_data.manager_id,
            vendor_id=user_data.vendor_id
        )
        
        await db.commit()
        
        return UserResponse.model_validate(user)
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except (NotFoundException, PermissionDenied) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", response_model=List[UserResponse])
async def list_users(
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List users with role-based filtering.
    
    - SUPER_ADMIN: Can list all users
    - MANAGER: Can only list their assigned ADMINs
    - ADMIN: Can only view their own profile (redirects to GET /users/{id})
    """
    user_service = UserManagementService(db)
    
    # Super admin can see everything
    if current_user.role == UserRole.SUPER_ADMIN.value:
        users = await user_service.get_all(
            role=role,
            include_inactive=include_inactive
        )
        return [UserResponse.model_validate(u) for u in users]
    
    # Manager can only see their admins
    if current_user.role == UserRole.MANAGER.value:
        users = await user_service.get_manager_admins(current_user.id)
        return [UserResponse.model_validate(u) for u in users]
    
    # Admin can only see themselves
    if current_user.role == UserRole.ADMIN.value:
        return [UserResponse.model_validate(current_user)]
    
    # Vendor can only see themselves
    if current_user.role == UserRole.VENDOR.value:
        return [UserResponse.model_validate(current_user)]
    
    # Other roles have no access
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to list users"
    )


@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    user_data: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the authenticated user's own profile.

    Allows any authenticated user to update their full name. Only full_name is
    updatable via this endpoint.
    """
    user_service = UserManagementService(db)
    user = await user_service.update(
        user_id=current_user.id,
        full_name=user_data.full_name
    )
    await db.commit()
    return UserResponse.model_validate(user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get user by ID.
    
    - SUPER_ADMIN: Can view any user
    - MANAGER: Can only view their assigned ADMINs
    - ADMIN: Can only view their own profile
    """
    user_service = UserManagementService(db)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Super admin can see everything
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return UserResponse.model_validate(user)
    
    # Manager can only see their admins
    if current_user.role == UserRole.MANAGER.value:
        if user.manager_id == current_user.id and user.role == UserRole.ADMIN.value:
            return UserResponse.model_validate(user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your assigned admins"
        )
    
    # Admin can only see themselves
    if current_user.role == UserRole.ADMIN.value:
        if user.id == current_user.id:
            return UserResponse.model_validate(user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile"
        )
    
    # Vendor can only see themselves
    if current_user.role == UserRole.VENDOR.value:
        if user.id == current_user.id:
            return UserResponse.model_validate(user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile"
        )
    
    # Other roles have no access
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to view this user"
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserManagementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Update user (SUPER_ADMIN only).
    
    - Can update email, full_name, role, is_active, manager_id, and password
    - Email must be unique
    - ADMIN users must have a manager_id
    """
    user_service = UserManagementService(db)
    
    try:
        user = await user_service.update(
            user_id=user_id,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role,
            is_active=user_data.is_active,
            manager_id=user_data.manager_id,
            vendor_id=user_data.vendor_id,
            password=user_data.password
        )
        
        await db.commit()
        
        return UserResponse.model_validate(user)
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except PermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Delete user (SUPER_ADMIN only).
    
    WARNING: This is a hard delete and will cascade to related records.
    """
    user_service = UserManagementService(db)
    
    try:
        await user_service.delete(user_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
