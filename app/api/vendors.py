from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.user import User
from app.dependencies.auth import require_super_admin
from app.schemas.vendor import VendorCreate, VendorUpdate, VendorResponse
from app.services.vendor_service import VendorService
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    vendor_data: VendorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Create a new vendor (SUPER_ADMIN only)."""
    vendor_service = VendorService(db)
    
    vendor = await vendor_service.create(
        name=vendor_data.name,
        description=vendor_data.description,
        logo_url=vendor_data.logo_url
    )
    
    await db.commit()
    
    return VendorResponse.model_validate(vendor)


@router.get("", response_model=List[VendorResponse])
async def list_vendors(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """List all vendors (SUPER_ADMIN only)."""
    vendor_service = VendorService(db)
    vendors = await vendor_service.get_all(include_inactive=include_inactive)
    
    return [VendorResponse.model_validate(v) for v in vendors]


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get vendor by ID (SUPER_ADMIN only)."""
    vendor_service = VendorService(db)
    vendor = await vendor_service.get_by_id(vendor_id)
    
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found"
        )
    
    return VendorResponse.model_validate(vendor)


@router.put("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: UUID,
    vendor_data: VendorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Update vendor (SUPER_ADMIN only)."""
    vendor_service = VendorService(db)
    
    try:
        vendor = await vendor_service.update(
            vendor_id=vendor_id,
            name=vendor_data.name,
            description=vendor_data.description,
            logo_url=vendor_data.logo_url,
            is_active=vendor_data.is_active
        )
        
        await db.commit()
        
        return VendorResponse.model_validate(vendor)
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Delete vendor (SUPER_ADMIN only)."""
    vendor_service = VendorService(db)
    
    try:
        await vendor_service.delete(vendor_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
