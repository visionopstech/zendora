import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test")
os.environ.setdefault("SENDGRID_API_KEY", "test")
os.environ.setdefault("SENDGRID_FROM_EMAIL", "test@example.com")

from app.core.exceptions import ValidationError
from app.models.product import Product, ProductImage
from app.services.product_service import ProductService


def test_normalize_images_makes_first_image_primary_when_none_flagged():
    service = ProductService(AsyncMock())
    normalized = service._normalize_images(
        [
            {"url": "https://cdn.example.com/a.jpg"},
            {"url": "https://cdn.example.com/b.jpg", "is_primary": False},
        ]
    )

    assert [image["is_primary"] for image in normalized] == [True, False]
    assert [image["sort_order"] for image in normalized] == [0, 1]


def test_normalize_images_keeps_only_the_first_flagged_primary():
    service = ProductService(AsyncMock())
    normalized = service._normalize_images(
        [
            {"url": "https://cdn.example.com/a.jpg", "is_primary": True},
            {"url": "https://cdn.example.com/b.jpg", "is_primary": True},
            {"url": "https://cdn.example.com/c.jpg"},
        ]
    )

    assert [image["is_primary"] for image in normalized] == [True, False, False]


def test_normalize_images_rejects_missing_url():
    service = ProductService(AsyncMock())
    with pytest.raises(ValidationError):
        service._normalize_images([{"alt_text": "no url"}])


@pytest.mark.asyncio
async def test_add_image_promotes_first_image_and_demotes_previous_primary():
    product_id = uuid4()
    existing = ProductImage(
        id=uuid4(),
        product_id=product_id,
        url="https://cdn.example.com/old.jpg",
        is_primary=True,
        sort_order=0,
    )
    service = ProductService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=Product(id=product_id, name="Gift", base_price=1, price=1))
    service.list_images = AsyncMock(return_value=[existing])
    service.db.add = lambda obj: setattr(obj, "id", uuid4())
    service.db.flush = AsyncMock()
    service.db.refresh = AsyncMock()

    image = await service.add_image(
        product_id=product_id,
        url="https://cdn.example.com/new.jpg",
        is_primary=True,
    )

    assert existing.is_primary is False
    assert image.is_primary is True
    assert image.url == "https://cdn.example.com/new.jpg"


@pytest.mark.asyncio
async def test_set_primary_image_demotes_the_others():
    product_id = uuid4()
    first = ProductImage(
        id=uuid4(), product_id=product_id, url="a", is_primary=True, sort_order=0
    )
    second = ProductImage(
        id=uuid4(), product_id=product_id, url="b", is_primary=False, sort_order=1
    )
    service = ProductService(AsyncMock())
    service.get_image = AsyncMock(return_value=second)
    service.list_images = AsyncMock(return_value=[first, second])
    service.db.flush = AsyncMock()
    service.db.refresh = AsyncMock()

    result = await service.set_primary_image(product_id, second.id)

    assert first.is_primary is False
    assert second.is_primary is True
    assert result is second


@pytest.mark.asyncio
async def test_delete_primary_image_promotes_the_next_one():
    product_id = uuid4()
    primary = ProductImage(
        id=uuid4(), product_id=product_id, url="a", is_primary=True, sort_order=0
    )
    remaining = ProductImage(
        id=uuid4(), product_id=product_id, url="b", is_primary=False, sort_order=1
    )
    service = ProductService(AsyncMock())
    service.get_image = AsyncMock(return_value=primary)
    service.db.delete = AsyncMock()
    service.db.flush = AsyncMock()

    async def list_images(_product_id):
        if service.db.delete.await_count:
            return [remaining]
        return [primary, remaining]

    service.list_images = list_images

    await service.delete_image(product_id, primary.id)

    assert remaining.is_primary is True
    service.db.delete.assert_awaited_once()
