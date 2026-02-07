from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.core.config import settings
from app.schemas.wishlist import WishlistPublicResponse, ProductInWishlist, WishlistCustomization
from app.services.wishlist_service import WishlistService
from app.services.qr_service import QRCodeService
from app.models.wishlist import WishlistStatus

router = APIRouter()


@router.get("/{public_slug}", response_model=WishlistPublicResponse)
async def get_public_wishlist(
    public_slug: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get public wishlist by slug.
    
    This endpoint:
    - Is accessible without authentication
    - Only shows PUBLISHED wishlists
    - Returns 404 for DRAFT or non-existent wishlists
    - Does not expose sensitive data
    """
    wishlist_service = WishlistService(db)
    
    wishlist = await wishlist_service.get_by_slug(public_slug, load_products=True)
    
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    # Only show published wishlists
    if wishlist.status != WishlistStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    # Build customization object
    customization = WishlistCustomization(
        logo_url=wishlist.logo_url,
        header_image_url=wishlist.header_image_url,
        primary_color=wishlist.primary_color,
        secondary_color=wishlist.secondary_color
    )
    
    # Build products list
    products = []
    for wp in wishlist.products:
        product = wp.product
        products.append(ProductInWishlist(
            id=product.id,
            name=product.name,
            description=product.description,
            price=float(product.price),
            images=product.images if product.images else [],
            quantity=wp.quantity
        ))
    
    return WishlistPublicResponse(
        id=wishlist.id,
        title=wishlist.title,
        description=wishlist.description,
        customization=customization,
        products=products,
        qr_code_url=f"/w/{public_slug}/qr-code"
    )


@router.get("/{public_slug}/qr-code")
async def get_public_wishlist_qr_code(
    public_slug: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get QR code for a public wishlist.
    
    This endpoint:
    - Is accessible without authentication
    - Only works for PUBLISHED wishlists
    - Returns 404 for DRAFT or non-existent wishlists
    - Returns a PNG image that redirects to the frontend URL
    """
    wishlist_service = WishlistService(db)
    
    wishlist = await wishlist_service.get_by_slug(public_slug)
    
    if not wishlist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    # Only show published wishlists
    if wishlist.status != WishlistStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found"
        )
    
    # Generate QR code for frontend URL
    frontend_url = f"{settings.frontend_url}/w/{public_slug}"
    qr_buffer = QRCodeService.generate_qr_code(frontend_url)
    
    return StreamingResponse(
        qr_buffer,
        media_type="image/png",
        headers={
            "Content-Disposition": f"inline; filename=wishlist-{public_slug}-qr.png"
        }
    )
