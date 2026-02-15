from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.models.user import User
from app.dependencies.auth import require_manager
from app.schemas.settings import (
    ManagerSettingsCreate,
    ManagerSettingsUpdate,
    ManagerSettingsResponse
)
from app.services.manager_settings_service import ManagerSettingsService
from app.core.exceptions import NotFoundException, ConflictError

router = APIRouter()


@router.get("/manager/settings", response_model=Optional[ManagerSettingsResponse])
async def get_manager_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Get current manager's settings (MANAGER only)."""
    service = ManagerSettingsService(db)
    settings = await service.get_by_manager_id(current_user.id)
    return settings


@router.post("/manager/settings", response_model=ManagerSettingsResponse, status_code=status.HTTP_201_CREATED)
async def create_manager_settings(
    settings_data: ManagerSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Create manager settings (MANAGER only). Can only be called once."""
    service = ManagerSettingsService(db)
    
    try:
        settings = await service.create(
            manager_id=current_user.id,
            logo_url=settings_data.logo_url,
            banner_image_url=settings_data.banner_image_url,
            primary_color=settings_data.primary_color,
            secondary_color=settings_data.secondary_color,
            custom_message=settings_data.custom_message
        )
        await db.commit()
        return settings
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.put("/manager/settings", response_model=ManagerSettingsResponse)
async def update_manager_settings(
    settings_data: ManagerSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Update manager settings (MANAGER only)."""
    service = ManagerSettingsService(db)
    
    try:
        settings = await service.update(
            manager_id=current_user.id,
            logo_url=settings_data.logo_url,
            banner_image_url=settings_data.banner_image_url,
            primary_color=settings_data.primary_color,
            secondary_color=settings_data.secondary_color,
            custom_message=settings_data.custom_message
        )
        await db.commit()
        return settings
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/manager/settings", status_code=status.HTTP_204_NO_CONTENT)
async def delete_manager_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """Delete manager settings (MANAGER only)."""
    service = ManagerSettingsService(db)
    
    try:
        await service.delete(current_user.id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
