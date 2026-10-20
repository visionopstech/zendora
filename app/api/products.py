from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional

from app.core.database import get_db
from app.models.product import Product
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


def _require_product_write_access(current_user: User = Depends(get_current_user)) -> User:
    """Allow SUPER_ADMIN, VENDOR, or DIRECTOR to create and mutate gifts."""
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return current_user
    if current_user.role == UserRole.VENDOR.value and current_user.vendor_id:
        return current_user
    if current_user.role == UserRole.DIRECTOR.value:
        return current_user
    raise PermissionDenied("This action requires SUPER_ADMIN, DIRECTOR, or VENDOR role")


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


def _serialize_product(
    product: Product,
    current_user: User,
    product_service: ProductService,
) -> ProductWithVendors:
    """Build the list/detail payload including vendor ids and can_edit."""
    vendor_ids = [assoc.vendor_id for assoc in product.vendor_associations]
    response_data = ProductResponse.model_validate(product).model_dump()
    response_data["vendor_ids"] = vendor_ids
    response_data["can_edit"] = product_service.can_edit(current_user, product)
    return ProductWithVendors(**response_data)


@router.post("", response_model=ProductWithVendors, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_product_write_access)
):
    """
    Create a new product.

    SUPER_ADMIN: Can create with any vendors (or none). Global catalog.
    VENDOR: Creates product and automatically associates with their vendor.
    DIRECTOR: Creates a gift scoped to their funeral home. vendor_ids are ignored.
    """
    product_service = ProductService(db)
    
    try:
        funeral_home_id = product_service.resolve_create_scope(current_user)
        vendor_ids = list(product_data.vendor_ids) if product_data.vendor_ids else []

        if current_user.role == UserRole.DIRECTOR.value:
            vendor_ids = []
        elif current_user.role == UserRole.VENDOR.value:
            if current_user.vendor_id not in vendor_ids:
                vendor_ids.append(current_user.vendor_id)
            vendor_ids = [vid for vid in vendor_ids if vid == current_user.vendor_id]
        
        if vendor_ids:
            product = await product_service.create_with_vendors(
                name=product_data.name,
                base_price=product_data.base_price,
                description=product_data.description,
                details=product_data.details,
                price=product_data.price,
                images=_images_payload(product_data.images),
                vendor_ids=vendor_ids,
                created_by=current_user.id,
            )
        else:
            if current_user.role == UserRole.VENDOR.value:
                product = await product_service.create_with_vendors(
                    name=product_data.name,
                    base_price=product_data.base_price,
                    description=product_data.description,
                    details=product_data.details,
                    price=product_data.price,
                    images=_images_payload(product_data.images),
                    vendor_ids=[current_user.vendor_id],
                    created_by=current_user.id,
                )
            else:
                product = await product_service.create(
                    name=product_data.name,
                    base_price=product_data.base_price,
                    description=product_data.description,
                    details=product_data.details,
                    price=product_data.price,
                    images=_images_payload(product_data.images),
                    funeral_home_id=funeral_home_id,
                    created_by=current_user.id,
                )
        
        await db.commit()
        product = await product_service.get_by_id(product.id, load_vendors=True)
        return _serialize_product(product, current_user, product_service)
    except PermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
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
    """List products visible to the caller. Vendors see only their own."""
    product_service = ProductService(db)
    vendor_id = current_user.vendor_id if current_user.role == UserRole.VENDOR.value else None
    products = await product_service.get_all(
        include_inactive=include_inactive,
        load_vendors=True,
        vendor_id=vendor_id,
        actor=current_user,
    )
    
    return [
        _serialize_product(product, current_user, product_service)
        for product in products
    ]


@router.get("/{product_id}", response_model=ProductWithVendors)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_product_list_access)
):
    """Get product by ID. Hidden (404) when outside the caller's catalog."""
    product_service = ProductService(db)
    product = await product_service.get_by_id(product_id, load_vendors=True)
    
    if not product or not product_service.can_read(current_user, product):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    return _serialize_product(product, current_user, product_service)


@router.put("/{product_id}", response_model=ProductWithVendors)
@router.patch("/{product_id}", response_model=ProductWithVendors)
async def update_product(
    product_id: UUID,
    product_data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_product_write_access)
):
    """
    Update product. VENDOR: only products from their vendor.
    DIRECTOR: only gifts belonging to their funeral home.

    Supports both PUT and PATCH methods for partial updates.
    If vendor_ids is provided (SUPER_ADMIN only), it replaces vendor associations.
    """
    product_service = ProductService(db)
    
    try:
        await _assert_can_manage_product(product_service, product_id, current_user)

        if current_user.role != UserRole.SUPER_ADMIN.value:
            product_data.vendor_ids = None
        
        product = await product_service.update(
            product_id=product_id,
            name=product_data.name,
            description=product_data.description,
            details=product_data.details,
            base_price=product_data.base_price,
            price=product_data.price,
            images=_images_payload(product_data.images),
            is_active=product_data.is_active
        )
        
        if product_data.vendor_ids is not None:
            product = await product_service.associate_vendors(
                product_id=product_id,
                vendor_ids=product_data.vendor_ids
            )
        
        await db.commit()
        
        product = await product_service.get_by_id(product_id, load_vendors=True)
        return _serialize_product(product, current_user, product_service)
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
        product = await product_service.get_by_id(product.id, load_vendors=True)
        return _serialize_product(product, current_user, product_service)
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
    product = await product_service.get_by_id(product_id, load_vendors=True)
    if not product or not product_service.can_edit(current_user, product):
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
    current_user: User = Depends(_require_product_write_access),
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
    current_user: User = Depends(_require_product_write_access),
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
    current_user: User = Depends(_require_product_write_access),
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
    current_user: User = Depends(_require_product_write_access),
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
    current_user: User = Depends(_require_product_write_access)
):
    """Delete product. VENDOR/DIRECTOR: only gifts they own."""
    product_service = ProductService(db)
    
    try:
        await _assert_can_manage_product(product_service, product_id, current_user)
        await product_service.delete(product_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
