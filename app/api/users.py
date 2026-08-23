from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.core.database import get_db
from app.models.user import User, UserRole
from app.dependencies.auth import get_current_user, require_super_admin
from app.schemas.common import PaginatedResponse, PaginationParams
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
    
    - FAMILY_ADMIN users must have a director_id
    - VENDOR users must have a vendor_id
    - profit_percentage is only valid for DIRECTOR users
    - Password must be at least 8 characters
    """
    user_service = UserManagementService(db)
    
    try:
        user = await user_service.create(
            email=user_data.email,
            password=user_data.password,
            role=user_data.role,
            full_name=user_data.full_name,
            director_id=user_data.director_id,
            funeral_home_id=user_data.funeral_home_id,
            vendor_id=user_data.vendor_id,
            profit_percentage=user_data.profit_percentage
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


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    funeral_home_id: Optional[UUID] = Query(None, description="Filter by funeral home (SUPER_ADMIN)"),
    unassigned: Optional[bool] = Query(
        None,
        description="True returns users with no funeral home, e.g. directors awaiting assignment",
    ),
    search: Optional[str] = Query(None, description="Search email and full name"),
    include_inactive: bool = False,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List users with role-based filtering.
    
    - SUPER_ADMIN: all users, filterable by role, funeral home and assignment state
    - DIRECTOR: only their own family admins
    - FAMILY_ADMIN / VENDOR: only themselves
    """
    user_service = UserManagementService(db)
    
    if current_user.role == UserRole.SUPER_ADMIN.value:
        users, total = await user_service.get_all(
            role=role,
            include_inactive=include_inactive,
            funeral_home_id=funeral_home_id,
            unassigned=unassigned,
            search=search,
            offset=pagination.offset,
            limit=pagination.limit,
        )
        return PaginatedResponse.build(
            items=[UserResponse.model_validate(user) for user in users],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )
    
    if current_user.role == UserRole.DIRECTOR.value:
        users = await user_service.get_director_family_admins(current_user.id)
        return PaginatedResponse.build(
            items=[UserResponse.model_validate(user) for user in users],
            total=len(users),
            page=1,
            page_size=max(len(users), 1),
        )
    
    if current_user.role in {UserRole.FAMILY_ADMIN.value, UserRole.VENDOR.value}:
        return PaginatedResponse.build(
            items=[UserResponse.model_validate(current_user)],
            total=1,
            page=1,
            page_size=1,
        )
    
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
    - DIRECTOR: Can only view their assigned family admins
    - FAMILY_ADMIN / VENDOR: Can only view their own profile
    """
    user_service = UserManagementService(db)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return UserResponse.model_validate(user)
    
    if current_user.role == UserRole.DIRECTOR.value:
        if user.director_id == current_user.id and user.role == UserRole.FAMILY_ADMIN.value:
            return UserResponse.model_validate(user)
        if user.id == current_user.id:
            return UserResponse.model_validate(user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your assigned family admins"
        )
    
    if current_user.role in {UserRole.FAMILY_ADMIN.value, UserRole.VENDOR.value}:
        if user.id == current_user.id:
            return UserResponse.model_validate(user)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile"
        )
    
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
    
    - Can update email, full_name, role, is_active, director_id, funeral_home_id,
      vendor_id, profit_percentage and password
    - Email must be unique
    - FAMILY_ADMIN users must have a director_id
    """
    user_service = UserManagementService(db)
    
    try:
        user = await user_service.update(
            user_id=user_id,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role,
            is_active=user_data.is_active,
            director_id=user_data.director_id,
            funeral_home_id=user_data.funeral_home_id,
            vendor_id=user_data.vendor_id,
            password=user_data.password,
            profit_percentage=user_data.profit_percentage,
            profit_percentage_provided="profit_percentage" in user_data.model_fields_set,
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
