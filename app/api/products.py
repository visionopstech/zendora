from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.user import User
from app.dependencies.auth import require_super_admin
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductWithVendors,
    AssociateVendorsRequest
)
from app.services.product_service import ProductService
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.post("", response_model=ProductWithVendors, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Create a new product (SUPER_ADMIN only).
    
    Optionally associate vendors with the product in a single operation
    by providing vendor_ids in the request body.
    """
    product_service = ProductService(db)
    
    try:
        # If vendor_ids provided, create product with vendors
        if product_data.vendor_ids:
            product = await product_service.create_with_vendors(
                name=product_data.name,
                description=product_data.description,
                price=product_data.price,
                images=product_data.images,
                vendor_ids=product_data.vendor_ids
            )
        else:
            # Otherwise, create product without vendors
            product = await product_service.create(
                name=product_data.name,
                description=product_data.description,
                price=product_data.price,
                images=product_data.images
            )
        
        await db.commit()
        
        # Prepare response with vendor IDs
        vendor_ids = [assoc.vendor_id for assoc in product.vendor_associations]
        response_data = ProductResponse.model_validate(product).model_dump()
        response_data["vendor_ids"] = vendor_ids
        
        return ProductWithVendors(**response_data)
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("", response_model=List[ProductWithVendors])
async def list_products(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """List all products with vendor IDs (SUPER_ADMIN only)."""
    product_service = ProductService(db)
    products = await product_service.get_all(include_inactive=include_inactive, load_vendors=True)
    
    # Build response with vendor IDs for each product
    result = []
    for product in products:
        vendor_ids = [assoc.vendor_id for assoc in product.vendor_associations]
        
        response_data = ProductResponse.model_validate(product).model_dump()
        response_data["vendor_ids"] = vendor_ids
        result.append(ProductWithVendors(**response_data))
    
    return result


@router.get("/{product_id}", response_model=ProductWithVendors)
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


@router.put("/{product_id}", response_model=ProductWithVendors)
@router.patch("/{product_id}", response_model=ProductWithVendors)
async def update_product(
    product_id: UUID,
    product_data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Update product (SUPER_ADMIN only).
    
    Supports both PUT and PATCH methods for partial updates.
    Only provide the fields you want to update.
    
    If vendor_ids is provided, it will replace all existing vendor associations.
    """
    product_service = ProductService(db)
    
    try:
        # Update basic product fields
        product = await product_service.update(
            product_id=product_id,
            name=product_data.name,
            description=product_data.description,
            price=product_data.price,
            images=product_data.images,
            is_active=product_data.is_active
        )
        
        # Update vendor associations if provided
        if product_data.vendor_ids is not None:
            product = await product_service.associate_vendors(
                product_id=product_id,
                vendor_ids=product_data.vendor_ids
            )
        
        await db.commit()
        
        # Load vendors for response
        product = await product_service.get_by_id(product_id, load_vendors=True)
        vendor_ids = [assoc.vendor_id for assoc in product.vendor_associations]
        
        response_data = ProductResponse.model_validate(product).model_dump()
        response_data["vendor_ids"] = vendor_ids
        
        return ProductWithVendors(**response_data)
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/{product_id}/vendors", response_model=ProductWithVendors)
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


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """Delete product (SUPER_ADMIN only)."""
    product_service = ProductService(db)
    
    try:
        await product_service.delete(product_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
