from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional

from app.models.director_settings import DirectorSettings
from app.core.exceptions import NotFoundException, ConflictError


class DirectorSettingsService:
    """Service for director settings operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_director_id(self, director_id: UUID) -> Optional[DirectorSettings]:
        """Get settings for a director."""
        result = await self.db.execute(
            select(DirectorSettings).where(DirectorSettings.director_id == director_id)
        )
        return result.scalar_one_or_none()
    
    async def create(
        self,
        director_id: UUID,
        logo_url: Optional[str] = None,
        banner_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> DirectorSettings:
        """Create new director settings."""
        existing = await self.get_by_director_id(director_id)
        if existing:
            raise ConflictError("Director settings already exist. Use update instead.")
        
        settings = DirectorSettings(
            director_id=director_id,
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
        director_id: UUID,
        logo_url: Optional[str] = None,
        banner_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> DirectorSettings:
        """Update director settings."""
        settings = await self.get_by_director_id(director_id)
        
        if not settings:
            raise NotFoundException("Director settings not found")
        
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
    
    async def delete(self, director_id: UUID) -> None:
        """Delete director settings."""
        settings = await self.get_by_director_id(director_id)
        
        if not settings:
            raise NotFoundException("Director settings not found")
        
        await self.db.delete(settings)
        await self.db.flush()
