from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.models.product import Product
from app.models.wishlist_template import WishlistTemplate, WishlistTemplateProduct


class WishlistTemplateService:
    """Service for wishlist template operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
        self,
        template_id: UUID,
        load_products: bool = False,
    ) -> Optional[WishlistTemplate]:
        """Get a wishlist template by ID."""

        query = select(WishlistTemplate).where(WishlistTemplate.id == template_id)

        if load_products:
            query = query.options(
                selectinload(WishlistTemplate.products).selectinload(WishlistTemplateProduct.product)
            )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_templates(
        self,
        active_only: bool = True,
        load_products: bool = False,
    ) -> List[WishlistTemplate]:
        """List wishlist templates."""

        query = select(WishlistTemplate)

        if active_only:
            query = query.where(WishlistTemplate.is_active == True)

        if load_products:
            query = query.options(
                selectinload(WishlistTemplate.products).selectinload(WishlistTemplateProduct.product)
            )

        query = query.order_by(WishlistTemplate.name)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _validate_products(self, products: List[dict]) -> None:
        """Ensure all referenced products exist and are active."""

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

        if len(existing_products) != len(product_ids):
            raise NotFoundException("One or more products not found or inactive")

    async def _replace_products(
        self,
        template: WishlistTemplate,
        products: List[dict],
    ) -> None:
        """Replace all products on a template."""

        existing = await self.db.execute(
            select(WishlistTemplateProduct).where(WishlistTemplateProduct.template_id == template.id)
        )
        for association in existing.scalars().all():
            await self.db.delete(association)

        if not products:
            await self.db.flush()
            return

        await self._validate_products(products)

        for product in products:
            self.db.add(
                WishlistTemplateProduct(
                    template_id=template.id,
                    product_id=product["product_id"],
                    quantity=product.get("quantity", 1),
                )
            )

        await self.db.flush()

    async def create(
        self,
        created_by: UUID,
        name: str,
        description: Optional[str] = None,
        wishlist_title: Optional[str] = None,
        wishlist_description: Optional[str] = None,
        logo_url: Optional[str] = None,
        header_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        delivery_address: Optional[dict] = None,
        is_active: bool = True,
        products: Optional[List[dict]] = None,
    ) -> WishlistTemplate:
        """Create a wishlist template."""

        template = WishlistTemplate(
            created_by=created_by,
            name=name,
            description=description,
            wishlist_title=wishlist_title,
            wishlist_description=wishlist_description,
            logo_url=logo_url,
            header_image_url=header_image_url,
            primary_color=primary_color,
            secondary_color=secondary_color,
            delivery_address=delivery_address,
            is_active=is_active,
        )

        self.db.add(template)
        await self.db.flush()
        await self._replace_products(template, products or [])
        await self.db.refresh(template)

        return template

    async def update(
        self,
        template_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        wishlist_title: Optional[str] = None,
        wishlist_description: Optional[str] = None,
        logo_url: Optional[str] = None,
        header_image_url: Optional[str] = None,
        primary_color: Optional[str] = None,
        secondary_color: Optional[str] = None,
        delivery_address: Optional[dict] = None,
        is_active: Optional[bool] = None,
        products: Optional[List[dict]] = None,
    ) -> WishlistTemplate:
        """Update a wishlist template."""

        template = await self.get_by_id(template_id)
        if not template:
            raise NotFoundException("Wishlist template not found")

        if name is not None:
            template.name = name
        if description is not None:
            template.description = description
        if wishlist_title is not None:
            template.wishlist_title = wishlist_title
        if wishlist_description is not None:
            template.wishlist_description = wishlist_description
        if logo_url is not None:
            template.logo_url = logo_url
        if header_image_url is not None:
            template.header_image_url = header_image_url
        if primary_color is not None:
            template.primary_color = primary_color
        if secondary_color is not None:
            template.secondary_color = secondary_color
        if delivery_address is not None:
            template.delivery_address = delivery_address
        if is_active is not None:
            template.is_active = is_active

        await self.db.flush()

        if products is not None:
            await self._replace_products(template, products)

        await self.db.refresh(template)
        return template

    async def deactivate(self, template_id: UUID) -> WishlistTemplate:
        """Deactivate a wishlist template."""

        template = await self.get_by_id(template_id)
        if not template:
            raise NotFoundException("Wishlist template not found")

        template.is_active = False
        await self.db.flush()
        await self.db.refresh(template)
        return template

    def build_wishlist_payload(self, template: WishlistTemplate) -> dict:
        """Build the wishlist payload copied from a template."""

        return {
            "title": template.wishlist_title,
            "description": template.wishlist_description,
            "logo_url": template.logo_url,
            "header_image_url": template.header_image_url,
            "primary_color": template.primary_color,
            "secondary_color": template.secondary_color,
            "delivery_address": template.delivery_address,
            "products": [
                {
                    "product_id": product.product_id,
                    "quantity": product.quantity,
                }
                for product in template.products
            ],
        }
