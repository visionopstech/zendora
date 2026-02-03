from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.schemas.wishlist import WishlistPublicResponse, ProductInWishlist, WishlistCustomization
from app.services.wishlist_service import WishlistService
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
        products=products
    )
