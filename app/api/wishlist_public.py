from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.gift_collection import GiftCollectionStatus
from app.schemas.gift_collection import (
    GiftCollectionCustomization,
    GiftCollectionPublicResponse,
    GiftInCollection,
)
from app.schemas.settings import CombinedSettingsResponse
from app.services.gift_collection_service import GiftCollectionService
from app.services.qr_service import QRCodeService

router = APIRouter()


@router.get("/{public_slug}", response_model=GiftCollectionPublicResponse)
async def get_public_gift_collection(
    public_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a public gift collection by slug.

    Accessible without authentication. Only PUBLISHED collections are returned;
    DRAFT and unknown slugs both produce 404 so drafts cannot be enumerated.
    """
    collection_service = GiftCollectionService(db)
    collection = await collection_service.get_by_slug(public_slug, load_products=True)

    if not collection or collection.status != GiftCollectionStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gift collection not found",
        )

    customization = GiftCollectionCustomization(
        logo_url=collection.logo_url,
        header_image_url=collection.header_image_url,
        primary_color=collection.primary_color,
        secondary_color=collection.secondary_color,
    )

    products = [
        GiftInCollection.from_collection_product(association)
        for association in collection.products
        if association.product
    ]

    return GiftCollectionPublicResponse(
        id=collection.id,
        title=collection.title,
        description=collection.description,
        customization=customization,
        products=products,
        qr_code_url=f"/w/{public_slug}/qr-code",
        settings=CombinedSettingsResponse(director=None, gift_collection=None),
    )


@router.get("/{public_slug}/qr-code")
async def get_public_gift_collection_qr_code(
    public_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the PNG QR code for a published gift collection.

    The QR code points at the frontend public page.
    """
    collection_service = GiftCollectionService(db)
    collection = await collection_service.get_by_slug(public_slug)

    if not collection or collection.status != GiftCollectionStatus.PUBLISHED.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gift collection not found",
        )

    frontend_url = f"{settings.frontend_url}/w/{public_slug}"
    qr_buffer = QRCodeService.generate_qr_code(frontend_url)

    return StreamingResponse(
        qr_buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename=gift-collection-{public_slug}-qr.png"
        },
    )
