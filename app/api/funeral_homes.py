from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ConflictError, NotFoundException, PermissionDenied
from app.dependencies.auth import get_current_user, require_director, require_super_admin
from app.models.funeral_home import FuneralHome
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse, PaginationParams, UserRef
from app.schemas.funeral_home import (
    AssignDirectorRequest,
    FuneralHomeCreate,
    FuneralHomeResponse,
    FuneralHomeUpdate,
)
from app.services.funeral_home_service import FuneralHomeService

router = APIRouter()


async def _build_response(
    service: FuneralHomeService,
    funeral_home: FuneralHome,
) -> FuneralHomeResponse:
    """Serialize a funeral home together with its director and family count."""
    response = FuneralHomeResponse.model_validate(funeral_home)
    response.director = (
        UserRef.model_validate(funeral_home.director) if funeral_home.director else None
    )
    response.family_count = await service.count_families(funeral_home.id)
    return response


def _assert_can_read(current_user: User, funeral_home: FuneralHome) -> None:
    """Super admins see every funeral home, directors only their own."""
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return
    if (
        current_user.role == UserRole.DIRECTOR.value
        and current_user.funeral_home_id == funeral_home.id
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access this funeral home",
    )


@router.post("", response_model=FuneralHomeResponse, status_code=status.HTTP_201_CREATED)
async def create_funeral_home(
    funeral_home_data: FuneralHomeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Create a funeral home (SUPER_ADMIN only), optionally assigning a director."""
    service = FuneralHomeService(db)

    try:
        funeral_home = await service.create(
            name=funeral_home_data.name,
            description=funeral_home_data.description,
            email=funeral_home_data.email,
            phone=funeral_home_data.phone,
            address=funeral_home_data.address.model_dump() if funeral_home_data.address else None,
            logo_url=funeral_home_data.logo_url,
            director_id=funeral_home_data.director_id,
        )
        await db.commit()
        funeral_home = await service.get_by_id(funeral_home.id)
        return await _build_response(service, funeral_home)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=PaginatedResponse[FuneralHomeResponse])
async def list_funeral_homes(
    search: Optional[str] = Query(None, description="Search name, email and description"),
    is_active: Optional[bool] = Query(None),
    has_director: Optional[bool] = Query(
        None, description="True returns only funeral homes that already have a director"
    ),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List funeral homes.
    
    - SUPER_ADMIN: all funeral homes
    - DIRECTOR: only the funeral home they are assigned to
    """
    if current_user.role not in {UserRole.SUPER_ADMIN.value, UserRole.DIRECTOR.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to list funeral homes",
        )

    service = FuneralHomeService(db)

    ids = None
    if current_user.role == UserRole.DIRECTOR.value:
        ids = [current_user.funeral_home_id] if current_user.funeral_home_id else []

    funeral_homes, total = await service.list_funeral_homes(
        search=search,
        is_active=is_active,
        has_director=has_director,
        ids=ids,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    items = [await _build_response(service, funeral_home) for funeral_home in funeral_homes]
    return PaginatedResponse.build(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/me", response_model=FuneralHomeResponse)
async def get_my_funeral_home(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_director),
):
    """
    Get the funeral home of the authenticated director.
    
    Returns 409 while the director has not been assigned to a funeral home yet.
    """
    if not current_user.funeral_home_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Director is not assigned to a funeral home yet",
        )

    service = FuneralHomeService(db)
    funeral_home = await service.get_by_id(current_user.funeral_home_id)
    if not funeral_home:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral home not found",
        )

    return await _build_response(service, funeral_home)


@router.get("/{funeral_home_id}", response_model=FuneralHomeResponse)
async def get_funeral_home(
    funeral_home_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a funeral home by ID (SUPER_ADMIN, or the assigned DIRECTOR)."""
    service = FuneralHomeService(db)
    funeral_home = await service.get_by_id(funeral_home_id)

    if not funeral_home:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral home not found",
        )

    _assert_can_read(current_user, funeral_home)
    return await _build_response(service, funeral_home)


@router.put("/{funeral_home_id}", response_model=FuneralHomeResponse)
async def update_funeral_home(
    funeral_home_id: UUID,
    funeral_home_data: FuneralHomeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a funeral home.
    
    - SUPER_ADMIN: any funeral home, including is_active
    - DIRECTOR: only their own funeral home, and not is_active
    """
    service = FuneralHomeService(db)
    funeral_home = await service.get_by_id(funeral_home_id)

    if not funeral_home:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Funeral home not found",
        )

    _assert_can_read(current_user, funeral_home)

    is_active = funeral_home_data.is_active
    if is_active is not None and current_user.role != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can activate or deactivate a funeral home",
        )

    try:
        updated = await service.update(
            funeral_home_id=funeral_home_id,
            name=funeral_home_data.name,
            description=funeral_home_data.description,
            email=funeral_home_data.email,
            phone=funeral_home_data.phone,
            address=funeral_home_data.address.model_dump() if funeral_home_data.address else None,
            logo_url=funeral_home_data.logo_url,
            is_active=is_active,
        )
        await db.commit()
        updated = await service.get_by_id(updated.id)
        return await _build_response(service, updated)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{funeral_home_id}", response_model=FuneralHomeResponse)
async def deactivate_funeral_home(
    funeral_home_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Deactivate a funeral home (SUPER_ADMIN only). This is a soft delete."""
    service = FuneralHomeService(db)

    try:
        funeral_home = await service.deactivate(funeral_home_id)
        await db.commit()
        funeral_home = await service.get_by_id(funeral_home.id)
        return await _build_response(service, funeral_home)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{funeral_home_id}/director", response_model=FuneralHomeResponse)
async def assign_director(
    funeral_home_id: UUID,
    request: AssignDirectorRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """
    Assign a director to a funeral home (SUPER_ADMIN only).
    
    The user must have the DIRECTOR role and must not already run another
    funeral home. The funeral home is cascaded onto that director's existing
    families and gift collections.
    """
    service = FuneralHomeService(db)

    try:
        funeral_home = await service.assign_director(funeral_home_id, request.user_id)
        await db.commit()
        funeral_home = await service.get_by_id(funeral_home.id)
        return await _build_response(service, funeral_home)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{funeral_home_id}/director", response_model=FuneralHomeResponse)
async def unassign_director(
    funeral_home_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Remove the director from a funeral home (SUPER_ADMIN only)."""
    service = FuneralHomeService(db)

    try:
        funeral_home = await service.unassign_director(funeral_home_id)
        await db.commit()
        funeral_home = await service.get_by_id(funeral_home.id)
        return await _build_response(service, funeral_home)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
