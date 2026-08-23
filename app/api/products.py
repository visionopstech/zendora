from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional

from app.core.database import get_db
from app.models.user import User, UserRole
from app.dependencies.auth import get_current_user
from app.core.exceptions import PermissionDenied
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductWithVendors,
    ProductImageInput,
    ProductImageResponse,
    ReorderImagesRequest,
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
        UserRole.DIRECTOR.value,
        UserRole.FAMILY_ADMIN.value,
    }:
        return current_user
    if current_user.role == UserRole.VENDOR.value and current_user.vendor_id:
        return current_user
    raise PermissionDenied(
        "This action requires SUPER_ADMIN, DIRECTOR, FAMILY_ADMIN, or VENDOR role"
    )


def _images_payload(images: Optional[List[ProductImageInput]]) -> Optional[List[dict]]:
    """Convert gallery input models into service payloads."""
    if images is None:
        return None
    return [image.model_dump() for image in images]


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
                images=_images_payload(product_data.images),
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
                    images=_images_payload(product_data.images),
                    vendor_ids=vendor_ids
                )
            else:
                product = await product_service.create(
                    name=product_data.name,
                    base_price=product_data.base_price,
                    description=product_data.description,
                    price=product_data.price,
                    images=_images_payload(product_data.images)
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
            images=_images_payload(product_data.images),
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


async def _assert_can_manage_product(
    product_service: ProductService,
    product_id: UUID,
    current_user: User,
) -> None:
    """Ensure the caller may mutate this gift (and its gallery)."""
    product = await product_service.get_by_id(product_id)
    if not product:
        raise NotFoundException("Gift not found")
    if current_user.role == UserRole.VENDOR.value:
        belongs = await product_service.product_belongs_to_vendor(
            product_id, current_user.vendor_id
        )
        if not belongs:
            raise NotFoundException("Gift not found")


@router.post(
    "/{product_id}/images",
    response_model=ProductImageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_product_image(
    product_id: UUID,
    image_data: ProductImageInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_super_admin_or_vendor),
):
    """Append an image to a gift's gallery. The first image is always primary."""
    product_service = ProductService(db)
    try:
        await _assert_can_manage_product(product_service, product_id, current_user)
        image = await product_service.add_image(
            product_id=product_id,
            url=image_data.url,
            alt_text=image_data.alt_text,
            is_primary=image_data.is_primary,
            sort_order=image_data.sort_order,
        )
        await db.commit()
        return ProductImageResponse.model_validate(image)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.delete("/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_image(
    product_id: UUID,
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_super_admin_or_vendor),
):
    """Remove a gallery image. If it was primary, the next image is promoted."""
    product_service = ProductService(db)
    try:
        await _assert_can_manage_product(product_service, product_id, current_user)
        await product_service.delete_image(product_id, image_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/{product_id}/images/reorder", response_model=List[ProductImageResponse])
async def reorder_product_images(
    product_id: UUID,
    request: ReorderImagesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_super_admin_or_vendor),
):
    """Reorder a gift's gallery. `image_ids` must list every existing image exactly once."""
    product_service = ProductService(db)
    try:
        await _assert_can_manage_product(product_service, product_id, current_user)
        images = await product_service.reorder_images(product_id, request.image_ids)
        await db.commit()
        return [ProductImageResponse.model_validate(image) for image in images]
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.put("/{product_id}/images/{image_id}/primary", response_model=ProductImageResponse)
async def set_primary_product_image(
    product_id: UUID,
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_super_admin_or_vendor),
):
    """Promote one gallery image to primary and demote the others."""
    product_service = ProductService(db)
    try:
        await _assert_can_manage_product(product_service, product_id, current_user)
        image = await product_service.set_primary_image(product_id, image_id)
        await db.commit()
        return ProductImageResponse.model_validate(image)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


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
