from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.models.user import User
from app.dependencies.auth import require_director
from app.schemas.settings import (
    DirectorSettingsCreate,
    DirectorSettingsUpdate,
    DirectorSettingsResponse,
)
from app.services.director_settings_service import DirectorSettingsService
from app.core.exceptions import NotFoundException, ConflictError

router = APIRouter()


@router.get("/director/settings", response_model=Optional[DirectorSettingsResponse])
async def get_director_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_director),
):
    """Get the authenticated director's settings."""
    service = DirectorSettingsService(db)
    return await service.get_by_director_id(current_user.id)


@router.post(
    "/director/settings",
    response_model=DirectorSettingsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_director_settings(
    settings_data: DirectorSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_director),
):
    """Create director settings. Can only be called once."""
    service = DirectorSettingsService(db)

    try:
        settings = await service.create(
            director_id=current_user.id,
            logo_url=settings_data.logo_url,
            banner_image_url=settings_data.banner_image_url,
            primary_color=settings_data.primary_color,
            secondary_color=settings_data.secondary_color,
            custom_message=settings_data.custom_message,
        )
        await db.commit()
        return settings
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.put("/director/settings", response_model=DirectorSettingsResponse)
async def update_director_settings(
    settings_data: DirectorSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_director),
):
    """Update director settings."""
    service = DirectorSettingsService(db)

    try:
        settings = await service.update(
            director_id=current_user.id,
            logo_url=settings_data.logo_url,
            banner_image_url=settings_data.banner_image_url,
            primary_color=settings_data.primary_color,
            secondary_color=settings_data.secondary_color,
            custom_message=settings_data.custom_message,
        )
        await db.commit()
        return settings
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/director/settings", status_code=status.HTTP_204_NO_CONTENT)
async def delete_director_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_director),
):
    """Delete director settings."""
    service = DirectorSettingsService(db)

    try:
        await service.delete(current_user.id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
