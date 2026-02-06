from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, List
from decimal import Decimal

from app.models.product import Product, ProductVendor
from app.models.vendor import Vendor
from app.core.exceptions import NotFoundException, ConflictError


class ProductService:
    """Service for product-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, product_id: UUID, load_vendors: bool = False) -> Optional[Product]:
        """Get product by ID."""
        query = select(Product).where(Product.id == product_id)
        
        if load_vendors:
            query = query.options(selectinload(Product.vendor_associations))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all(self, include_inactive: bool = False, load_vendors: bool = False) -> List[Product]:
        """Get all products."""
        query = select(Product)
        
        if load_vendors:
            query = query.options(selectinload(Product.vendor_associations))
        
        if not include_inactive:
            query = query.where(Product.is_active == True)
        
        query = query.order_by(Product.name)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_by_ids(self, product_ids: List[UUID]) -> List[Product]:
        """Get multiple products by IDs."""
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
        price: Decimal,
        description: Optional[str] = None,
        images: Optional[List[str]] = None
    ) -> Product:
        """Create a new product."""
        product = Product(
            name=name,
            description=description,
            price=price,
            images=images or [],
            is_active=True
        )
        
        self.db.add(product)
        await self.db.flush()
        await self.db.refresh(product)
        
        return product
    
    async def create_with_vendors(
        self,
        name: str,
        price: Decimal,
        vendor_ids: List[UUID],
        description: Optional[str] = None,
        images: Optional[List[str]] = None
    ) -> Product:
        """Create a new product and associate it with vendors in one operation."""
        # Create the product
        product = await self.create(
            name=name,
            price=price,
            description=description,
            images=images
        )
        
        # Associate vendors if provided
        if vendor_ids:
            # Verify all vendors exist
            result = await self.db.execute(
                select(Vendor).where(Vendor.id.in_(vendor_ids))
            )
            vendors = list(result.scalars().all())
            
            if len(vendors) != len(vendor_ids):
                raise NotFoundException("One or more vendors not found")
            
            # Create associations
            for vendor_id in vendor_ids:
                association = ProductVendor(
                    product_id=product.id,
                    vendor_id=vendor_id
                )
                self.db.add(association)
            
            await self.db.flush()
            await self.db.refresh(product, attribute_names=["vendor_associations"])
        
        return product
    
    async def update(
        self,
        product_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        price: Optional[Decimal] = None,
        images: Optional[List[str]] = None,
        is_active: Optional[bool] = None
    ) -> Product:
        """Update a product."""
        product = await self.get_by_id(product_id)
        
        if not product:
            raise NotFoundException("Product not found")
        
        if name is not None:
            product.name = name
        if description is not None:
            product.description = description
        if price is not None:
            product.price = price
        if images is not None:
            product.images = images
        if is_active is not None:
            product.is_active = is_active
        
        await self.db.flush()
        await self.db.refresh(product)
        
        return product
    
    async def delete(self, product_id: UUID) -> None:
        """Delete a product."""
        product = await self.get_by_id(product_id)
        
        if not product:
            raise NotFoundException("Product not found")
        
        await self.db.delete(product)
        await self.db.flush()
    
    async def associate_vendors(
        self,
        product_id: UUID,
        vendor_ids: List[UUID]
    ) -> Product:
        """
        Associate vendors with a product.
        This replaces existing associations.
        """
        product = await self.get_by_id(product_id)
        
        if not product:
            raise NotFoundException("Product not found")
        
        # Verify all vendors exist
        result = await self.db.execute(
            select(Vendor).where(Vendor.id.in_(vendor_ids))
        )
        vendors = list(result.scalars().all())
        
        if len(vendors) != len(vendor_ids):
            raise NotFoundException("One or more vendors not found")
        
        # Remove existing associations
        await self.db.execute(
            select(ProductVendor).where(ProductVendor.product_id == product_id)
        )
        existing = await self.db.execute(
            select(ProductVendor).where(ProductVendor.product_id == product_id)
        )
        for assoc in existing.scalars().all():
            await self.db.delete(assoc)
        
        # Create new associations
        for vendor_id in vendor_ids:
            association = ProductVendor(
                product_id=product_id,
                vendor_id=vendor_id
            )
            self.db.add(association)
        
        await self.db.flush()
        await self.db.refresh(product)
        
        return product
    
    async def get_product_vendors(self, product_id: UUID) -> List[Vendor]:
        """Get all vendors associated with a product."""
        result = await self.db.execute(
            select(Vendor)
            .join(ProductVendor, ProductVendor.vendor_id == Vendor.id)
            .where(ProductVendor.product_id == product_id)
            .order_by(Vendor.name)
        )
        return list(result.scalars().all())
