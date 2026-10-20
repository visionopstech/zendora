import os
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
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

from app.api import products as products_api
from app.core.exceptions import NotFoundException, PermissionDenied
from app.models.user import UserRole
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.default_gift_collection_service import DefaultGiftCollectionService
from app.services.gift_collection_service import GiftCollectionService
from app.services.product_service import ProductService


def make_user(role: UserRole, **kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        role=role.value,
        funeral_home_id=kwargs.get("funeral_home_id"),
        vendor_id=kwargs.get("vendor_id"),
        email=kwargs.get("email", "user@example.com"),
    )


def make_product(**kwargs):
    vendor_ids = kwargs.get("vendor_ids", [])
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        name=kwargs.get("name", "Chapel bouquet"),
        description=kwargs.get("description", "Local flowers"),
        details=kwargs.get("details", []),
        base_price=kwargs.get("base_price", Decimal("10.00")),
        price=kwargs.get("price", Decimal("15.00")),
        is_active=kwargs.get("is_active", True),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        images=kwargs.get("images", []),
        primary_image_url=kwargs.get("primary_image_url"),
        funeral_home_id=kwargs.get("funeral_home_id"),
        created_by=kwargs.get("created_by"),
        vendor_associations=[
            SimpleNamespace(vendor_id=vendor_id) for vendor_id in vendor_ids
        ],
    )


def make_create_payload(**kwargs):
    return ProductCreate(
        name=kwargs.get("name", "Chapel bouquet"),
        base_price=kwargs.get("base_price", Decimal("10.00")),
        price=kwargs.get("price", Decimal("15.00")),
        description=kwargs.get("description", "Local flowers"),
        vendor_ids=kwargs.get("vendor_ids", []),
    )


def test_super_admin_can_read_and_edit_any_gift():
    service = ProductService(AsyncMock())
    admin = make_user(UserRole.SUPER_ADMIN)
    global_gift = make_product()
    home_gift = make_product(funeral_home_id=uuid4())

    assert service.can_read(admin, global_gift) is True
    assert service.can_edit(admin, global_gift) is True
    assert service.can_read(admin, home_gift) is True
    assert service.can_edit(admin, home_gift) is True


def test_director_sees_global_read_only_and_edits_own_home():
    service = ProductService(AsyncMock())
    home_id = uuid4()
    director = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    global_gift = make_product()
    own = make_product(funeral_home_id=home_id)
    other = make_product(funeral_home_id=uuid4())

    assert service.can_read(director, global_gift) is True
    assert service.can_edit(director, global_gift) is False
    assert service.can_read(director, own) is True
    assert service.can_edit(director, own) is True
    assert service.can_read(director, other) is False
    assert service.can_edit(director, other) is False


def test_family_sees_global_and_own_home_but_cannot_edit():
    service = ProductService(AsyncMock())
    home_id = uuid4()
    family = make_user(UserRole.FAMILY_ADMIN, funeral_home_id=home_id)
    global_gift = make_product()
    own = make_product(funeral_home_id=home_id)
    other = make_product(funeral_home_id=uuid4())

    assert service.can_read(family, global_gift) is True
    assert service.can_edit(family, global_gift) is False
    assert service.can_read(family, own) is True
    assert service.can_edit(family, own) is False
    assert service.can_read(family, other) is False


def test_vendor_only_sees_own_vendor_gifts():
    service = ProductService(AsyncMock())
    vendor_id = uuid4()
    vendor = make_user(UserRole.VENDOR, vendor_id=vendor_id)
    own = make_product(vendor_ids=[vendor_id])
    other = make_product(vendor_ids=[uuid4()])
    home_gift = make_product(funeral_home_id=uuid4())

    assert service.can_read(vendor, own) is True
    assert service.can_edit(vendor, own) is True
    assert service.can_read(vendor, other) is False
    assert service.can_edit(vendor, other) is False
    assert service.can_read(vendor, home_gift) is False
    assert service.can_edit(vendor, home_gift) is False


def test_create_scope_is_forced_from_caller():
    service = ProductService(AsyncMock())
    admin = make_user(UserRole.SUPER_ADMIN)
    home_id = uuid4()
    director = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    vendor = make_user(UserRole.VENDOR, vendor_id=uuid4())
    family = make_user(UserRole.FAMILY_ADMIN, funeral_home_id=home_id)

    assert service.resolve_create_scope(admin) is None
    assert service.resolve_create_scope(vendor) is None
    assert service.resolve_create_scope(director) == home_id

    with pytest.raises(PermissionDenied):
        service.resolve_create_scope(family)

    with pytest.raises(PermissionDenied):
        service.resolve_create_scope(make_user(UserRole.DIRECTOR, funeral_home_id=None))


def test_gift_is_available_to_matching_home_or_global():
    home_id = uuid4()
    global_gift = make_product()
    own = make_product(funeral_home_id=home_id)
    other = make_product(funeral_home_id=uuid4())

    assert ProductService.is_available_to_funeral_home(global_gift, home_id) is True
    assert ProductService.is_available_to_funeral_home(own, home_id) is True
    assert ProductService.is_available_to_funeral_home(other, home_id) is False
    assert ProductService.is_available_to_funeral_home(
        own, None, global_only=True
    ) is False
    assert ProductService.is_available_to_funeral_home(
        global_gift, None, global_only=True
    ) is True


def test_director_list_filter_includes_global_and_own_home():
    service = ProductService(AsyncMock())
    home_id = uuid4()
    director = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    filters = service._visibility_filters(director, None)
    compiled = str(filters[0].compile(compile_kwargs={"literal_binds": True}))

    assert "funeral_home_id IS NULL" in compiled
    assert home_id.hex in compiled
    assert ProductService(AsyncMock())._visibility_filters(
        make_user(UserRole.SUPER_ADMIN), None
    ) == []


@pytest.mark.asyncio
async def test_director_creates_home_scoped_gift_and_ignores_vendor_ids(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    home_id = uuid4()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    created = make_product(funeral_home_id=home_id, created_by=current_user.id)
    real = ProductService(AsyncMock())
    service = SimpleNamespace(
        resolve_create_scope=real.resolve_create_scope,
        create=AsyncMock(return_value=created),
        create_with_vendors=AsyncMock(),
        get_by_id=AsyncMock(return_value=created),
        can_edit=real.can_edit,
        can_read=real.can_read,
    )
    monkeypatch.setattr(products_api, "ProductService", lambda _: service)

    response = await products_api.create_product(
        product_data=make_create_payload(vendor_ids=[uuid4()]),
        db=db,
        current_user=current_user,
    )

    service.create_with_vendors.assert_not_called()
    assert service.create.await_args.kwargs["funeral_home_id"] == home_id
    assert service.create.await_args.kwargs["created_by"] == current_user.id
    assert response.funeral_home_id == home_id
    assert response.can_edit is True
    assert response.vendor_ids == []


@pytest.mark.asyncio
async def test_super_admin_create_leaves_funeral_home_null(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    created = make_product(created_by=current_user.id)
    real = ProductService(AsyncMock())
    service = SimpleNamespace(
        resolve_create_scope=real.resolve_create_scope,
        create=AsyncMock(return_value=created),
        create_with_vendors=AsyncMock(),
        get_by_id=AsyncMock(return_value=created),
        can_edit=real.can_edit,
    )
    monkeypatch.setattr(products_api, "ProductService", lambda _: service)

    response = await products_api.create_product(
        product_data=make_create_payload(),
        db=db,
        current_user=current_user,
    )

    assert service.create.await_args.kwargs["funeral_home_id"] is None
    assert response.funeral_home_id is None
    assert response.can_edit is True


@pytest.mark.asyncio
async def test_vendor_create_leaves_funeral_home_null(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    vendor_id = uuid4()
    current_user = make_user(UserRole.VENDOR, vendor_id=vendor_id)
    created = make_product(vendor_ids=[vendor_id], created_by=current_user.id)
    real = ProductService(AsyncMock())
    service = SimpleNamespace(
        resolve_create_scope=real.resolve_create_scope,
        create=AsyncMock(),
        create_with_vendors=AsyncMock(return_value=created),
        get_by_id=AsyncMock(return_value=created),
        can_edit=real.can_edit,
    )
    monkeypatch.setattr(products_api, "ProductService", lambda _: service)

    response = await products_api.create_product(
        product_data=make_create_payload(),
        db=db,
        current_user=current_user,
    )

    service.create.assert_not_called()
    assert "funeral_home_id" not in service.create_with_vendors.await_args.kwargs
    assert response.funeral_home_id is None
    assert response.vendor_ids == [vendor_id]


@pytest.mark.asyncio
async def test_family_cannot_create_gift():
    with pytest.raises(HTTPException) as exc:
        await products_api.create_product(
            product_data=make_create_payload(),
            db=SimpleNamespace(),
            current_user=make_user(UserRole.FAMILY_ADMIN, funeral_home_id=uuid4()),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_director_without_home_cannot_create_gift():
    with pytest.raises(HTTPException) as exc:
        await products_api.create_product(
            product_data=make_create_payload(),
            db=SimpleNamespace(),
            current_user=make_user(UserRole.DIRECTOR, funeral_home_id=None),
        )

    assert exc.value.status_code == 403
    assert "funeral home" in exc.value.detail


@pytest.mark.asyncio
async def test_director_list_passes_actor_and_sets_can_edit(monkeypatch):
    db = SimpleNamespace()
    home_id = uuid4()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    global_gift = make_product(name="Shared candle")
    own = make_product(name="Home bouquet", funeral_home_id=home_id)
    real = ProductService(AsyncMock())
    service = SimpleNamespace(
        get_all=AsyncMock(return_value=[global_gift, own]),
        can_edit=real.can_edit,
    )
    monkeypatch.setattr(products_api, "ProductService", lambda _: service)

    result = await products_api.list_products(
        include_inactive=False,
        db=db,
        current_user=current_user,
    )

    assert service.get_all.await_args.kwargs["actor"] is current_user
    assert service.get_all.await_args.kwargs["vendor_id"] is None
    by_name = {item.name: item for item in result}
    assert by_name["Shared candle"].can_edit is False
    assert by_name["Home bouquet"].can_edit is True


@pytest.mark.asyncio
async def test_director_cannot_get_other_home_gift(monkeypatch):
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    other = make_product(funeral_home_id=uuid4())
    real = ProductService(AsyncMock())
    service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=other),
        can_read=real.can_read,
        can_edit=real.can_edit,
    )
    monkeypatch.setattr(products_api, "ProductService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await products_api.get_product(
            product_id=other.id,
            db=SimpleNamespace(),
            current_user=current_user,
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_director_cannot_update_or_delete_other_home_gift(monkeypatch):
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    other = make_product(funeral_home_id=uuid4())
    real = ProductService(AsyncMock())
    service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=other),
        can_edit=real.can_edit,
        update=AsyncMock(),
        delete=AsyncMock(),
    )
    monkeypatch.setattr(products_api, "ProductService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await products_api.update_product(
            product_id=other.id,
            product_data=ProductUpdate(name="Nope"),
            db=SimpleNamespace(),
            current_user=current_user,
        )
    assert exc.value.status_code == 404
    service.update.assert_not_called()

    with pytest.raises(HTTPException) as exc:
        await products_api.delete_product(
            product_id=other.id,
            db=SimpleNamespace(),
            current_user=current_user,
        )
    assert exc.value.status_code == 404
    service.delete.assert_not_called()


@pytest.mark.asyncio
async def test_director_cannot_edit_global_gift(monkeypatch):
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    global_gift = make_product()
    real = ProductService(AsyncMock())
    service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=global_gift),
        can_edit=real.can_edit,
        update=AsyncMock(),
    )
    monkeypatch.setattr(products_api, "ProductService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await products_api.update_product(
            product_id=global_gift.id,
            product_data=ProductUpdate(name="Nope"),
            db=SimpleNamespace(),
            current_user=current_user,
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_collection_rejects_other_home_gift():
    home_a = uuid4()
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, funeral_home_id=uuid4())
    service = GiftCollectionService(AsyncMock())
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [product])
        )
    )

    with pytest.raises(NotFoundException):
        await service._validate_products(
            [{"product_id": product_id}],
            funeral_home_id=home_a,
        )


@pytest.mark.asyncio
async def test_collection_allows_global_and_own_home_gifts():
    home_id = uuid4()
    global_id = uuid4()
    own_id = uuid4()
    products = [
        SimpleNamespace(id=global_id, funeral_home_id=None),
        SimpleNamespace(id=own_id, funeral_home_id=home_id),
    ]
    service = GiftCollectionService(AsyncMock())
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: products)
        )
    )

    await service._validate_products(
        [{"product_id": global_id}, {"product_id": own_id}],
        funeral_home_id=home_id,
    )


@pytest.mark.asyncio
async def test_zendora_default_rejects_home_scoped_gift():
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, funeral_home_id=uuid4())
    service = DefaultGiftCollectionService(AsyncMock())
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [product])
        )
    )

    with pytest.raises(NotFoundException):
        await service._validate_products(
            [{"product_id": product_id}],
            funeral_home_id=None,
            global_only=True,
        )


@pytest.mark.asyncio
async def test_funeral_home_default_allows_own_home_gift():
    home_id = uuid4()
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, funeral_home_id=home_id)
    service = DefaultGiftCollectionService(AsyncMock())
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: [product])
        )
    )

    await service._validate_products(
        [{"product_id": product_id}],
        funeral_home_id=home_id,
        global_only=False,
    )
