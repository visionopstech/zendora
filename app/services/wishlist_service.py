import secrets
import string
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, List

from app.models.wishlist import Wishlist, WishlistProduct, WishlistStatus
from app.models.product import Product
from app.models.user import User, UserRole
from app.core.exceptions import NotFoundException, ConflictError, PermissionDenied
from app.schemas.wishlist import DeliveryAddress


class WishlistService:
    """Service for wishlist-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _generate_slug(self, length: int = 12) -> str:
        """Generate a random URL-safe slug."""
        chars = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    async def _ensure_unique_slug(self) -> str:
        """Generate a unique slug for a wishlist."""
        max_attempts = 10
        for _ in range(max_attempts):
            slug = self._generate_slug()
            result = await self.db.execute(
                select(Wishlist).where(Wishlist.public_slug == slug)
            )
            if not result.scalar_one_or_none():
                return slug
        raise Exception("Failed to generate unique slug")
    
    async def get_by_id(
        self,
        wishlist_id: UUID,
        load_products: bool = False
    ) -> Optional[Wishlist]:
        """Get wishlist by ID."""
        query = select(Wishlist).where(Wishlist.id == wishlist_id)
        
        # Always load settings relationships
        query = query.options(
            selectinload(Wishlist.settings),
            selectinload(Wishlist.manager).selectinload(User.manager_settings)
        )
        
        if load_products:
            query = query.options(
                selectinload(Wishlist.products).selectinload(WishlistProduct.product)
            )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_slug(
        self,
        public_slug: str,
        load_products: bool = False
    ) -> Optional[Wishlist]:
        """Get wishlist by public slug."""
        query = select(Wishlist).where(Wishlist.public_slug == public_slug)
        
        # Always load settings relationships
        query = query.options(
            selectinload(Wishlist.settings),
            selectinload(Wishlist.manager).selectinload(User.manager_settings)
        )
        
        if load_products:
            query = query.options(
                selectinload(Wishlist.products).selectinload(WishlistProduct.product)
            )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_published_by_admin(self, admin_id: UUID) -> Optional[Wishlist]:
        """Get published wishlist for an admin."""
        result = await self.db.execute(
            select(Wishlist).where(
                Wishlist.admin_id == admin_id,
                Wishlist.status == WishlistStatus.PUBLISHED.value
            )
        )
        return result.scalar_one_or_none()
    
    async def get_admin_wishlists(self, admin_id: UUID, load_products: bool = False) -> List[Wishlist]:
        """Get all wishlists for an admin."""
        query = select(Wishlist).where(Wishlist.admin_id == admin_id).order_by(Wishlist.created_at.desc())
        
        # Always load settings relationships
        query = query.options(
            selectinload(Wishlist.settings),
            selectinload(Wishlist.manager).selectinload(User.manager_settings)
        )
        
        if load_products:
            query = query.options(
                selectinload(Wishlist.products).selectinload(WishlistProduct.product)
            )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_manager_wishlists(self, manager_id: UUID, load_products: bool = False) -> List[Wishlist]:
        """Get all wishlists managed by a manager."""
        query = select(Wishlist).where(Wishlist.manager_id == manager_id).order_by(Wishlist.created_at.desc())
        
        # Always load settings relationships
        query = query.options(
            selectinload(Wishlist.settings),
            selectinload(Wishlist.manager).selectinload(User.manager_settings)
        )
        
        if load_products:
            query = query.options(
                selectinload(Wishlist.products).selectinload(WishlistProduct.product)
            )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def create(
        self,
        admin_id: UUID,
        manager_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        logo_url: Optional[str] = None,
        header_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        delivery_address: Optional[dict] = None
    ) -> Wishlist:
        """Create a new wishlist."""
        slug = await self._ensure_unique_slug()
        
        wishlist = Wishlist(
            admin_id=admin_id,
            manager_id=manager_id,
            public_slug=slug,
            status=WishlistStatus.DRAFT.value,
            title=title,
            description=description,
            logo_url=logo_url,
            header_image_url=header_image_url,
            primary_color=primary_color,
            secondary_color=secondary_color,
            delivery_address=delivery_address
        )
        
        self.db.add(wishlist)
        await self.db.flush()
        await self.db.refresh(wishlist)
        
        return wishlist
    
    async def update(
        self,
        wishlist_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        logo_url: Optional[str] = None,
        header_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        delivery_address: Optional[dict] = None
    ) -> Wishlist:
        """Update a wishlist."""
        wishlist = await self.get_by_id(wishlist_id)
        
        if not wishlist:
            raise NotFoundException("Wishlist not found")
        
        if title is not None:
            wishlist.title = title
        if description is not None:
            wishlist.description = description
        if logo_url is not None:
            wishlist.logo_url = logo_url
        if header_image_url is not None:
            wishlist.header_image_url = header_image_url
        if primary_color is not None:
            wishlist.primary_color = primary_color
        if secondary_color is not None:
            wishlist.secondary_color = secondary_color
        if delivery_address is not None:
            wishlist.delivery_address = delivery_address
        
        await self.db.flush()
        await self.db.refresh(wishlist)
        
        return wishlist
    
    async def publish(self, wishlist_id: UUID, admin_id: UUID) -> Wishlist:
        """
        Publish a wishlist.
        Enforces the rule: one published wishlist per admin.
        """
        wishlist = await self.get_by_id(wishlist_id)
        
        if not wishlist:
            raise NotFoundException("Wishlist not found")
        
        if wishlist.admin_id != admin_id:
            raise PermissionDenied("You can only publish your own wishlists")
        
        if wishlist.status == WishlistStatus.PUBLISHED.value:
            raise ConflictError("Wishlist is already published")
        
        # Check if admin has another published wishlist
        existing_published = await self.get_published_by_admin(admin_id)
        if existing_published and existing_published.id != wishlist_id:
            raise ConflictError(
                "You already have a published wishlist. "
                "Please unpublish it before publishing another."
            )
        
        # Update status
        from datetime import datetime
        wishlist.status = WishlistStatus.PUBLISHED.value
        wishlist.published_at = datetime.utcnow()
        
        await self.db.flush()
        await self.db.refresh(wishlist)
        
        return wishlist
    
    async def add_product(
        self,
        wishlist_id: UUID,
        product_id: UUID,
        quantity: int = 1
    ) -> WishlistProduct:
        """Add a product to a wishlist."""
        # Verify wishlist exists
        wishlist = await self.get_by_id(wishlist_id)
        if not wishlist:
            raise NotFoundException("Wishlist not found")
        
        # Verify product exists
        result = await self.db.execute(
            select(Product).where(Product.id == product_id, Product.is_active == True)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundException("Product not found or inactive")
        
        # Check if product already in wishlist
        result = await self.db.execute(
            select(WishlistProduct).where(
                WishlistProduct.wishlist_id == wishlist_id,
                WishlistProduct.product_id == product_id
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update quantity
            existing.quantity = quantity
            await self.db.flush()
            await self.db.refresh(existing)
            return existing
        
        # Add new product
        wishlist_product = WishlistProduct(
            wishlist_id=wishlist_id,
            product_id=product_id,
            quantity=quantity
        )
        
        self.db.add(wishlist_product)
        await self.db.flush()
        await self.db.refresh(wishlist_product)
        
        return wishlist_product
    
    async def remove_product(
        self,
        wishlist_id: UUID,
        product_id: UUID
    ) -> None:
        """Remove a product from a wishlist."""
        result = await self.db.execute(
            select(WishlistProduct).where(
                WishlistProduct.wishlist_id == wishlist_id,
                WishlistProduct.product_id == product_id
            )
        )
        wishlist_product = result.scalar_one_or_none()
        
        if not wishlist_product:
            raise NotFoundException("Product not in wishlist")
        
        await self.db.delete(wishlist_product)
        await self.db.flush()
    
    async def create_with_products(
        self,
        admin_id: UUID,
        manager_id: UUID,
        products: List[dict],
        title: Optional[str] = None,
        description: Optional[str] = None,
        logo_url: Optional[str] = None,
        header_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        delivery_address: Optional[dict] = None
    ) -> Wishlist:
        """Create a new wishlist and add products in one operation."""
        # Create the wishlist
        wishlist = await self.create(
            admin_id=admin_id,
            manager_id=manager_id,
            title=title,
            description=description,
            logo_url=logo_url,
            header_image_url=header_image_url,
            primary_color=primary_color,
            secondary_color=secondary_color,
            delivery_address=delivery_address
        )
        
        # Add products if provided
        if products:
            product_ids = [p["product_id"] for p in products]
            
            # Verify all products exist and are active
            result = await self.db.execute(
                select(Product).where(
                    Product.id.in_(product_ids),
                    Product.is_active == True
                )
            )
            existing_products = list(result.scalars().all())
            
            if len(existing_products) != len(product_ids):
                raise NotFoundException("One or more products not found or inactive")
            
            # Add each product
            for product_data in products:
                wishlist_product = WishlistProduct(
                    wishlist_id=wishlist.id,
                    product_id=product_data["product_id"],
                    quantity=product_data.get("quantity", 1)
                )
                self.db.add(wishlist_product)
            
            await self.db.flush()
            await self.db.refresh(wishlist, attribute_names=["products"])
        
        return wishlist
    
    async def update_products(
        self,
        wishlist_id: UUID,
        products: List[dict]
    ) -> Wishlist:
        """
        Update products in a wishlist (replaces all existing products).
        
        Args:
            wishlist_id: ID of the wishlist
            products: List of dicts with product_id and quantity
        """
        wishlist = await self.get_by_id(wishlist_id)
        
        if not wishlist:
            raise NotFoundException("Wishlist not found")
        
        # Remove all existing products
        result = await self.db.execute(
            select(WishlistProduct).where(WishlistProduct.wishlist_id == wishlist_id)
        )
        for wp in result.scalars().all():
            await self.db.delete(wp)
        
        # Add new products
        if products:
            product_ids = [p["product_id"] for p in products]
            
            # Verify all products exist and are active
            result = await self.db.execute(
                select(Product).where(
                    Product.id.in_(product_ids),
                    Product.is_active == True
                )
            )
            existing_products = list(result.scalars().all())
            
            if len(existing_products) != len(product_ids):
                raise NotFoundException("One or more products not found or inactive")
            
            # Add each product
            for product_data in products:
                wishlist_product = WishlistProduct(
                    wishlist_id=wishlist_id,
                    product_id=product_data["product_id"],
                    quantity=product_data.get("quantity", 1)
                )
                self.db.add(wishlist_product)
        
        await self.db.flush()
        await self.db.refresh(wishlist, attribute_names=["products"])
        
        return wishlist
    
    async def delete(self, wishlist_id: UUID) -> None:
        """Delete a wishlist."""
        wishlist = await self.get_by_id(wishlist_id)
        
        if not wishlist:
            raise NotFoundException("Wishlist not found")
        
        await self.db.delete(wishlist)
        await self.db.flush()
    
    async def get_all(self, load_products: bool = False) -> List[Wishlist]:
        """Get all wishlists (super admin only)."""
        query = select(Wishlist).order_by(Wishlist.created_at.desc())
        
        # Always load settings relationships
        query = query.options(
            selectinload(Wishlist.settings),
            selectinload(Wishlist.manager).selectinload(User.manager_settings)
        )
        
        if load_products:
            query = query.options(
                selectinload(Wishlist.products).selectinload(WishlistProduct.product)
            )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
