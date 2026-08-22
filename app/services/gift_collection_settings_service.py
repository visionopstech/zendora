from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional

from app.models.gift_collection_settings import GiftCollectionSettings
from app.core.exceptions import NotFoundException, ConflictError


class GiftCollectionSettingsService:
    """Service for gift collection settings operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_collection_id(
        self,
        gift_collection_id: UUID
    ) -> Optional[GiftCollectionSettings]:
        """Get settings for a gift collection."""
        result = await self.db.execute(
            select(GiftCollectionSettings).where(
                GiftCollectionSettings.gift_collection_id == gift_collection_id
            )
        )
        return result.scalar_one_or_none()
    
    async def create(
        self,
        gift_collection_id: UUID,
        banner_image_url: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> GiftCollectionSettings:
        """Create new gift collection settings."""
        existing = await self.get_by_collection_id(gift_collection_id)
        if existing:
            raise ConflictError("Gift collection settings already exist. Use update instead.")
        
        settings = GiftCollectionSettings(
            gift_collection_id=gift_collection_id,
            banner_image_url=banner_image_url,
            custom_message=custom_message
        )
        
        self.db.add(settings)
        await self.db.flush()
        await self.db.refresh(settings)
        
        return settings
    
    async def update(
        self,
        gift_collection_id: UUID,
        banner_image_url: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> GiftCollectionSettings:
        """Update gift collection settings."""
        settings = await self.get_by_collection_id(gift_collection_id)
        
        if not settings:
            raise NotFoundException("Gift collection settings not found")
        
        if banner_image_url is not None:
            settings.banner_image_url = banner_image_url
        if custom_message is not None:
            settings.custom_message = custom_message
        
        await self.db.flush()
        await self.db.refresh(settings)
        
        return settings
    
    async def delete(self, gift_collection_id: UUID) -> None:
        """Delete gift collection settings."""
        settings = await self.get_by_collection_id(gift_collection_id)
        
        if not settings:
            raise NotFoundException("Gift collection settings not found")
        
        await self.db.delete(settings)
        await self.db.flush()
