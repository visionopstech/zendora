from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException, PermissionDenied
from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.schemas.wishlist_template import (
    WishlistTemplateCreate,
    WishlistTemplateResponse,
    WishlistTemplateUpdate,
)
from app.services.wishlist_template_service import WishlistTemplateService

router = APIRouter()


def _ensure_template_access(current_user: User, template_is_active: bool) -> None:
    """Allow super admins to access all templates and others only active ones."""

    if current_user.role == UserRole.SUPER_ADMIN.value:
        return

    if current_user.role in {UserRole.MANAGER.value, UserRole.ADMIN.value} and template_is_active:
        return

    raise PermissionDenied("You do not have permission to access this wishlist template")


@router.post("", response_model=WishlistTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_wishlist_template(
    template_data: WishlistTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new wishlist template (SUPER_ADMIN only)."""

    if current_user.role != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can create wishlist templates",
        )

    template_service = WishlistTemplateService(db)
    products = [
        {"product_id": product.product_id, "quantity": product.quantity}
        for product in template_data.products
    ]
    delivery_address = (
        template_data.delivery_address.model_dump() if template_data.delivery_address else None
    )

    try:
        template = await template_service.create(
            created_by=current_user.id,
            name=template_data.name,
            description=template_data.description,
            wishlist_title=template_data.wishlist_title,
            wishlist_description=template_data.wishlist_description,
            logo_url=template_data.logo_url,
            header_image_url=template_data.header_image_url,
            primary_color=template_data.primary_color,
            secondary_color=template_data.secondary_color,
            delivery_address=delivery_address,
            is_active=template_data.is_active,
            products=products,
        )
        await db.commit()
        template = await template_service.get_by_id(template.id, load_products=True)
        return WishlistTemplateResponse.model_validate(template)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("", response_model=List[WishlistTemplateResponse])
async def list_wishlist_templates(
    include_inactive: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List wishlist templates."""

    if current_user.role not in {
        UserRole.SUPER_ADMIN.value,
        UserRole.MANAGER.value,
        UserRole.ADMIN.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view wishlist templates",
        )

    template_service = WishlistTemplateService(db)
    active_only = not (
        current_user.role == UserRole.SUPER_ADMIN.value and include_inactive
    )
    templates = await template_service.list_templates(
        active_only=active_only,
        load_products=True,
    )
    return [WishlistTemplateResponse.model_validate(template) for template in templates]


@router.get("/{template_id}", response_model=WishlistTemplateResponse)
async def get_wishlist_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a wishlist template."""

    template_service = WishlistTemplateService(db)
    template = await template_service.get_by_id(template_id, load_products=True)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist template not found")

    try:
        _ensure_template_access(current_user, template.is_active)
    except PermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    return WishlistTemplateResponse.model_validate(template)


@router.put("/{template_id}", response_model=WishlistTemplateResponse)
async def update_wishlist_template(
    template_id: UUID,
    template_data: WishlistTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a wishlist template (SUPER_ADMIN only)."""

    if current_user.role != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can update wishlist templates",
        )

    template_service = WishlistTemplateService(db)
    delivery_address = (
        template_data.delivery_address.model_dump() if template_data.delivery_address else None
    )
    products = None
    if "products" in template_data.model_fields_set:
        products = [
            {"product_id": product.product_id, "quantity": product.quantity}
            for product in (template_data.products or [])
        ]

    try:
        template = await template_service.update(
            template_id=template_id,
            name=template_data.name,
            description=template_data.description,
            wishlist_title=template_data.wishlist_title,
            wishlist_description=template_data.wishlist_description,
            logo_url=template_data.logo_url,
            header_image_url=template_data.header_image_url,
            primary_color=template_data.primary_color,
            secondary_color=template_data.secondary_color,
            delivery_address=delivery_address,
            is_active=template_data.is_active,
            products=products,
        )
        await db.commit()
        template = await template_service.get_by_id(template.id, load_products=True)
        return WishlistTemplateResponse.model_validate(template)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wishlist_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a wishlist template (SUPER_ADMIN only)."""

    if current_user.role != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admins can deactivate wishlist templates",
        )

    template_service = WishlistTemplateService(db)
    try:
        await template_service.deactivate(template_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
