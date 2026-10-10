import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")

from app.api import wishlist_public
from app.models.gift_collection import GiftCollectionStatus
from app.schemas.gift_collection import GiftCollectionResponse


def make_collection(**kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        family_admin_id=kwargs.get("family_admin_id", uuid4()),
        director_id=kwargs.get("director_id"),
        funeral_home_id=kwargs.get("funeral_home_id"),
        source_default_collection_id=None,
        public_slug=kwargs.get("public_slug", "test-slug"),
        status=kwargs.get("status", GiftCollectionStatus.PUBLISHED.value),
        visit_count=kwargs.get("visit_count", 0),
        title="Memorial collection",
        description=None,
        logo_url=None,
        header_image_url=None,
        primary_color=None,
        secondary_color=None,
        delivery_address=None,
        created_at=datetime.utcnow(),
        published_at=datetime.utcnow(),
        products=[],
        settings=None,
        family_admin=None,
        funeral_home=None,
        director=None,
    )


@pytest.mark.asyncio
async def test_public_page_visit_increments_counter():
    collection = make_collection()
    db = AsyncMock()

    with patch.object(wishlist_public, "GiftCollectionService") as service_cls:
        service = service_cls.return_value
        service.get_by_slug = AsyncMock(return_value=collection)
        service.increment_visit_count = AsyncMock()

        response = await wishlist_public.get_public_gift_collection(
            public_slug=collection.public_slug, db=db
        )

    service.increment_visit_count.assert_awaited_once_with(collection.id)
    db.commit.assert_awaited_once()
    assert response.id == collection.id


@pytest.mark.asyncio
async def test_draft_or_missing_collection_does_not_count_visits():
    draft = make_collection(status=GiftCollectionStatus.DRAFT.value)
    db = AsyncMock()

    with patch.object(wishlist_public, "GiftCollectionService") as service_cls:
        service = service_cls.return_value
        service.get_by_slug = AsyncMock(return_value=draft)
        service.increment_visit_count = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await wishlist_public.get_public_gift_collection(
                public_slug=draft.public_slug, db=db
            )

    assert exc_info.value.status_code == 404
    service.increment_visit_count.assert_not_awaited()
    db.commit.assert_not_awaited()


def test_visit_count_exposed_in_authenticated_response():
    collection = make_collection(visit_count=42)
    response = GiftCollectionResponse.model_validate(collection)
    assert response.visit_count == 42
