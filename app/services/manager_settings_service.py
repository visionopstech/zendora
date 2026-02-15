from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional

from app.models.manager_settings import ManagerSettings
from app.core.exceptions import NotFoundException, ConflictError


class ManagerSettingsService:
    """Service for manager settings operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_manager_id(self, manager_id: UUID) -> Optional[ManagerSettings]:
        """Get settings for a manager."""
        result = await self.db.execute(
            select(ManagerSettings).where(ManagerSettings.manager_id == manager_id)
        )
        return result.scalar_one_or_none()
    
    async def create(
        self,
        manager_id: UUID,
        logo_url: Optional[str] = None,
        banner_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> ManagerSettings:
        """Create new manager settings."""
        # Check if settings already exist
        existing = await self.get_by_manager_id(manager_id)
        if existing:
            raise ConflictError("Manager settings already exist. Use update instead.")
        
        settings = ManagerSettings(
            manager_id=manager_id,
            logo_url=logo_url,
            banner_image_url=banner_image_url,
            primary_color=primary_color,
            secondary_color=secondary_color,
            custom_message=custom_message
        )
        
        self.db.add(settings)
        await self.db.flush()
        await self.db.refresh(settings)
        
        return settings
    
    async def update(
        self,
        manager_id: UUID,
        logo_url: Optional[str] = None,
        banner_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> ManagerSettings:
        """Update manager settings."""
        settings = await self.get_by_manager_id(manager_id)
        
        if not settings:
            raise NotFoundException("Manager settings not found")
        
        if logo_url is not None:
            settings.logo_url = logo_url
        if banner_image_url is not None:
            settings.banner_image_url = banner_image_url
        if primary_color is not None:
            settings.primary_color = primary_color
        if secondary_color is not None:
            settings.secondary_color = secondary_color
        if custom_message is not None:
            settings.custom_message = custom_message
        
        await self.db.flush()
        await self.db.refresh(settings)
        
        return settings
    
    async def delete(self, manager_id: UUID) -> None:
        """Delete manager settings."""
        settings = await self.get_by_manager_id(manager_id)
        
        if not settings:
            raise NotFoundException("Manager settings not found")
        
        await self.db.delete(settings)
        await self.db.flush()
