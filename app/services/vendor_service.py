from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional, List

from app.models.vendor import Vendor
from app.core.exceptions import NotFoundException, ConflictError


class VendorService:
    """Service for vendor-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, vendor_id: UUID) -> Optional[Vendor]:
        """Get vendor by ID."""
        result = await self.db.execute(
            select(Vendor).where(Vendor.id == vendor_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, include_inactive: bool = False) -> List[Vendor]:
        """Get all vendors."""
        query = select(Vendor)
        
        if not include_inactive:
            query = query.where(Vendor.is_active == True)
        
        query = query.order_by(Vendor.name)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def create(
        self,
        name: str,
        description: Optional[str] = None,
        logo_url: Optional[str] = None
    ) -> Vendor:
        """Create a new vendor."""
        vendor = Vendor(
            name=name,
            description=description,
            logo_url=logo_url,
            is_active=True
        )
        
        self.db.add(vendor)
        await self.db.flush()
        await self.db.refresh(vendor)
        
        return vendor
    
    async def update(
        self,
        vendor_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        logo_url: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Vendor:
        """Update a vendor."""
        vendor = await self.get_by_id(vendor_id)
        
        if not vendor:
            raise NotFoundException("Vendor not found")
        
        if name is not None:
            vendor.name = name
        if description is not None:
            vendor.description = description
        if logo_url is not None:
            vendor.logo_url = logo_url
        if is_active is not None:
            vendor.is_active = is_active
        
        await self.db.flush()
        await self.db.refresh(vendor)
        
        return vendor
    
    async def delete(self, vendor_id: UUID) -> None:
        """Delete a vendor."""
        vendor = await self.get_by_id(vendor_id)
        
        if not vendor:
            raise NotFoundException("Vendor not found")
        
        await self.db.delete(vendor)
        await self.db.flush()
