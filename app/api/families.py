from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.schemas.common import FuneralHomeRef, PaginatedResponse, PaginationParams, UserRef
from app.schemas.family import FamilyResponse
from app.services.family_service import FamilyService

router = APIRouter()


def _build_response(family: User, stats: dict) -> FamilyResponse:
    """Serialize a family admin together with its funeral home, director and stats."""
    return FamilyResponse(
        id=family.id,
        email=family.email,
        full_name=family.full_name,
        is_active=family.is_active,
        created_at=family.created_at,
        funeral_home=(
            FuneralHomeRef.model_validate(family.funeral_home) if family.funeral_home else None
        ),
        director=UserRef.model_validate(family.director) if family.director else None,
        gift_collection_count=stats.get("count", 0),
        published_collection_id=stats.get("published_id"),
        published_collection_slug=stats.get("published_slug"),
    )


@router.get("", response_model=PaginatedResponse[FamilyResponse])
async def list_families(
    funeral_home_id: Optional[UUID] = Query(
        None, description="Filter by funeral home (SUPER_ADMIN)"
    ),
    director_id: Optional[UUID] = Query(None, description="Filter by director"),
    search: Optional[str] = Query(None, description="Search email and full name"),
    is_active: Optional[bool] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List families (FAMILY_ADMIN users), scoped by role.
    
    - SUPER_ADMIN: all families, filterable by funeral home and director
    - DIRECTOR: only the families of their own funeral home
    """
    service = FamilyService(db)

    if current_user.role == UserRole.SUPER_ADMIN.value:
        scoped_funeral_home_id = funeral_home_id
        scoped_director_id = director_id
    elif current_user.role == UserRole.DIRECTOR.value:
        if current_user.funeral_home_id:
            scoped_funeral_home_id = current_user.funeral_home_id
            scoped_director_id = director_id
        else:
            # Not assigned to a funeral home yet: fall back to their own families.
            scoped_funeral_home_id = None
            scoped_director_id = current_user.id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to list families",
        )

    families, total = await service.list_families(
        funeral_home_id=scoped_funeral_home_id,
        director_id=scoped_director_id,
        search=search,
        is_active=is_active,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    stats = await service.get_collection_stats([family.id for family in families])
    items: List[FamilyResponse] = [
        _build_response(family, stats.get(family.id, {})) for family in families
    ]

    return PaginatedResponse.build(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{family_admin_id}", response_model=FamilyResponse)
async def get_family(
    family_admin_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a single family.
    
    - SUPER_ADMIN: any family
    - DIRECTOR: only families in their funeral home or assigned to them
    - FAMILY_ADMIN: only themselves
    """
    service = FamilyService(db)
    family = await service.get_by_id(family_admin_id)

    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        )

    if current_user.role == UserRole.SUPER_ADMIN.value:
        pass
    elif current_user.role == UserRole.DIRECTOR.value:
        same_funeral_home = (
            current_user.funeral_home_id is not None
            and family.funeral_home_id == current_user.funeral_home_id
        )
        if not (same_funeral_home or family.director_id == current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view families in your own funeral home",
            )
    elif current_user.role == UserRole.FAMILY_ADMIN.value:
        if family.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own family",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view families",
        )

    stats = await service.get_collection_stats([family.id])
    return _build_response(family, stats.get(family.id, {}))
