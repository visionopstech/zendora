from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException, PermissionDenied
from app.dependencies.auth import get_current_user
from app.models.default_gift_collection import DefaultCollectionScope, DefaultGiftCollection
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.default_gift_collection import (
    DefaultGiftCollectionCreate,
    DefaultGiftCollectionResponse,
    DefaultGiftCollectionUpdate,
)
from app.services.default_gift_collection_service import DefaultGiftCollectionService

router = APIRouter()


def _serialize_products(products) -> Optional[List[dict]]:
    """Convert gift request objects into service payloads."""
    if products is None:
        return None

    return [
        {"product_id": product.product_id, "quantity": product.quantity}
        for product in products
    ]


def _assert_can_write(current_user: User, default_collection: DefaultGiftCollection) -> None:
    """Only the owning scope may modify a default collection."""
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return

    if current_user.role == UserRole.DIRECTOR.value:
        is_own_funeral_home_default = (
            default_collection.owner_scope == DefaultCollectionScope.FUNERAL_HOME.value
            and current_user.funeral_home_id is not None
            and default_collection.funeral_home_id == current_user.funeral_home_id
        )
        if is_own_funeral_home_default:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Directors can only modify their own funeral home's default gift collections",
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to modify default gift collections",
    )


def _can_read(current_user: User, default_collection: DefaultGiftCollection) -> bool:
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return True

    if default_collection.owner_scope == DefaultCollectionScope.ZENDORA.value:
        return current_user.role in {
            UserRole.DIRECTOR.value,
            UserRole.FAMILY_ADMIN.value,
        }

    return (
        current_user.funeral_home_id is not None
        and default_collection.funeral_home_id == current_user.funeral_home_id
    )


@router.post("", response_model=DefaultGiftCollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_default_gift_collection(
    collection_data: DefaultGiftCollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a default gift collection.
    
    The owner scope follows the caller: a SUPER_ADMIN creates Zendora defaults
    available to everyone, a DIRECTOR creates defaults for their own funeral
    home. A director without a funeral home gets a 409.
    """
    if current_user.role == UserRole.SUPER_ADMIN.value:
        owner_scope = DefaultCollectionScope.ZENDORA
        funeral_home_id = None
    elif current_user.role == UserRole.DIRECTOR.value:
        if not current_user.funeral_home_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Director is not assigned to a funeral home yet",
            )
        owner_scope = DefaultCollectionScope.FUNERAL_HOME
        funeral_home_id = current_user.funeral_home_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create default gift collections",
        )

    service = DefaultGiftCollectionService(db)

    try:
        default_collection = await service.create(
            created_by=current_user.id,
            name=collection_data.name,
            owner_scope=owner_scope,
            funeral_home_id=funeral_home_id,
            description=collection_data.description,
            collection_title=collection_data.collection_title,
            collection_description=collection_data.collection_description,
            logo_url=collection_data.logo_url,
            header_image_url=collection_data.header_image_url,
            primary_color=collection_data.primary_color,
            secondary_color=collection_data.secondary_color,
            delivery_address=(
                collection_data.delivery_address.model_dump()
                if collection_data.delivery_address
                else None
            ),
            is_active=collection_data.is_active,
            products=_serialize_products(collection_data.products) or [],
        )
        await db.commit()

        default_collection = await service.get_by_id(default_collection.id, load_products=True)
        return DefaultGiftCollectionResponse.model_validate(default_collection)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=PaginatedResponse[DefaultGiftCollectionResponse])
async def list_default_gift_collections(
    owner_scope: Optional[DefaultCollectionScope] = Query(
        None, description="ZENDORA or FUNERAL_HOME"
    ),
    funeral_home_id: Optional[UUID] = Query(
        None, description="Filter funeral-home defaults by funeral home (SUPER_ADMIN)"
    ),
    include_inactive: bool = Query(False),
    search: Optional[str] = Query(None, description="Search name, description and title"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List default gift collections, scoped by role.
    
    - SUPER_ADMIN: everything, filterable by scope and funeral home
    - DIRECTOR: Zendora defaults plus their own funeral home's defaults
    - FAMILY_ADMIN: the resolved set they may pick from, which is their funeral
      home's defaults when it has any, otherwise the Zendora defaults. Each item
      carries `owner_scope` so the UI can label the source.
    """
    service = DefaultGiftCollectionService(db)

    if current_user.role == UserRole.FAMILY_ADMIN.value:
        resolved = await service.resolve_for_family_admin(
            current_user,
            active_only=not include_inactive,
        )
        if owner_scope:
            resolved = [
                item for item in resolved if item.owner_scope == owner_scope.value
            ]
        if search:
            needle = search.lower()
            resolved = [
                item
                for item in resolved
                if needle in (item.name or "").lower()
                or needle in (item.description or "").lower()
                or needle in (item.collection_title or "").lower()
            ]

        total = len(resolved)
        page_items = resolved[pagination.offset : pagination.offset + pagination.limit]
        return PaginatedResponse.build(
            items=[
                DefaultGiftCollectionResponse.model_validate(item) for item in page_items
            ],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    if current_user.role == UserRole.SUPER_ADMIN.value:
        funeral_home_ids = [funeral_home_id] if funeral_home_id else None
    elif current_user.role == UserRole.DIRECTOR.value:
        funeral_home_ids = (
            [current_user.funeral_home_id] if current_user.funeral_home_id else []
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view default gift collections",
        )

    collections, total = await service.list_collections(
        owner_scope=owner_scope,
        funeral_home_ids=funeral_home_ids,
        active_only=not include_inactive,
        search=search,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse.build(
        items=[
            DefaultGiftCollectionResponse.model_validate(collection)
            for collection in collections
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{default_collection_id}", response_model=DefaultGiftCollectionResponse)
async def get_default_gift_collection(
    default_collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a default gift collection by ID, subject to scope visibility."""
    service = DefaultGiftCollectionService(db)
    default_collection = await service.get_by_id(default_collection_id, load_products=True)

    if not default_collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default gift collection not found",
        )

    if not _can_read(current_user, default_collection):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this default gift collection",
        )

    return DefaultGiftCollectionResponse.model_validate(default_collection)


@router.put("/{default_collection_id}", response_model=DefaultGiftCollectionResponse)
async def update_default_gift_collection(
    default_collection_id: UUID,
    collection_data: DefaultGiftCollectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a default gift collection (owning scope only)."""
    service = DefaultGiftCollectionService(db)
    default_collection = await service.get_by_id(default_collection_id)

    if not default_collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default gift collection not found",
        )

    _assert_can_write(current_user, default_collection)

    try:
        await service.update(
            default_collection_id=default_collection_id,
            name=collection_data.name,
            description=collection_data.description,
            collection_title=collection_data.collection_title,
            collection_description=collection_data.collection_description,
            logo_url=collection_data.logo_url,
            header_image_url=collection_data.header_image_url,
            primary_color=collection_data.primary_color,
            secondary_color=collection_data.secondary_color,
            delivery_address=(
                collection_data.delivery_address.model_dump()
                if collection_data.delivery_address
                else None
            ),
            is_active=collection_data.is_active,
            products=_serialize_products(collection_data.products),
        )
        await db.commit()

        updated = await service.get_by_id(default_collection_id, load_products=True)
        return DefaultGiftCollectionResponse.model_validate(updated)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{default_collection_id}", response_model=DefaultGiftCollectionResponse)
async def deactivate_default_gift_collection(
    default_collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a default gift collection (owning scope only). This is a soft delete."""
    service = DefaultGiftCollectionService(db)
    default_collection = await service.get_by_id(default_collection_id)

    if not default_collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default gift collection not found",
        )

    _assert_can_write(current_user, default_collection)

    try:
        await service.deactivate(default_collection_id)
        await db.commit()

        updated = await service.get_by_id(default_collection_id, load_products=True)
        return DefaultGiftCollectionResponse.model_validate(updated)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
