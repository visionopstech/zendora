from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.user import User
from app.dependencies.auth import require_super_admin
from app.schemas.vendor import VendorCreate, VendorUpdate, VendorResponse
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductWithVendors,
    AssociateVendorsRequest
)
from app.services.vendor_service import VendorService
from app.services.product_service import ProductService
from app.core.exceptions import NotFoundException, ValidationError

router = APIRouter()


# Vendor Endpoints
@router.post("/vendors", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
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


@router.get("/vendors", response_model=List[VendorResponse])
async def list_vendors(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """List all vendors (SUPER_ADMIN only)."""
    vendor_service = VendorService(db)
    vendors = await vendor_service.get_all(include_inactive=include_inactive)
    
    return [VendorResponse.model_validate(v) for v in vendors]


@router.get("/vendors/{vendor_id}", response_model=VendorResponse)
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


@router.put("/vendors/{vendor_id}", response_model=VendorResponse)
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


# Product Endpoints
@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Create a new product (SUPER_ADMIN only)."""
    product_service = ProductService(db)

    try:
        product = await product_service.create(
            name=product_data.name,
            description=product_data.description,
            base_price=product_data.base_price,
            price=product_data.price,
            images=product_data.images
        )
        
        await db.commit()
        
        return ProductResponse.model_validate(product)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.get("/products", response_model=List[ProductResponse])
async def list_products(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """List all products (SUPER_ADMIN only)."""
    product_service = ProductService(db)
    products = await product_service.get_all(include_inactive=include_inactive)
    
    return [ProductResponse.model_validate(p) for p in products]


@router.get("/products/{product_id}", response_model=ProductWithVendors)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Get product by ID with vendors (SUPER_ADMIN only)."""
    product_service = ProductService(db)
    product = await product_service.get_by_id(product_id, load_vendors=True)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    vendor_ids = [assoc.vendor_id for assoc in product.vendor_associations]
    
    response_data = ProductResponse.model_validate(product).model_dump()
    response_data["vendor_ids"] = vendor_ids
    
    return ProductWithVendors(**response_data)


@router.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    product_data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Update product (SUPER_ADMIN only)."""
    product_service = ProductService(db)
    
    try:
        product = await product_service.update(
            product_id=product_id,
            name=product_data.name,
            description=product_data.description,
            base_price=product_data.base_price,
            price=product_data.price,
            images=product_data.images,
            is_active=product_data.is_active
        )
        
        await db.commit()
        
        return ProductResponse.model_validate(product)
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.post("/products/{product_id}/vendors", response_model=ProductWithVendors)
async def associate_product_vendors(
    product_id: UUID,
    request: AssociateVendorsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Associate vendors with a product (SUPER_ADMIN only)."""
    product_service = ProductService(db)
    
    try:
        product = await product_service.associate_vendors(
            product_id=product_id,
            vendor_ids=request.vendor_ids
        )
        
        await db.commit()
        
        vendor_ids = [assoc.vendor_id for assoc in product.vendor_associations]
        
        response_data = ProductResponse.model_validate(product).model_dump()
        response_data["vendor_ids"] = vendor_ids
        
        return ProductWithVendors(**response_data)
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
