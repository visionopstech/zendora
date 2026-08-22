from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.core.database import get_db
from app.core.exceptions import ConflictError, NotFoundException, PermissionDenied
from app.dependencies.auth import get_current_user
from app.models.gift_collection import GiftCollection, GiftCollectionStatus
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.gift_collection import (
    AddGiftsListRequest,
    GiftCollectionCreate,
    GiftCollectionCreateByFamilyAdmin,
    GiftCollectionResponse,
    GiftCollectionUpdate,
    UpdateGiftCollectionProductsRequest,
)
from app.schemas.settings import (
    GiftCollectionSettingsCreate,
    GiftCollectionSettingsResponse,
    GiftCollectionSettingsUpdate,
)
from app.services.default_gift_collection_service import DefaultGiftCollectionService
from app.services.gift_collection_service import GiftCollectionService
from app.services.gift_collection_settings_service import GiftCollectionSettingsService
from app.services.qr_service import QRCodeService
from app.services.user_service import UserService

router = APIRouter()


def _serialize_products(products) -> Optional[List[dict]]:
    """Convert gift request objects into service payloads."""
    if products is None:
        return None

    return [
        {"product_id": product.product_id, "quantity": product.quantity}
        for product in products
    ]


def _build_response(collection: GiftCollection) -> GiftCollectionResponse:
    response = GiftCollectionResponse.model_validate(collection)
    response.qr_code_url = f"/api/gift-collections/{collection.id}/qr-code"
    return response


def _can_read(current_user: User, collection: GiftCollection) -> bool:
    """Super admin reads everything, a director their funeral home, a family their own."""
    if current_user.role == UserRole.SUPER_ADMIN.value:
        return True
    if current_user.role == UserRole.DIRECTOR.value:
        return collection.director_id == current_user.id or (
            current_user.funeral_home_id is not None
            and collection.funeral_home_id == current_user.funeral_home_id
        )
    if current_user.role == UserRole.FAMILY_ADMIN.value:
        return collection.family_admin_id == current_user.id
    return False


async def _load_collection(
    service: GiftCollectionService,
    collection_id: UUID,
    current_user: User,
    load_products: bool = False,
) -> GiftCollection:
    collection = await service.get_by_id(collection_id, load_products=load_products)

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gift collection not found",
        )

    if not _can_read(current_user, collection):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this gift collection",
        )

    return collection


async def _resolve_default_collection(
    default_service: DefaultGiftCollectionService,
    default_collection_id: UUID,
    current_user: User,
):
    """Load a default collection and verify the caller may build from it."""
    default_collection = await default_service.get_by_id(
        default_collection_id, load_products=True
    )

    if not default_collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Default gift collection not found",
        )

    if not default_collection.is_active and current_user.role != UserRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Default gift collection is inactive",
        )

    if current_user.role == UserRole.FAMILY_ADMIN.value:
        applicable = await default_service.is_applicable_to_family_admin(
            current_user, default_collection
        )
        if not applicable:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This default gift collection is not available to you",
            )

    return default_collection


@router.post("", response_model=GiftCollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_gift_collection(
    collection_data: GiftCollectionCreate | GiftCollectionCreateByFamilyAdmin,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a gift collection, optionally copied from a default gift collection.
    
    - DIRECTOR: creates for a family (requires family_admin_email and
      family_admin_full_name). A new family admin account is created and its
      credentials are emailed.
    - FAMILY_ADMIN: creates their own collection
    - SUPER_ADMIN: creates for an existing family admin
    
    Pass `default_collection_id` to copy a default collection; any field sent
    explicitly overrides the copied value.
    """
    collection_service = GiftCollectionService(db)
    default_service = DefaultGiftCollectionService(db)
    user_service = UserService(db)

    new_family_admin: Optional[tuple[User, str]] = None

    try:
        if current_user.role == UserRole.DIRECTOR.value:
            if not isinstance(collection_data, GiftCollectionCreate):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Directors must provide family_admin_email and family_admin_full_name",
                )

            family_admin = await user_service.get_by_email(collection_data.family_admin_email)
            if not family_admin:
                family_admin, password = await user_service.create_family_admin_with_director(
                    email=collection_data.family_admin_email,
                    full_name=collection_data.family_admin_full_name,
                    director_id=current_user.id,
                    funeral_home_id=current_user.funeral_home_id,
                )
                new_family_admin = (family_admin, password)
            elif family_admin.director_id != current_user.id:
                raise PermissionDenied("This family admin belongs to another director")

            family_admin_id = family_admin.id
            director_id = current_user.id
            funeral_home_id = current_user.funeral_home_id

        elif current_user.role == UserRole.FAMILY_ADMIN.value:
            if not current_user.director_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Family admin must be assigned to a director before creating gift collections",
                )
            family_admin_id = current_user.id
            director_id = current_user.director_id
            funeral_home_id = current_user.funeral_home_id

        elif current_user.role == UserRole.SUPER_ADMIN.value:
            if not isinstance(collection_data, GiftCollectionCreate):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Super admins must provide family_admin_email",
                )

            family_admin = await user_service.get_by_email(collection_data.family_admin_email)
            if not family_admin:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Family admin not found",
                )
            if not family_admin.director_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Family admin must be assigned to a director before creating gift collections",
                )
            family_admin_id = family_admin.id
            director_id = family_admin.director_id
            funeral_home_id = family_admin.funeral_home_id

        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to create gift collections",
            )

        delivery_address = (
            collection_data.delivery_address.model_dump()
            if collection_data.delivery_address
            else None
        )
        products = _serialize_products(collection_data.products)

        if collection_data.default_collection_id:
            default_collection = await _resolve_default_collection(
                default_service, collection_data.default_collection_id, current_user
            )

            collection = await collection_service.create_from_default_collection(
                family_admin_id=family_admin_id,
                director_id=director_id,
                funeral_home_id=funeral_home_id,
                source_default_collection_id=default_collection.id,
                default_collection_data=default_service.build_collection_payload(
                    default_collection
                ),
                overrides={
                    "title": collection_data.title,
                    "description": collection_data.description,
                    "logo_url": collection_data.logo_url,
                    "header_image_url": collection_data.header_image_url,
                    "primary_color": collection_data.primary_color,
                    "secondary_color": collection_data.secondary_color,
                    "delivery_address": delivery_address,
                    "products": products,
                },
                override_fields=set(collection_data.model_fields_set),
            )
        elif products:
            collection = await collection_service.create_with_products(
                family_admin_id=family_admin_id,
                director_id=director_id,
                funeral_home_id=funeral_home_id,
                products=products,
                title=collection_data.title,
                description=collection_data.description,
                logo_url=collection_data.logo_url,
                header_image_url=collection_data.header_image_url,
                primary_color=collection_data.primary_color,
                secondary_color=collection_data.secondary_color,
                delivery_address=delivery_address,
            )
        else:
            collection = await collection_service.create(
                family_admin_id=family_admin_id,
                director_id=director_id,
                funeral_home_id=funeral_home_id,
                title=collection_data.title,
                description=collection_data.description,
                logo_url=collection_data.logo_url,
                header_image_url=collection_data.header_image_url,
                primary_color=collection_data.primary_color,
                secondary_color=collection_data.secondary_color,
                delivery_address=delivery_address,
            )

        await db.commit()

        if new_family_admin:
            from app.services.email_service import EmailService

            email_service = EmailService()
            background_tasks.add_task(
                email_service.send_family_admin_credentials_email,
                new_family_admin[0],
                new_family_admin[1],
            )

        collection = await collection_service.get_by_id(collection.id, load_products=True)
        return _build_response(collection)

    except (NotFoundException, ConflictError, PermissionDenied) as e:
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail=str(e),
        )


@router.get("", response_model=PaginatedResponse[GiftCollectionResponse])
async def list_gift_collections(
    funeral_home_id: Optional[UUID] = Query(None, description="Filter by funeral home (SUPER_ADMIN)"),
    director_id: Optional[UUID] = Query(None, description="Filter by director"),
    family_admin_id: Optional[UUID] = Query(None, description="Filter by family admin"),
    collection_status: Optional[GiftCollectionStatus] = Query(
        None, alias="status", description="DRAFT or PUBLISHED"
    ),
    search: Optional[str] = Query(None, description="Search title, description and slug"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List gift collections, scoped by role.
    
    - SUPER_ADMIN: every collection, filterable by funeral home, director and family
    - DIRECTOR: only their own funeral home's collections
    - FAMILY_ADMIN: only their own collections
    """
    service = GiftCollectionService(db)

    if current_user.role == UserRole.SUPER_ADMIN.value:
        scoped_funeral_home_id = funeral_home_id
        scoped_director_id = director_id
        scoped_family_admin_id = family_admin_id
    elif current_user.role == UserRole.DIRECTOR.value:
        if current_user.funeral_home_id:
            scoped_funeral_home_id = current_user.funeral_home_id
            scoped_director_id = director_id
        else:
            # Not assigned to a funeral home yet: fall back to collections they own.
            scoped_funeral_home_id = None
            scoped_director_id = current_user.id
        scoped_family_admin_id = family_admin_id
    elif current_user.role == UserRole.FAMILY_ADMIN.value:
        scoped_funeral_home_id = None
        scoped_director_id = None
        scoped_family_admin_id = current_user.id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view gift collections",
        )

    collections, total = await service.list_collections(
        funeral_home_id=scoped_funeral_home_id,
        director_id=scoped_director_id,
        family_admin_id=scoped_family_admin_id,
        status=collection_status.value if collection_status else None,
        search=search,
        offset=pagination.offset,
        limit=pagination.limit,
    )

    return PaginatedResponse.build(
        items=[_build_response(collection) for collection in collections],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{gift_collection_id}", response_model=GiftCollectionResponse)
async def get_gift_collection(
    gift_collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a gift collection by ID (SUPER_ADMIN, its DIRECTOR, or its FAMILY_ADMIN)."""
    service = GiftCollectionService(db)
    collection = await _load_collection(
        service, gift_collection_id, current_user, load_products=True
    )
    return _build_response(collection)


@router.put("/{gift_collection_id}", response_model=GiftCollectionResponse)
async def update_gift_collection(
    gift_collection_id: UUID,
    collection_data: GiftCollectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a gift collection's content and customization."""
    service = GiftCollectionService(db)
    await _load_collection(service, gift_collection_id, current_user)

    delivery_address = (
        collection_data.delivery_address.model_dump()
        if collection_data.delivery_address
        else None
    )

    try:
        await service.update(
            gift_collection_id=gift_collection_id,
            title=collection_data.title,
            description=collection_data.description,
            logo_url=collection_data.logo_url,
            header_image_url=collection_data.header_image_url,
            primary_color=collection_data.primary_color,
            secondary_color=collection_data.secondary_color,
            delivery_address=delivery_address,
        )
        await db.commit()

        collection = await service.get_by_id(gift_collection_id, load_products=True)
        return _build_response(collection)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/{gift_collection_id}/products", response_model=GiftCollectionResponse)
async def replace_gift_collection_products(
    gift_collection_id: UUID,
    request: UpdateGiftCollectionProductsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Replace every gift in a collection."""
    service = GiftCollectionService(db)
    await _load_collection(service, gift_collection_id, current_user)

    try:
        await service.update_products(
            gift_collection_id=gift_collection_id,
            products=_serialize_products(request.products) or [],
        )
        await db.commit()

        collection = await service.get_by_id(gift_collection_id, load_products=True)
        return _build_response(collection)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{gift_collection_id}/products", response_model=GiftCollectionResponse)
async def add_gifts_to_collection(
    gift_collection_id: UUID,
    request: AddGiftsListRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add gifts to a collection, keeping the existing ones."""
    service = GiftCollectionService(db)
    await _load_collection(service, gift_collection_id, current_user)

    try:
        for gift in request.products:
            await service.add_product(
                gift_collection_id=gift_collection_id,
                product_id=gift.product_id,
                quantity=gift.quantity,
            )
        await db.commit()

        collection = await service.get_by_id(gift_collection_id, load_products=True)
        return _build_response(collection)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{gift_collection_id}/products/{product_id}", response_model=GiftCollectionResponse)
async def remove_gift_from_collection(
    gift_collection_id: UUID,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a single gift from a collection."""
    service = GiftCollectionService(db)
    await _load_collection(service, gift_collection_id, current_user)

    try:
        await service.remove_product(gift_collection_id, product_id)
        await db.commit()

        collection = await service.get_by_id(gift_collection_id, load_products=True)
        return _build_response(collection)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{gift_collection_id}/publish", response_model=GiftCollectionResponse)
async def publish_gift_collection(
    gift_collection_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Publish a gift collection (FAMILY_ADMIN owner or SUPER_ADMIN).
    
    A family admin may only have one published collection at a time. The
    director is notified by email.
    """
    service = GiftCollectionService(db)
    collection = await _load_collection(service, gift_collection_id, current_user)

    if current_user.role == UserRole.SUPER_ADMIN.value:
        family_admin_id = collection.family_admin_id
    elif current_user.role == UserRole.FAMILY_ADMIN.value:
        family_admin_id = current_user.id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the family admin owner or a super admin can publish a gift collection",
        )

    try:
        await service.publish(gift_collection_id, family_admin_id)
        await db.commit()

        collection = await service.get_by_id(gift_collection_id, load_products=True)

        if collection.director:
            from app.services.email_service import EmailService

            email_service = EmailService()
            background_tasks.add_task(
                email_service.send_gift_collection_published_email,
                collection,
                collection.director,
            )

        return _build_response(collection)
    except (ConflictError, PermissionDenied) as e:
        raise HTTPException(
            status_code=getattr(e, "status_code", status.HTTP_400_BAD_REQUEST),
            detail=str(e),
        )


@router.delete("/{gift_collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gift_collection(
    gift_collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a gift collection.
    
    WARNING: This is a hard delete and cascades to its gifts and orders.
    """
    service = GiftCollectionService(db)
    await _load_collection(service, gift_collection_id, current_user)

    try:
        await service.delete(gift_collection_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{gift_collection_id}/qr-code")
async def get_gift_collection_qr_code(
    gift_collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the PNG QR code that points at the public gift collection page."""
    service = GiftCollectionService(db)
    collection = await _load_collection(service, gift_collection_id, current_user)

    public_url = f"{app_settings.frontend_url}/w/{collection.public_slug}"
    qr_buffer = QRCodeService.generate_qr_code(public_url)

    return StreamingResponse(
        qr_buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": (
                f"inline; filename=gift-collection-{collection.public_slug}-qr.png"
            )
        },
    )


@router.get("/{gift_collection_id}/settings", response_model=Optional[GiftCollectionSettingsResponse])
async def get_gift_collection_settings(
    gift_collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the collection-level settings, or null when none exist yet."""
    service = GiftCollectionService(db)
    await _load_collection(service, gift_collection_id, current_user)

    settings_service = GiftCollectionSettingsService(db)
    return await settings_service.get_by_collection_id(gift_collection_id)


@router.post(
    "/{gift_collection_id}/settings",
    response_model=GiftCollectionSettingsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_gift_collection_settings(
    gift_collection_id: UUID,
    settings_data: GiftCollectionSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create the collection-level settings."""
    service = GiftCollectionService(db)
    await _load_collection(service, gift_collection_id, current_user)

    settings_service = GiftCollectionSettingsService(db)

    try:
        collection_settings = await settings_service.create(
            gift_collection_id=gift_collection_id,
            banner_image_url=settings_data.banner_image_url,
            custom_message=settings_data.custom_message,
        )
        await db.commit()
        return collection_settings
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.put("/{gift_collection_id}/settings", response_model=GiftCollectionSettingsResponse)
async def update_gift_collection_settings(
    gift_collection_id: UUID,
    settings_data: GiftCollectionSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the collection-level settings."""
    service = GiftCollectionService(db)
    await _load_collection(service, gift_collection_id, current_user)

    settings_service = GiftCollectionSettingsService(db)

    try:
        collection_settings = await settings_service.update(
            gift_collection_id=gift_collection_id,
            banner_image_url=settings_data.banner_image_url,
            custom_message=settings_data.custom_message,
        )
        await db.commit()
        return collection_settings
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{gift_collection_id}/settings", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gift_collection_settings(
    gift_collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete the collection-level settings."""
    service = GiftCollectionService(db)
    await _load_collection(service, gift_collection_id, current_user)

    settings_service = GiftCollectionSettingsService(db)

    try:
        await settings_service.delete(gift_collection_id)
        await db.commit()
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
