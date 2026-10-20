from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException, PermissionDenied
from app.dependencies.auth import get_current_user
from app.models.banner_preset import BannerPreset
from app.models.user import User, UserRole
from app.schemas.banner_preset import (
    BannerPresetCreate,
    BannerPresetResponse,
    BannerPresetUpdate,
)
from app.schemas.common import PaginatedResponse, PaginationParams
from app.services.banner_preset_service import BannerPresetService

router = APIRouter()

BANNER_ROLES = {
    UserRole.SUPER_ADMIN.value,
    UserRole.DIRECTOR.value,
    UserRole.FAMILY_ADMIN.value,
}


def _assert_role_allowed(current_user: User, action: str) -> None:
    if current_user.role not in BANNER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to {action} default banners",
        )


def _assert_can_write(service: BannerPresetService, current_user: User, banner: BannerPreset) -> None:
    if service.can_edit(current_user, banner):
        return
    if service.can_read(current_user, banner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This default banner belongs to Zendora and is read-only",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to modify this default banner",
    )


def _build_response(
    banner: BannerPreset,
    current_user: User,
    service: BannerPresetService,
) -> BannerPresetResponse:
    response = BannerPresetResponse.model_validate(banner)
    response.can_edit = service.can_edit(current_user, banner)
    return response


def _build_responses(
    banners: List[BannerPreset],
    current_user: User,
    service: BannerPresetService,
) -> List[BannerPresetResponse]:
    return [_build_response(banner, current_user, service) for banner in banners]


@router.post("", response_model=BannerPresetResponse, status_code=status.HTTP_201_CREATED)
async def create_banner_preset(
    banner_data: BannerPresetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a default banner.

    Super admins create Zendora banners visible to every family. Directors
    create funeral-home banners visible to families of their home. Upload the
    image with POST /api/files first, then pass the returned URL as image_url.
    """
    service = BannerPresetService(db)
    try:
        owner_scope, funeral_home_id = service.resolve_create_scope(current_user)
        banner = await service.create(
            created_by=current_user.id,
            name=banner_data.name,
            image_url=banner_data.image_url,
            owner_scope=owner_scope,
            funeral_home_id=funeral_home_id,
            sort_order=banner_data.sort_order,
            is_active=banner_data.is_active,
        )
        await db.commit()
        banner = await service.get_by_id(banner.id)
        return _build_response(banner, current_user, service)
    except PermissionDenied as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.get("", response_model=PaginatedResponse[BannerPresetResponse])
async def list_banner_presets(
    include_inactive: bool = Query(False),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List default banners the caller may use.

    Families see active Zendora banners plus those of their funeral home.
    Directors see the same set (Zendora is read-only) and may include inactive
    rows they manage. Super admins see every banner.
    """
    _assert_role_allowed(current_user, "view")
    service = BannerPresetService(db)
    active_only = True
    if include_inactive and current_user.role in {
        UserRole.SUPER_ADMIN.value,
        UserRole.DIRECTOR.value,
    }:
        active_only = False

    banners, total = await service.list_for_user(
        current_user,
        active_only=active_only,
        offset=pagination.offset,
        limit=pagination.limit,
    )
    return PaginatedResponse.build(
        items=_build_responses(banners, current_user, service),
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{banner_id}", response_model=BannerPresetResponse)
async def get_banner_preset(
    banner_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get one default banner the caller is allowed to see."""
    _assert_role_allowed(current_user, "view")
    service = BannerPresetService(db)
    banner = await service.get_by_id(banner_id)
    if not banner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Banner preset not found",
        )
    if not service.can_read(current_user, banner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this default banner",
        )
    return _build_response(banner, current_user, service)


@router.put("/{banner_id}", response_model=BannerPresetResponse)
async def update_banner_preset(
    banner_id: UUID,
    banner_data: BannerPresetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a default banner. Zendora banners are read-only for directors."""
    service = BannerPresetService(db)
    banner = await service.get_by_id(banner_id)
    if not banner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Banner preset not found",
        )
    _assert_can_write(service, current_user, banner)

    try:
        updated = await service.update(
            banner_id,
            name=banner_data.name,
            image_url=banner_data.image_url,
            sort_order=banner_data.sort_order,
            is_active=banner_data.is_active,
        )
        await db.commit()
        return _build_response(updated, current_user, service)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{banner_id}", response_model=BannerPresetResponse)
async def deactivate_banner_preset(
    banner_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-deactivate a default banner. Existing collections keep their image URL."""
    service = BannerPresetService(db)
    banner = await service.get_by_id(banner_id)
    if not banner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Banner preset not found",
        )
    _assert_can_write(service, current_user, banner)

    try:
        updated = await service.deactivate(banner_id)
        await db.commit()
        return _build_response(updated, current_user, service)
    except NotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
