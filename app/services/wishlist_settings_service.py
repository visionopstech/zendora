from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional

from app.models.wishlist_settings import WishlistSettings
from app.core.exceptions import NotFoundException, ConflictError


class WishlistSettingsService:
    """Service for wishlist settings operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_wishlist_id(self, wishlist_id: UUID) -> Optional[WishlistSettings]:
        """Get settings for a wishlist."""
        result = await self.db.execute(
            select(WishlistSettings).where(WishlistSettings.wishlist_id == wishlist_id)
        )
        return result.scalar_one_or_none()
    
    async def create(
        self,
        wishlist_id: UUID,
        banner_image_url: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> WishlistSettings:
        """Create new wishlist settings."""
        # Check if settings already exist
        existing = await self.get_by_wishlist_id(wishlist_id)
        if existing:
            raise ConflictError("Wishlist settings already exist. Use update instead.")
        
        settings = WishlistSettings(
            wishlist_id=wishlist_id,
            banner_image_url=banner_image_url,
            custom_message=custom_message
        )
        
        self.db.add(settings)
        await self.db.flush()
        await self.db.refresh(settings)
        
        return settings
    
    async def update(
        self,
        wishlist_id: UUID,
        banner_image_url: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> WishlistSettings:
        """Update wishlist settings."""
        settings = await self.get_by_wishlist_id(wishlist_id)
        
        if not settings:
            raise NotFoundException("Wishlist settings not found")
        
        if banner_image_url is not None:
            settings.banner_image_url = banner_image_url
        if custom_message is not None:
            settings.custom_message = custom_message
        
        await self.db.flush()
        await self.db.refresh(settings)
        
        return settings
    
    async def delete(self, wishlist_id: UUID) -> None:
        """Delete wishlist settings."""
        settings = await self.get_by_wishlist_id(wishlist_id)
        
        if not settings:
            raise NotFoundException("Wishlist settings not found")
        
        await self.db.delete(settings)
        await self.db.flush()
