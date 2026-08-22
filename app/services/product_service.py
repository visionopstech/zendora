from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, List
from decimal import Decimal

from app.models.product import Product, ProductImage, ProductVendor
from app.models.vendor import Vendor
from app.core.exceptions import NotFoundException, ValidationError


class ProductService:
    """Service for gift (product) operations, including the image gallery."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    def _validate_prices(self, base_price: Decimal, price: Decimal) -> None:
        if price < base_price:
            raise ValidationError("price must be greater than or equal to base_price")

    def _normalize_images(self, images: Optional[List[dict]]) -> List[dict]:
        """
        Normalize a submitted gallery: exactly one primary image, stable ordering.

        The first image flagged primary wins; when none is flagged the first
        image becomes primary. sort_order defaults to the list position.
        """
        if not images:
            return []

        normalized = []
        primary_index = next(
            (index for index, image in enumerate(images) if image.get("is_primary")),
            0,
        )

        for index, image in enumerate(images):
            url = image.get("url")
            if not url:
                raise ValidationError("Every gift image requires a url")
            normalized.append(
                {
                    "url": url,
                    "alt_text": image.get("alt_text"),
                    "is_primary": index == primary_index,
                    "sort_order": image.get("sort_order") if image.get("sort_order") is not None else index,
                }
            )

        return normalized

    async def _replace_images(self, product: Product, images: Optional[List[dict]]) -> None:
        """Replace a gift's whole gallery."""
        existing = await self.db.execute(
            select(ProductImage).where(ProductImage.product_id == product.id)
        )
        for image in existing.scalars().all():
            await self.db.delete(image)
        await self.db.flush()

        for image in self._normalize_images(images):
            self.db.add(ProductImage(product_id=product.id, **image))

        await self.db.flush()
    
    async def get_by_id(self, product_id: UUID, load_vendors: bool = False) -> Optional[Product]:
        """Get gift by ID."""
        query = select(Product).where(Product.id == product_id)
        
        if load_vendors:
            query = query.options(selectinload(Product.vendor_associations))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        include_inactive: bool = False,
        load_vendors: bool = False,
        vendor_id: Optional[UUID] = None
    ) -> List[Product]:
        """Get all gifts, optionally filtered by vendor."""
        query = select(Product)
        
        if load_vendors:
            query = query.options(selectinload(Product.vendor_associations))
        
        if vendor_id is not None:
            vendor_product_ids = select(ProductVendor.product_id).where(
                ProductVendor.vendor_id == vendor_id
            )
            query = query.where(Product.id.in_(vendor_product_ids))
        
        if not include_inactive:
            query = query.where(Product.is_active == True)
        
        query = query.order_by(Product.name)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_by_ids(self, product_ids: List[UUID]) -> List[Product]:
        """Get multiple gifts by IDs."""
        result = await self.db.execute(
            select(Product).where(
                Product.id.in_(product_ids),
                Product.is_active == True
            )
        )
        return list(result.scalars().all())
    
    async def create(
        self,
        name: str,
        base_price: Decimal,
        price: Decimal,
        description: Optional[str] = None,
        images: Optional[List[dict]] = None
    ) -> Product:
        """Create a new gift with its gallery."""
        self._validate_prices(base_price, price)
        product = Product(
            name=name,
            description=description,
            base_price=base_price,
            price=price,
            is_active=True
        )
        
        self.db.add(product)
        await self.db.flush()
        
        if images:
            await self._replace_images(product, images)
        
        await self.db.refresh(product)
        
        return product
    
    async def create_with_vendors(
        self,
        name: str,
        base_price: Decimal,
        price: Decimal,
        vendor_ids: List[UUID],
        description: Optional[str] = None,
        images: Optional[List[dict]] = None
    ) -> Product:
        """Create a new gift and associate it with vendors in one operation."""
        product = await self.create(
            name=name,
            base_price=base_price,
            price=price,
            description=description,
            images=images
        )
        
        if vendor_ids:
            result = await self.db.execute(
                select(Vendor).where(Vendor.id.in_(vendor_ids))
            )
            vendors = list(result.scalars().all())
            
            if len(vendors) != len(set(vendor_ids)):
                raise NotFoundException("One or more vendors not found")
            
            for vendor_id in vendor_ids:
                self.db.add(ProductVendor(product_id=product.id, vendor_id=vendor_id))
            
            await self.db.flush()
            await self.db.refresh(product, attribute_names=["vendor_associations"])
        
        return product
    
    async def update(
        self,
        product_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        base_price: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        images: Optional[List[dict]] = None,
        is_active: Optional[bool] = None
    ) -> Product:
        """Update a gift. When images are provided they replace the whole gallery."""
        product = await self.get_by_id(product_id)
        
        if not product:
            raise NotFoundException("Gift not found")

        next_base_price = base_price if base_price is not None else product.base_price
        next_price = price if price is not None else product.price
        self._validate_prices(next_base_price, next_price)
        
        if name is not None:
            product.name = name
        if description is not None:
            product.description = description
        if base_price is not None:
            product.base_price = base_price
        if price is not None:
            product.price = price
        if is_active is not None:
            product.is_active = is_active
        
        await self.db.flush()
        
        if images is not None:
            await self._replace_images(product, images)
        
        await self.db.refresh(product)
        
        return product
    
    async def delete(self, product_id: UUID) -> None:
        """Delete a gift."""
        product = await self.get_by_id(product_id)
        
        if not product:
            raise NotFoundException("Gift not found")
        
        await self.db.delete(product)
        await self.db.flush()
    
    # Gallery operations
    
    async def get_image(self, product_id: UUID, image_id: UUID) -> Optional[ProductImage]:
        """Get one gallery image belonging to a gift."""
        result = await self.db.execute(
            select(ProductImage).where(
                ProductImage.id == image_id,
                ProductImage.product_id == product_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def list_images(self, product_id: UUID) -> List[ProductImage]:
        """List a gift's gallery in display order."""
        result = await self.db.execute(
            select(ProductImage)
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.sort_order, ProductImage.created_at)
        )
        return list(result.scalars().all())
    
    async def add_image(
        self,
        product_id: UUID,
        url: str,
        alt_text: Optional[str] = None,
        is_primary: bool = False,
        sort_order: Optional[int] = None,
    ) -> ProductImage:
        """Append an image to a gift's gallery."""
        product = await self.get_by_id(product_id)
        if not product:
            raise NotFoundException("Gift not found")
        
        existing = await self.list_images(product_id)
        
        # The first image of an empty gallery is always primary.
        make_primary = is_primary or not existing
        
        if make_primary:
            for image in existing:
                image.is_primary = False
        
        image = ProductImage(
            product_id=product_id,
            url=url,
            alt_text=alt_text,
            is_primary=make_primary,
            sort_order=sort_order if sort_order is not None else len(existing),
        )
        self.db.add(image)
        await self.db.flush()
        await self.db.refresh(image)
        
        return image
    
    async def delete_image(self, product_id: UUID, image_id: UUID) -> None:
        """Remove an image, promoting another one to primary when needed."""
        image = await self.get_image(product_id, image_id)
        if not image:
            raise NotFoundException("Gift image not found")
        
        was_primary = image.is_primary
        await self.db.delete(image)
        await self.db.flush()
        
        if was_primary:
            remaining = await self.list_images(product_id)
            if remaining:
                remaining[0].is_primary = True
                await self.db.flush()
    
    async def set_primary_image(self, product_id: UUID, image_id: UUID) -> ProductImage:
        """Promote one gallery image to primary, demoting the others."""
        target = await self.get_image(product_id, image_id)
        if not target:
            raise NotFoundException("Gift image not found")
        
        for image in await self.list_images(product_id):
            image.is_primary = image.id == image_id
        
        await self.db.flush()
        await self.db.refresh(target)
        return target
    
    async def reorder_images(self, product_id: UUID, image_ids: List[UUID]) -> List[ProductImage]:
        """Reorder a gift's gallery to match the given id order."""
        images = await self.list_images(product_id)
        if not images:
            raise NotFoundException("Gift has no images")
        
        known_ids = {image.id for image in images}
        if set(image_ids) != known_ids:
            raise ValidationError("image_ids must list every image of this gift exactly once")
        
        positions = {image_id: index for index, image_id in enumerate(image_ids)}
        for image in images:
            image.sort_order = positions[image.id]
        
        await self.db.flush()
        return await self.list_images(product_id)
    
    async def associate_vendors(
        self,
        product_id: UUID,
        vendor_ids: List[UUID]
    ) -> Product:
        """
        Associate vendors with a gift.
        This replaces existing associations.
        """
        product = await self.get_by_id(product_id)
        
        if not product:
            raise NotFoundException("Gift not found")
        
        result = await self.db.execute(
            select(Vendor).where(Vendor.id.in_(vendor_ids))
        )
        vendors = list(result.scalars().all())
        
        if len(vendors) != len(set(vendor_ids)):
            raise NotFoundException("One or more vendors not found")
        
        existing = await self.db.execute(
            select(ProductVendor).where(ProductVendor.product_id == product_id)
        )
        for assoc in existing.scalars().all():
            await self.db.delete(assoc)
        
        for vendor_id in vendor_ids:
            self.db.add(ProductVendor(product_id=product_id, vendor_id=vendor_id))
        
        await self.db.flush()
        await self.db.refresh(product)
        
        return product
    
    async def get_product_vendors(self, product_id: UUID) -> List[Vendor]:
        """Get all vendors associated with a gift."""
        result = await self.db.execute(
            select(Vendor)
            .join(ProductVendor, ProductVendor.vendor_id == Vendor.id)
            .where(ProductVendor.product_id == product_id)
            .order_by(Vendor.name)
        )
        return list(result.scalars().all())
    
    async def product_belongs_to_vendor(self, product_id: UUID, vendor_id: UUID) -> bool:
        """Check if a gift is associated with a vendor."""
        result = await self.db.execute(
            select(ProductVendor).where(
                ProductVendor.product_id == product_id,
                ProductVendor.vendor_id == vendor_id
            )
        )
        return result.scalar_one_or_none() is not None
    
    async def add_vendor_to_product(self, product_id: UUID, vendor_id: UUID) -> Product:
        """Add a vendor association to a gift (without removing existing)."""
        product = await self.get_by_id(product_id)
        if not product:
            raise NotFoundException("Gift not found")
        
        if await self.product_belongs_to_vendor(product_id, vendor_id):
            return product
        
        result = await self.db.execute(select(Vendor).where(Vendor.id == vendor_id))
        if not result.scalar_one_or_none():
            raise NotFoundException("Vendor not found")
        
        self.db.add(ProductVendor(product_id=product_id, vendor_id=vendor_id))
        await self.db.flush()
        await self.db.refresh(product, attribute_names=["vendor_associations"])
        return product
