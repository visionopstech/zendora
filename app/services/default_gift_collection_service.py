from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, PermissionDenied
from app.models.default_gift_collection import (
    DefaultCollectionScope,
    DefaultGiftCollection,
    DefaultGiftCollectionProduct,
)
from app.models.product import Product
from app.models.user import User


class DefaultGiftCollectionService:
    """Service for default gift collection operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _product_options(self, load_products: bool) -> list:
        if not load_products:
            return []
        return [
            selectinload(DefaultGiftCollection.products).selectinload(
                DefaultGiftCollectionProduct.product
            )
        ]

    async def get_by_id(
        self,
        default_collection_id: UUID,
        load_products: bool = False,
    ) -> Optional[DefaultGiftCollection]:
        """Get a default gift collection by ID."""

        query = select(DefaultGiftCollection).where(
            DefaultGiftCollection.id == default_collection_id
        )
        options = self._product_options(load_products)
        if options:
            query = query.options(*options)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_collections(
        self,
        owner_scope: Optional[DefaultCollectionScope] = None,
        funeral_home_ids: Optional[List[UUID]] = None,
        include_zendora: bool = True,
        active_only: bool = True,
        search: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        load_products: bool = True,
    ) -> tuple[List[DefaultGiftCollection], int]:
        """
        List default gift collections.

        `funeral_home_ids` restricts FUNERAL_HOME-scoped rows. When
        `include_zendora` is true, ZENDORA-scoped rows are returned as well.
        """

        scope_filters = []

        if owner_scope == DefaultCollectionScope.ZENDORA:
            scope_filters.append(
                DefaultGiftCollection.owner_scope == DefaultCollectionScope.ZENDORA.value
            )
        elif owner_scope == DefaultCollectionScope.FUNERAL_HOME:
            funeral_home_clause = (
                DefaultGiftCollection.owner_scope == DefaultCollectionScope.FUNERAL_HOME.value
            )
            if funeral_home_ids is not None:
                funeral_home_clause = funeral_home_clause & (
                    DefaultGiftCollection.funeral_home_id.in_(funeral_home_ids)
                )
            scope_filters.append(funeral_home_clause)
        else:
            clauses = []
            if include_zendora:
                clauses.append(
                    DefaultGiftCollection.owner_scope == DefaultCollectionScope.ZENDORA.value
                )
            funeral_home_clause = (
                DefaultGiftCollection.owner_scope == DefaultCollectionScope.FUNERAL_HOME.value
            )
            if funeral_home_ids is None:
                clauses.append(funeral_home_clause)
            elif funeral_home_ids:
                clauses.append(
                    funeral_home_clause
                    & DefaultGiftCollection.funeral_home_id.in_(funeral_home_ids)
                )
            if clauses:
                scope_filters.append(or_(*clauses))
            else:
                scope_filters.append(func.false())

        filters = list(scope_filters)

        if active_only:
            filters.append(DefaultGiftCollection.is_active == True)

        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    DefaultGiftCollection.name.ilike(pattern),
                    DefaultGiftCollection.description.ilike(pattern),
                    DefaultGiftCollection.collection_title.ilike(pattern),
                )
            )

        count_query = select(func.count()).select_from(DefaultGiftCollection).where(*filters)
        total = (await self.db.execute(count_query)).scalar() or 0

        query = select(DefaultGiftCollection).where(*filters)
        options = self._product_options(load_products)
        if options:
            query = query.options(*options)
        query = query.order_by(
            DefaultGiftCollection.owner_scope, DefaultGiftCollection.name
        )
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def resolve_for_family_admin(
        self,
        user: User,
        active_only: bool = True,
        load_products: bool = True,
    ) -> List[DefaultGiftCollection]:
        """
        Resolve the default collections a family admin may pick from.

        The funeral home's own defaults win; Zendora defaults are the fallback
        when the funeral home has not created any.
        """

        if user.funeral_home_id:
            funeral_home_defaults, _ = await self.list_collections(
                owner_scope=DefaultCollectionScope.FUNERAL_HOME,
                funeral_home_ids=[user.funeral_home_id],
                active_only=active_only,
                load_products=load_products,
            )
            if funeral_home_defaults:
                return funeral_home_defaults

        zendora_defaults, _ = await self.list_collections(
            owner_scope=DefaultCollectionScope.ZENDORA,
            active_only=active_only,
            load_products=load_products,
        )
        return zendora_defaults

    async def is_applicable_to_family_admin(
        self,
        user: User,
        default_collection: DefaultGiftCollection,
    ) -> bool:
        """Check whether a family admin may build a collection from this default."""

        applicable = await self.resolve_for_family_admin(
            user,
            active_only=True,
            load_products=False,
        )
        return any(item.id == default_collection.id for item in applicable)

    async def _validate_products(self, products: List[dict]) -> None:
        """Ensure all referenced gifts exist and are active."""

        if not products:
            return

        product_ids = [product["product_id"] for product in products]
        result = await self.db.execute(
            select(Product).where(
                Product.id.in_(product_ids),
                Product.is_active == True,
            )
        )
        existing_products = list(result.scalars().all())

        if len(existing_products) != len(set(product_ids)):
            raise NotFoundException("One or more gifts not found or inactive")

    async def _replace_products(
        self,
        default_collection: DefaultGiftCollection,
        products: List[dict],
    ) -> None:
        """Replace all gifts on a default collection."""

        existing = await self.db.execute(
            select(DefaultGiftCollectionProduct).where(
                DefaultGiftCollectionProduct.default_collection_id == default_collection.id
            )
        )
        for association in existing.scalars().all():
            await self.db.delete(association)

        if not products:
            await self.db.flush()
            return

        await self._validate_products(products)

        for product in products:
            self.db.add(
                DefaultGiftCollectionProduct(
                    default_collection_id=default_collection.id,
                    product_id=product["product_id"],
                    quantity=product.get("quantity", 1),
                )
            )

        await self.db.flush()

    async def create(
        self,
        created_by: UUID,
        name: str,
        owner_scope: DefaultCollectionScope = DefaultCollectionScope.ZENDORA,
        funeral_home_id: Optional[UUID] = None,
        description: Optional[str] = None,
        collection_title: Optional[str] = None,
        collection_description: Optional[str] = None,
        logo_url: Optional[str] = None,
        header_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        delivery_address: Optional[dict] = None,
        is_active: bool = True,
        products: Optional[List[dict]] = None,
    ) -> DefaultGiftCollection:
        """Create a default gift collection."""

        scope_value = (
            owner_scope.value if isinstance(owner_scope, DefaultCollectionScope) else owner_scope
        )

        if scope_value == DefaultCollectionScope.FUNERAL_HOME.value and not funeral_home_id:
            raise PermissionDenied("Funeral home scoped defaults require a funeral home")
        if scope_value == DefaultCollectionScope.ZENDORA.value:
            funeral_home_id = None

        default_collection = DefaultGiftCollection(
            created_by=created_by,
            name=name,
            owner_scope=scope_value,
            funeral_home_id=funeral_home_id,
            description=description,
            collection_title=collection_title,
            collection_description=collection_description,
            logo_url=logo_url,
            header_image_url=header_image_url,
            primary_color=primary_color,
            secondary_color=secondary_color,
            delivery_address=delivery_address,
            is_active=is_active,
        )

        self.db.add(default_collection)
        await self.db.flush()
        await self._replace_products(default_collection, products or [])
        await self.db.refresh(default_collection)

        return default_collection

    async def update(
        self,
        default_collection_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        collection_title: Optional[str] = None,
        collection_description: Optional[str] = None,
        logo_url: Optional[str] = None,
        header_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        delivery_address: Optional[dict] = None,
        is_active: Optional[bool] = None,
        products: Optional[List[dict]] = None,
    ) -> DefaultGiftCollection:
        """Update a default gift collection."""

        default_collection = await self.get_by_id(default_collection_id)
        if not default_collection:
            raise NotFoundException("Default gift collection not found")

        if name is not None:
            default_collection.name = name
        if description is not None:
            default_collection.description = description
        if collection_title is not None:
            default_collection.collection_title = collection_title
        if collection_description is not None:
            default_collection.collection_description = collection_description
        if logo_url is not None:
            default_collection.logo_url = logo_url
        if header_image_url is not None:
            default_collection.header_image_url = header_image_url
        if primary_color is not None:
            default_collection.primary_color = primary_color
        if secondary_color is not None:
            default_collection.secondary_color = secondary_color
        if delivery_address is not None:
            default_collection.delivery_address = delivery_address
        if is_active is not None:
            default_collection.is_active = is_active

        await self.db.flush()

        if products is not None:
            await self._replace_products(default_collection, products)

        await self.db.refresh(default_collection)
        return default_collection

    async def deactivate(self, default_collection_id: UUID) -> DefaultGiftCollection:
        """Deactivate a default gift collection."""

        default_collection = await self.get_by_id(default_collection_id)
        if not default_collection:
            raise NotFoundException("Default gift collection not found")

        default_collection.is_active = False
        await self.db.flush()
        await self.db.refresh(default_collection)
        return default_collection

    def build_collection_payload(self, default_collection: DefaultGiftCollection) -> dict:
        """Build the gift collection payload copied from a default collection."""

        return {
            "title": default_collection.collection_title,
            "description": default_collection.collection_description,
            "logo_url": default_collection.logo_url,
            "header_image_url": default_collection.header_image_url,
            "primary_color": default_collection.primary_color,
            "secondary_color": default_collection.secondary_color,
            "delivery_address": default_collection.delivery_address,
            "products": [
                {
                    "product_id": association.product_id,
                    "quantity": association.quantity,
                }
                for association in default_collection.products
            ],
        }
