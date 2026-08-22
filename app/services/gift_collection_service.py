import secrets
import string
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, List, Any

from app.models.gift_collection import (
    GiftCollection,
    GiftCollectionProduct,
    GiftCollectionStatus,
)
from app.models.product import Product
from app.models.user import User
from app.core.exceptions import NotFoundException, ConflictError, PermissionDenied


class GiftCollectionService:
    """Service for gift collection operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _generate_slug(self, length: int = 12) -> str:
        """Generate a random URL-safe slug."""
        chars = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    async def _ensure_unique_slug(self) -> str:
        """Generate a unique slug for a gift collection."""
        max_attempts = 10
        for _ in range(max_attempts):
            slug = self._generate_slug()
            result = await self.db.execute(
                select(GiftCollection).where(GiftCollection.public_slug == slug)
            )
            if not result.scalar_one_or_none():
                return slug
        raise Exception("Failed to generate unique slug")
    
    def _default_options(self, load_products: bool = False) -> list:
        """Eager-load options shared by every read path."""
        options = [
            selectinload(GiftCollection.settings),
            selectinload(GiftCollection.funeral_home),
            selectinload(GiftCollection.family_admin),
            selectinload(GiftCollection.director).selectinload(User.director_settings),
        ]
        if load_products:
            options.append(
                selectinload(GiftCollection.products).selectinload(GiftCollectionProduct.product)
            )
        return options
    
    async def get_by_id(
        self,
        gift_collection_id: UUID,
        load_products: bool = False
    ) -> Optional[GiftCollection]:
        """Get gift collection by ID."""
        query = (
            select(GiftCollection)
            .where(GiftCollection.id == gift_collection_id)
            .options(*self._default_options(load_products))
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_slug(
        self,
        public_slug: str,
        load_products: bool = False
    ) -> Optional[GiftCollection]:
        """Get gift collection by public slug."""
        query = (
            select(GiftCollection)
            .where(GiftCollection.public_slug == public_slug)
            .options(*self._default_options(load_products))
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_published_by_family_admin(self, family_admin_id: UUID) -> Optional[GiftCollection]:
        """Get the published collection for a family admin."""
        result = await self.db.execute(
            select(GiftCollection).where(
                GiftCollection.family_admin_id == family_admin_id,
                GiftCollection.status == GiftCollectionStatus.PUBLISHED.value
            )
        )
        return result.scalar_one_or_none()
    
    async def get_family_admin_collections(
        self,
        family_admin_id: UUID,
        load_products: bool = False
    ) -> List[GiftCollection]:
        """Get all collections owned by a family admin."""
        query = (
            select(GiftCollection)
            .where(GiftCollection.family_admin_id == family_admin_id)
            .order_by(GiftCollection.created_at.desc())
            .options(*self._default_options(load_products))
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_director_collections(
        self,
        director_id: UUID,
        load_products: bool = False
    ) -> List[GiftCollection]:
        """Get all collections overseen by a director."""
        query = (
            select(GiftCollection)
            .where(GiftCollection.director_id == director_id)
            .order_by(GiftCollection.created_at.desc())
            .options(*self._default_options(load_products))
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def list_collections(
        self,
        funeral_home_id: Optional[UUID] = None,
        director_id: Optional[UUID] = None,
        family_admin_id: Optional[UUID] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        load_products: bool = True,
    ) -> tuple[List[GiftCollection], int]:
        """List collections with filters, returning the page and the total count."""
        filters = []
        
        if funeral_home_id is not None:
            filters.append(GiftCollection.funeral_home_id == funeral_home_id)
        if director_id is not None:
            filters.append(GiftCollection.director_id == director_id)
        if family_admin_id is not None:
            filters.append(GiftCollection.family_admin_id == family_admin_id)
        if status is not None:
            filters.append(GiftCollection.status == status)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    GiftCollection.title.ilike(pattern),
                    GiftCollection.description.ilike(pattern),
                    GiftCollection.public_slug.ilike(pattern),
                )
            )
        
        count_query = select(func.count()).select_from(GiftCollection)
        if filters:
            count_query = count_query.where(*filters)
        total = (await self.db.execute(count_query)).scalar() or 0
        
        query = select(GiftCollection).options(*self._default_options(load_products))
        if filters:
            query = query.where(*filters)
        query = query.order_by(GiftCollection.created_at.desc()).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all()), total
    
    async def create(
        self,
        family_admin_id: UUID,
        director_id: UUID,
        funeral_home_id: Optional[UUID] = None,
        source_default_collection_id: Optional[UUID] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        logo_url: Optional[str] = None,
        header_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        delivery_address: Optional[dict] = None
    ) -> GiftCollection:
        """Create a new gift collection."""
        slug = await self._ensure_unique_slug()
        
        collection = GiftCollection(
            family_admin_id=family_admin_id,
            director_id=director_id,
            funeral_home_id=funeral_home_id,
            source_default_collection_id=source_default_collection_id,
            public_slug=slug,
            status=GiftCollectionStatus.DRAFT.value,
            title=title,
            description=description,
            logo_url=logo_url,
            header_image_url=header_image_url,
            primary_color=primary_color,
            secondary_color=secondary_color,
            delivery_address=delivery_address
        )
        
        self.db.add(collection)
        await self.db.flush()
        await self.db.refresh(collection)
        
        return collection

    async def create_from_default_collection(
        self,
        family_admin_id: UUID,
        director_id: UUID,
        default_collection_data: dict,
        overrides: dict,
        override_fields: set[str],
        funeral_home_id: Optional[UUID] = None,
        source_default_collection_id: Optional[UUID] = None,
    ) -> GiftCollection:
        """Create a collection by copying a default collection and applying overrides."""

        final_payload = {
            "title": self._pick_value("title", default_collection_data, overrides, override_fields),
            "description": self._pick_value("description", default_collection_data, overrides, override_fields),
            "logo_url": self._pick_value("logo_url", default_collection_data, overrides, override_fields),
            "header_image_url": self._pick_value("header_image_url", default_collection_data, overrides, override_fields),
            "primary_color": self._pick_value("primary_color", default_collection_data, overrides, override_fields),
            "secondary_color": self._pick_value("secondary_color", default_collection_data, overrides, override_fields),
            "delivery_address": self._pick_value("delivery_address", default_collection_data, overrides, override_fields),
            "products": self._pick_value("products", default_collection_data, overrides, override_fields) or [],
        }

        return await self._create_from_payload(
            family_admin_id=family_admin_id,
            director_id=director_id,
            funeral_home_id=funeral_home_id,
            source_default_collection_id=source_default_collection_id,
            payload=final_payload,
        )
    
    async def update(
        self,
        gift_collection_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        logo_url: Optional[str] = None,
        header_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        delivery_address: Optional[dict] = None
    ) -> GiftCollection:
        """Update a gift collection."""
        collection = await self.get_by_id(gift_collection_id)
        
        if not collection:
            raise NotFoundException("Gift collection not found")
        
        if title is not None:
            collection.title = title
        if description is not None:
            collection.description = description
        if logo_url is not None:
            collection.logo_url = logo_url
        if header_image_url is not None:
            collection.header_image_url = header_image_url
        if primary_color is not None:
            collection.primary_color = primary_color
        if secondary_color is not None:
            collection.secondary_color = secondary_color
        if delivery_address is not None:
            collection.delivery_address = delivery_address
        
        await self.db.flush()
        await self.db.refresh(collection)
        
        return collection
    
    async def publish(self, gift_collection_id: UUID, family_admin_id: UUID) -> GiftCollection:
        """
        Publish a gift collection.
        Enforces the rule: one published collection per family admin.
        """
        collection = await self.get_by_id(gift_collection_id)
        
        if not collection:
            raise NotFoundException("Gift collection not found")
        
        if collection.family_admin_id != family_admin_id:
            raise PermissionDenied("You can only publish your own gift collections")
        
        if collection.status == GiftCollectionStatus.PUBLISHED.value:
            raise ConflictError("Gift collection is already published")
        
        existing_published = await self.get_published_by_family_admin(family_admin_id)
        if existing_published and existing_published.id != gift_collection_id:
            raise ConflictError(
                "You already have a published gift collection. "
                "Please unpublish it before publishing another."
            )
        
        collection.status = GiftCollectionStatus.PUBLISHED.value
        collection.published_at = datetime.utcnow()
        
        await self.db.flush()
        await self.db.refresh(collection)
        
        return collection
    
    async def add_product(
        self,
        gift_collection_id: UUID,
        product_id: UUID,
        quantity: int = 1
    ) -> GiftCollectionProduct:
        """Add a gift to a collection."""
        collection = await self.get_by_id(gift_collection_id)
        if not collection:
            raise NotFoundException("Gift collection not found")
        
        result = await self.db.execute(
            select(Product).where(Product.id == product_id, Product.is_active == True)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise NotFoundException("Gift not found or inactive")
        
        result = await self.db.execute(
            select(GiftCollectionProduct).where(
                GiftCollectionProduct.gift_collection_id == gift_collection_id,
                GiftCollectionProduct.product_id == product_id
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.quantity = quantity
            await self.db.flush()
            await self.db.refresh(existing)
            return existing
        
        association = GiftCollectionProduct(
            gift_collection_id=gift_collection_id,
            product_id=product_id,
            quantity=quantity
        )
        
        self.db.add(association)
        await self.db.flush()
        await self.db.refresh(association)
        
        return association
    
    async def remove_product(
        self,
        gift_collection_id: UUID,
        product_id: UUID
    ) -> None:
        """Remove a gift from a collection."""
        result = await self.db.execute(
            select(GiftCollectionProduct).where(
                GiftCollectionProduct.gift_collection_id == gift_collection_id,
                GiftCollectionProduct.product_id == product_id
            )
        )
        association = result.scalar_one_or_none()
        
        if not association:
            raise NotFoundException("Gift not in collection")
        
        await self.db.delete(association)
        await self.db.flush()
    
    async def create_with_products(
        self,
        family_admin_id: UUID,
        director_id: UUID,
        products: List[dict],
        funeral_home_id: Optional[UUID] = None,
        source_default_collection_id: Optional[UUID] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        logo_url: Optional[str] = None,
        header_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        delivery_address: Optional[dict] = None
    ) -> GiftCollection:
        """Create a new collection and add gifts in one operation."""
        collection = await self.create(
            family_admin_id=family_admin_id,
            director_id=director_id,
            funeral_home_id=funeral_home_id,
            source_default_collection_id=source_default_collection_id,
            title=title,
            description=description,
            logo_url=logo_url,
            header_image_url=header_image_url,
            primary_color=primary_color,
            secondary_color=secondary_color,
            delivery_address=delivery_address
        )
        
        if products:
            await self._validate_products(products)
            
            for product_data in products:
                self.db.add(
                    GiftCollectionProduct(
                        gift_collection_id=collection.id,
                        product_id=product_data["product_id"],
                        quantity=product_data.get("quantity", 1)
                    )
                )
            
            await self.db.flush()
            await self.db.refresh(collection, attribute_names=["products"])
        
        return collection

    async def _validate_products(self, products: List[dict]) -> None:
        """Ensure every referenced gift exists and is active."""
        product_ids = [product["product_id"] for product in products]
        result = await self.db.execute(
            select(Product).where(
                Product.id.in_(product_ids),
                Product.is_active == True
            )
        )
        existing_products = list(result.scalars().all())
        
        if len(existing_products) != len(set(product_ids)):
            raise NotFoundException("One or more gifts not found or inactive")

    async def _create_from_payload(
        self,
        family_admin_id: UUID,
        director_id: UUID,
        payload: dict[str, Any],
        funeral_home_id: Optional[UUID] = None,
        source_default_collection_id: Optional[UUID] = None,
    ) -> GiftCollection:
        """Create a collection from a prepared payload."""

        products = payload.get("products") or []

        if products:
            return await self.create_with_products(
                family_admin_id=family_admin_id,
                director_id=director_id,
                funeral_home_id=funeral_home_id,
                source_default_collection_id=source_default_collection_id,
                products=products,
                title=payload.get("title"),
                description=payload.get("description"),
                logo_url=payload.get("logo_url"),
                header_image_url=payload.get("header_image_url"),
                primary_color=payload.get("primary_color"),
                secondary_color=payload.get("secondary_color"),
                delivery_address=payload.get("delivery_address"),
            )

        return await self.create(
            family_admin_id=family_admin_id,
            director_id=director_id,
            funeral_home_id=funeral_home_id,
            source_default_collection_id=source_default_collection_id,
            title=payload.get("title"),
            description=payload.get("description"),
            logo_url=payload.get("logo_url"),
            header_image_url=payload.get("header_image_url"),
            primary_color=payload.get("primary_color"),
            secondary_color=payload.get("secondary_color"),
            delivery_address=payload.get("delivery_address"),
        )

    @staticmethod
    def _pick_value(
        field_name: str,
        default_collection_data: dict,
        overrides: dict,
        override_fields: set[str],
    ):
        """Resolve a field from request overrides first, then default collection values."""

        if field_name in override_fields:
            return overrides.get(field_name)

        return default_collection_data.get(field_name)
    
    async def update_products(
        self,
        gift_collection_id: UUID,
        products: List[dict]
    ) -> GiftCollection:
        """Replace all gifts in a collection."""
        collection = await self.get_by_id(gift_collection_id)
        
        if not collection:
            raise NotFoundException("Gift collection not found")
        
        result = await self.db.execute(
            select(GiftCollectionProduct).where(
                GiftCollectionProduct.gift_collection_id == gift_collection_id
            )
        )
        for association in result.scalars().all():
            await self.db.delete(association)
        
        if products:
            await self._validate_products(products)
            
            for product_data in products:
                self.db.add(
                    GiftCollectionProduct(
                        gift_collection_id=gift_collection_id,
                        product_id=product_data["product_id"],
                        quantity=product_data.get("quantity", 1)
                    )
                )
        
        await self.db.flush()
        await self.db.refresh(collection, attribute_names=["products"])
        
        return collection
    
    async def delete(self, gift_collection_id: UUID) -> None:
        """Delete a gift collection."""
        collection = await self.get_by_id(gift_collection_id)
        
        if not collection:
            raise NotFoundException("Gift collection not found")
        
        await self.db.delete(collection)
        await self.db.flush()
    
    async def get_all(self, load_products: bool = False) -> List[GiftCollection]:
        """Get all gift collections (super admin only)."""
        query = (
            select(GiftCollection)
            .order_by(GiftCollection.created_at.desc())
            .options(*self._default_options(load_products))
        )
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
