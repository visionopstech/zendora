from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.models.user import User, UserRole
from app.dependencies.auth import get_current_user
from app.core.exceptions import PermissionDenied
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductWithVendors,
    AssociateVendorsRequest
)
from app.services.product_service import ProductService
from app.core.exceptions import NotFoundException, ValidationError

router = APIRouter()


def _require_super_admin_or_vendor(current_user: User = Depends(get_current_user)) -> User:
    """Allow SUPER_ADMIN or VENDOR (with vendor_id) to access."""
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return current_user
    if current_user.role == UserRole.VENDOR.value and current_user.vendor_id:
        return current_user
    raise PermissionDenied("This action requires SUPER_ADMIN or VENDOR role")


def _require_product_list_access(current_user: User = Depends(get_current_user)) -> User:
    """Allow back-office roles and vendor users to list products."""
    if current_user.role in {
        UserRole.SUPER_ADMIN.value,
        UserRole.MANAGER.value,
        UserRole.ADMIN.value,
    }:
        return current_user
    if current_user.role == UserRole.VENDOR.value and current_user.vendor_id:
        return current_user
    raise PermissionDenied("This action requires SUPER_ADMIN, MANAGER, ADMIN, or VENDOR role")


@router.post("", response_model=ProductWithVendors, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_super_admin_or_vendor)
):
    """
    Create a new product.
    
    SUPER_ADMIN: Can create with any vendors (or none).
    VENDOR: Creates product and automatically associates with their vendor.
    """
    product_service = ProductService(db)
    
    try:
        vendor_ids = list(product_data.vendor_ids) if product_data.vendor_ids else []
        
        # Vendor users can only associate their own vendor
        if current_user.role == UserRole.VENDOR.value:
            if current_user.vendor_id not in vendor_ids:
                vendor_ids.append(current_user.vendor_id)
            # Vendor can only add their vendor, not others
            vendor_ids = [vid for vid in vendor_ids if vid == current_user.vendor_id]
        
        # If vendor_ids provided, create product with vendors
        if vendor_ids:
            product = await product_service.create_with_vendors(
                name=product_data.name,
                base_price=product_data.base_price,
                description=product_data.description,
                price=product_data.price,
                images=product_data.images,
                vendor_ids=vendor_ids
            )
        else:
            # Super admin can create without vendors; vendor must have their vendor
            if current_user.role == UserRole.VENDOR.value:
                vendor_ids = [current_user.vendor_id]
                product = await product_service.create_with_vendors(
                    name=product_data.name,
                    base_price=product_data.base_price,
                    description=product_data.description,
                    price=product_data.price,
                    images=product_data.images,
                    vendor_ids=vendor_ids
                )
            else:
                product = await product_service.create(
                    name=product_data.name,
                    base_price=product_data.base_price,
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
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.get("", response_model=List[ProductWithVendors])
async def list_products(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_product_list_access)
):
    """List products. Back-office roles see all products; vendors see only their own."""
    product_service = ProductService(db)
    vendor_id = current_user.vendor_id if current_user.role == UserRole.VENDOR.value else None
    products = await product_service.get_all(
        include_inactive=include_inactive,
        load_vendors=True,
        vendor_id=vendor_id
    )
    
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
    current_user: User = Depends(_require_super_admin_or_vendor)
):
    """Get product by ID. VENDOR: only if product belongs to their vendor."""
    product_service = ProductService(db)
    product = await product_service.get_by_id(product_id, load_vendors=True)
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Vendor can only see products from their vendor
    if current_user.role == UserRole.VENDOR.value:
        belongs = await product_service.product_belongs_to_vendor(product_id, current_user.vendor_id)
        if not belongs:
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
    current_user: User = Depends(_require_super_admin_or_vendor)
):
    """
    Update product. VENDOR: only products from their vendor.
    
    Supports both PUT and PATCH methods for partial updates.
    If vendor_ids is provided (SUPER_ADMIN only), it replaces vendor associations.
    """
    product_service = ProductService(db)
    
    try:
        # Vendor can only update products from their vendor
        if current_user.role == UserRole.VENDOR.value:
            belongs = await product_service.product_belongs_to_vendor(product_id, current_user.vendor_id)
            if not belongs:
                raise NotFoundException("Product not found")
            # Vendor cannot change vendor associations
            product_data.vendor_ids = None
        
        # Update basic product fields
        product = await product_service.update(
            product_id=product_id,
            name=product_data.name,
            description=product_data.description,
            base_price=product_data.base_price,
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
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


@router.post("/{product_id}/vendors", response_model=ProductWithVendors)
async def associate_product_vendors(
    product_id: UUID,
    request: AssociateVendorsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_super_admin_or_vendor)
):
    """Associate vendors with a product. SUPER_ADMIN: replaces all. VENDOR: adds their vendor only."""
    product_service = ProductService(db)
    
    try:
        if current_user.role == UserRole.VENDOR.value:
            # Vendor can only add their vendor to a product (does not replace existing)
            product = await product_service.add_vendor_to_product(
                product_id=product_id,
                vendor_id=current_user.vendor_id
            )
        else:
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
    current_user: User = Depends(_require_super_admin_or_vendor)
):
    """Delete product. VENDOR: only products from their vendor."""
    product_service = ProductService(db)
    
    try:
        if current_user.role == UserRole.VENDOR.value:
            belongs = await product_service.product_belongs_to_vendor(product_id, current_user.vendor_id)
            if not belongs:
                raise NotFoundException("Product not found")
        await product_service.delete(product_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
