from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ConflictError, NotFoundException, PermissionDenied
from app.dependencies.auth import get_current_user, require_super_admin_or_director
from app.models.user import User, UserRole
from app.schemas.common import DeliveryAddress, FuneralHomeRef, PaginatedResponse, PaginationParams, UserRef
from app.schemas.family import FamilyCreate, FamilyResponse, FamilyUpdate
from app.services.director_scope import director_can_read_family, director_data_scope
from app.services.family_service import FamilyService
from app.services.funeral_home_service import FuneralHomeService
from app.services.user_service import UserService

router = APIRouter()


async def _resolve_family_assignment(
    current_user: User,
    family_data: FamilyCreate,
    user_service: UserService,
) -> tuple[Optional[UUID], Optional[UUID]]:
    """
    Decide which director and funeral home a new family should be assigned to.

    Directors are always assigned to themselves and their funeral home.
    Super admins may omit both, or supply either; a director without an
    explicit funeral home inherits that director's home.
    """
    if current_user.role == UserRole.DIRECTOR.value:
        if not current_user.funeral_home_id:
            raise ConflictError("Director is not assigned to a funeral home yet")
        return current_user.id, current_user.funeral_home_id

    if current_user.role != UserRole.SUPER_ADMIN.value:
        raise PermissionDenied("This action requires one of the following roles: SUPER_ADMIN, DIRECTOR")

    director_id = family_data.director_id
    funeral_home_id = family_data.funeral_home_id
    director = None

    if director_id:
        director = await user_service.get_by_id(director_id)
        if not director:
            raise NotFoundException("Director not found")
        if director.role != UserRole.DIRECTOR.value:
            raise PermissionDenied("Specified director_id must belong to a DIRECTOR user")

    if funeral_home_id:
        funeral_home = await FuneralHomeService(user_service.db).get_by_id(funeral_home_id)
        if not funeral_home:
            raise NotFoundException("Funeral home not found")
    elif director:
        funeral_home_id = director.funeral_home_id

    return director_id, funeral_home_id


def _assert_can_access_family(current_user: User, family: User, *, action: str) -> None:
    """Raise 403 unless the caller may view or update this family."""
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return
    if current_user.role == UserRole.DIRECTOR.value:
        if not director_can_read_family(current_user, family):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You can only {action} families assigned to you",
            )
        return
    if current_user.role == UserRole.FAMILY_ADMIN.value:
        if family.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You can only {action} your own family",
            )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"You do not have permission to {action} families",
    )


def _build_response(family: User, stats: dict) -> FamilyResponse:
    """Serialize a family admin together with its funeral home, director and stats."""
    address = None
    if family.address:
        address = DeliveryAddress.model_validate(family.address)
    return FamilyResponse(
        id=family.id,
        email=family.email,
        first_name=family.first_name,
        last_name=family.last_name,
        deceased_first_name=family.deceased_first_name,
        deceased_last_name=family.deceased_last_name,
        address=address,
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


@router.post("", response_model=FamilyResponse, status_code=status.HTTP_201_CREATED)
async def create_family(
    family_data: FamilyCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin_or_director),
):
    """
    Create a family admin account (SUPER_ADMIN or DIRECTOR).

    Directors are assigned to themselves and their funeral home.
    Super admins may omit director and funeral home, or supply either.
    Does not create a gift collection. Credentials are emailed to the family.
    """
    user_service = UserService(db)
    director_id, funeral_home_id = await _resolve_family_assignment(
        current_user, family_data, user_service
    )

    existing = await user_service.get_by_email(family_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    family, password = await user_service.create_family_admin_with_director(
        email=family_data.email,
        first_name=family_data.first_name,
        last_name=family_data.last_name,
        director_id=director_id,
        funeral_home_id=funeral_home_id,
        deceased_first_name=family_data.deceased_first_name,
        deceased_last_name=family_data.deceased_last_name,
        address=family_data.address.model_dump(),
    )
    await db.commit()

    from app.services.email_service import EmailService

    email_service = EmailService()
    background_tasks.add_task(
        email_service.send_family_admin_credentials_email,
        family,
        password,
    )

    service = FamilyService(db)
    family = await service.get_by_id(family.id)
    stats = await service.get_collection_stats([family.id])
    return _build_response(family, stats.get(family.id, {}))


@router.get("", response_model=PaginatedResponse[FamilyResponse])
async def list_families(
    funeral_home_id: Optional[UUID] = Query(
        None, description="Filter by funeral home (SUPER_ADMIN)"
    ),
    director_id: Optional[UUID] = Query(None, description="Filter by director"),
    search: Optional[str] = Query(None, description="Search email, name and deceased name"),
    is_active: Optional[bool] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List families (FAMILY_ADMIN users), scoped by role.
    
    - SUPER_ADMIN: all families, filterable by funeral home and director
    - Main director: all families of their funeral home
    - Other director: only families they oversee
    """
    service = FamilyService(db)

    if current_user.role == UserRole.SUPER_ADMIN.value:
        scoped_funeral_home_id = funeral_home_id
        scoped_director_id = director_id
    elif current_user.role == UserRole.DIRECTOR.value:
        scope = director_data_scope(current_user)
        scoped_funeral_home_id = scope.funeral_home_id
        scoped_director_id = scope.director_id
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
    - Main director: families in their funeral home
    - Other director: only families they oversee
    - FAMILY_ADMIN: only themselves
    """
    service = FamilyService(db)
    family = await service.get_by_id(family_admin_id)

    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        )

    _assert_can_access_family(current_user, family, action="view")

    stats = await service.get_collection_stats([family.id])
    return _build_response(family, stats.get(family.id, {}))


@router.patch("/{family_admin_id}", response_model=FamilyResponse)
async def update_family(
    family_admin_id: UUID,
    family_data: FamilyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Partially update a family.

    - SUPER_ADMIN: any family
    - Main director: families in their funeral home
    - Other director: only families they oversee
    - FAMILY_ADMIN: only themselves (cannot change is_active)
    """
    service = FamilyService(db)
    family = await service.get_by_id(family_admin_id)

    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found",
        )

    _assert_can_access_family(current_user, family, action="update")

    is_active = family_data.is_active
    if is_active is not None and current_user.role == UserRole.FAMILY_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Family admins cannot change their active status",
        )

    try:
        family = await service.update(
            family_admin_id=family_admin_id,
            first_name=family_data.first_name,
            last_name=family_data.last_name,
            email=family_data.email,
            deceased_first_name=family_data.deceased_first_name,
            deceased_last_name=family_data.deceased_last_name,
            address=family_data.address.model_dump() if family_data.address else None,
            is_active=is_active,
        )
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    family = await service.get_by_id(family.id)
    stats = await service.get_collection_stats([family.id])
    return _build_response(family, stats.get(family.id, {}))
