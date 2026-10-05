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


COLLECTION_ROLES = {
    UserRole.SUPER_ADMIN.value,
    UserRole.DIRECTOR.value,
    UserRole.FAMILY_ADMIN.value,
}


def _assert_role_allowed(current_user: User, action: str) -> None:
    if current_user.role not in COLLECTION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to {action} default gift collections",
        )


async def _assert_can_write(
    service: DefaultGiftCollectionService,
    current_user: User,
    default_collection: DefaultGiftCollection,
) -> None:
    """Only the owner, or someone managing that owner, may modify a default."""
    if await service.can_manage_owner(current_user, default_collection.owner_level_id):
        return

    if await service.can_read(current_user, default_collection):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This default gift collection belongs to a user above you "
                "and is read-only"
            ),
        )

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to modify this default gift collection",
    )


def _build_response(
    default_collection: DefaultGiftCollection,
    can_edit: bool,
    current_user: User,
) -> DefaultGiftCollectionResponse:
    """Serialize a default and tell the caller whether it is theirs to edit."""
    response = DefaultGiftCollectionResponse.model_validate(default_collection)
    response.can_edit = can_edit
    response.is_inherited = (
        not can_edit and default_collection.owner_level_id != current_user.id
    )
    return response


async def _build_responses(
    service: DefaultGiftCollectionService,
    current_user: User,
    collections: List[DefaultGiftCollection],
) -> List[DefaultGiftCollectionResponse]:
    manageable: dict[Optional[UUID], bool] = {}
    responses = []

    for collection in collections:
        owner_level_id = collection.owner_level_id
        if owner_level_id not in manageable:
            manageable[owner_level_id] = await service.can_manage_owner(
                current_user, owner_level_id
            )
        responses.append(
            _build_response(collection, manageable[owner_level_id], current_user)
        )

    return responses


@router.post("", response_model=DefaultGiftCollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_default_gift_collection(
    collection_data: DefaultGiftCollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a default gift collection.

    Defaults belong to a single user. A SUPER_ADMIN creates Zendora defaults,
    which sit at the top of every hierarchy; a DIRECTOR creates their own. Pass
    `owner_user_id` to create a default owned by a user you are responsible
    for, such as one of your family admins.
    """
    service = DefaultGiftCollectionService(db)

    if current_user.role == UserRole.DIRECTOR.value:
        owner_user_id = collection_data.owner_user_id or current_user.id
    elif current_user.role == UserRole.SUPER_ADMIN.value:
        owner_user_id = collection_data.owner_user_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create default gift collections",
        )

    if not await service.can_manage_owner(current_user, owner_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create default gift collections for this user",
        )

    owner_scope = (
        DefaultCollectionScope.ZENDORA
        if owner_user_id is None
        else DefaultCollectionScope.FUNERAL_HOME
    )

    try:
        default_collection = await service.create(
            created_by=current_user.id,
            name=collection_data.name,
            owner_scope=owner_scope,
            owner_user_id=owner_user_id,
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
        return _build_response(default_collection, True, current_user)
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
    owner_user_id: Optional[UUID] = Query(
        None, description="List the defaults owned by one user you manage"
    ),
    include_inactive: bool = Query(False),
    search: Optional[str] = Query(None, description="Search name, description and title"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List default gift collections, scoped by role.

    - SUPER_ADMIN: everything, filterable by scope, funeral home and owner
    - DIRECTOR and FAMILY_ADMIN: their own defaults, or those of the nearest
      user above them in the hierarchy when they have none of their own. A
      family admin falls back to their director, a director to the main
      director, and a main director to Zendora.

    Pass `owner_user_id` to inspect the defaults of a single user you are
    responsible for, such as one of your family admins. Each item carries
    `can_edit` and `is_inherited` so the UI can hide editing on inherited ones.
    """
    _assert_role_allowed(current_user, "view")
    service = DefaultGiftCollectionService(db)

    if owner_user_id is not None and not await service.can_manage_owner(
        current_user, owner_user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this user's default gift collections",
        )

    if current_user.role == UserRole.SUPER_ADMIN.value:
        collections, total = await service.list_collections(
            owner_scope=owner_scope,
            funeral_home_ids=[funeral_home_id] if funeral_home_id else None,
            owner_user_id=owner_user_id,
            active_only=not include_inactive,
            search=search,
            offset=pagination.offset,
            limit=pagination.limit,
        )
        return PaginatedResponse.build(
            items=await _build_responses(service, current_user, collections),
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    if owner_user_id is not None:
        resolved = await service.list_owned_by(
            owner_user_id,
            active_only=not include_inactive,
        )
    else:
        resolved = await service.resolve_for_user(
            current_user,
            active_only=not include_inactive,
        )

    if owner_scope:
        resolved = [item for item in resolved if item.owner_scope == owner_scope.value]
    if search:
        needle = search.lower()
        resolved = [
            item
            for item in resolved
            if needle in (item.name or "").lower()
            or needle in (item.description or "").lower()
            or needle in (item.collection_title or "").lower()
        ]

    page_items = resolved[pagination.offset : pagination.offset + pagination.limit]
    return PaginatedResponse.build(
        items=await _build_responses(service, current_user, page_items),
        total=len(resolved),
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{default_collection_id}", response_model=DefaultGiftCollectionResponse)
async def get_default_gift_collection(
    default_collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a default gift collection by ID: the caller's own, an upper hand's, or a managed user's."""
    _assert_role_allowed(current_user, "view")
    service = DefaultGiftCollectionService(db)
    default_collection = await service.get_by_id(default_collection_id, load_products=True)

    if not default_collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default gift collection not found",
        )

    if not await service.can_read(current_user, default_collection):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this default gift collection",
        )

    can_edit = await service.can_manage_owner(
        current_user, default_collection.owner_level_id
    )
    return _build_response(default_collection, can_edit, current_user)


@router.put("/{default_collection_id}", response_model=DefaultGiftCollectionResponse)
async def update_default_gift_collection(
    default_collection_id: UUID,
    collection_data: DefaultGiftCollectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a default gift collection. Inherited ones are read-only."""
    service = DefaultGiftCollectionService(db)
    default_collection = await service.get_by_id(default_collection_id)

    if not default_collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default gift collection not found",
        )

    await _assert_can_write(service, current_user, default_collection)

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
        return _build_response(updated, True, current_user)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{default_collection_id}", response_model=DefaultGiftCollectionResponse)
async def deactivate_default_gift_collection(
    default_collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a default gift collection. Inherited ones are read-only. This is a soft delete."""
    service = DefaultGiftCollectionService(db)
    default_collection = await service.get_by_id(default_collection_id)

    if not default_collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default gift collection not found",
        )

    await _assert_can_write(service, current_user, default_collection)

    try:
        await service.deactivate(default_collection_id)
        await db.commit()

        updated = await service.get_by_id(default_collection_id, load_products=True)
        return _build_response(updated, True, current_user)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
