import os
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test")
os.environ.setdefault("SENDGRID_API_KEY", "test")
os.environ.setdefault("SENDGRID_FROM_EMAIL", "test@example.com")

from app.api import admin_wishlist as admin_wishlist_api
from app.api import manager as manager_api
from app.api import wishlist_templates as wishlist_templates_api
from app.models.user import UserRole
from app.models.wishlist import WishlistStatus
from app.schemas.wishlist import WishlistCreate, WishlistCreateByAdmin
from app.schemas.wishlist_template import WishlistTemplateCreate, WishlistTemplateUpdate
from app.services.wishlist_service import WishlistService
from app.services.wishlist_template_service import WishlistTemplateService


def make_user(role: UserRole, **kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        role=role.value,
        manager_id=kwargs.get("manager_id"),
        email=kwargs.get("email", "user@example.com"),
        full_name=kwargs.get("full_name", "Test User"),
    )


def make_wishlist(**kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        admin_id=kwargs.get("admin_id", uuid4()),
        manager_id=kwargs.get("manager_id", uuid4()),
        public_slug=kwargs.get("public_slug", "template-copy"),
        status=kwargs.get("status", WishlistStatus.DRAFT),
        title=kwargs.get("title", "Starter wishlist"),
        description=kwargs.get("description", "Copied from template"),
        logo_url=kwargs.get("logo_url"),
        header_image_url=kwargs.get("header_image_url"),
        primary_color=kwargs.get("primary_color"),
        secondary_color=kwargs.get("secondary_color"),
        delivery_address=kwargs.get("delivery_address"),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        published_at=kwargs.get("published_at"),
        products=kwargs.get("products", []),
        settings=kwargs.get("settings"),
    )


def make_template(**kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        name=kwargs.get("name", "New baby"),
        description=kwargs.get("description", "Starter bundle"),
        wishlist_title=kwargs.get("wishlist_title", "Baby essentials"),
        wishlist_description=kwargs.get("wishlist_description", "Template description"),
        logo_url=kwargs.get("logo_url"),
        header_image_url=kwargs.get("header_image_url"),
        primary_color=kwargs.get("primary_color"),
        secondary_color=kwargs.get("secondary_color"),
        delivery_address=kwargs.get("delivery_address"),
        is_active=kwargs.get("is_active", True),
        created_by=kwargs.get("created_by"),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        updated_at=kwargs.get("updated_at"),
        products=kwargs.get("products", []),
    )


def test_build_wishlist_payload_creates_detached_product_snapshot():
    template_service = WishlistTemplateService(AsyncMock())
    product_id = uuid4()
    template = make_template(
        wishlist_title="Template title",
        products=[SimpleNamespace(product_id=product_id, quantity=2)],
    )

    payload = template_service.build_wishlist_payload(template)
    template.products[0].quantity = 5

    assert payload["title"] == "Template title"
    assert payload["products"] == [{"product_id": product_id, "quantity": 2}]


@pytest.mark.asyncio
async def test_create_from_template_uses_template_defaults_when_not_overridden():
    service = WishlistService(AsyncMock())
    service.create_with_products = AsyncMock(return_value="created-from-template")

    result = await service.create_from_template(
        admin_id=uuid4(),
        manager_id=uuid4(),
        template_data={
            "title": "Template title",
            "description": "Template description",
            "logo_url": "template-logo",
            "header_image_url": "template-header",
            "primary_color": "#111111",
            "secondary_color": "#222222",
            "delivery_address": {"city": "Austin"},
            "products": [{"product_id": uuid4(), "quantity": 2}],
        },
        overrides={
            "title": "Custom title",
            "description": None,
            "logo_url": None,
            "header_image_url": None,
            "primary_color": None,
            "secondary_color": None,
            "delivery_address": None,
            "products": None,
        },
        override_fields={"title"},
    )

    assert result == "created-from-template"
    service.create_with_products.assert_awaited_once()
    create_call = service.create_with_products.await_args.kwargs
    assert create_call["title"] == "Custom title"
    assert create_call["description"] == "Template description"
    assert create_call["products"][0]["quantity"] == 2


@pytest.mark.asyncio
async def test_create_from_template_allows_explicit_empty_product_override():
    service = WishlistService(AsyncMock())
    service.create = AsyncMock(return_value="manual-empty-copy")
    service.create_with_products = AsyncMock()

    result = await service.create_from_template(
        admin_id=uuid4(),
        manager_id=uuid4(),
        template_data={
            "title": "Template title",
            "description": "Template description",
            "logo_url": None,
            "header_image_url": None,
            "primary_color": None,
            "secondary_color": None,
            "delivery_address": None,
            "products": [{"product_id": uuid4(), "quantity": 3}],
        },
        overrides={
            "title": None,
            "description": None,
            "logo_url": None,
            "header_image_url": None,
            "primary_color": None,
            "secondary_color": None,
            "delivery_address": None,
            "products": [],
        },
        override_fields={"products"},
    )

    assert result == "manual-empty-copy"
    service.create.assert_awaited_once()
    service.create_with_products.assert_not_called()


@pytest.mark.asyncio
async def test_list_templates_filters_inactive_for_manager(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.MANAGER)
    template = make_template(products=[])
    service = SimpleNamespace(list_templates=AsyncMock(return_value=[template]))

    monkeypatch.setattr(wishlist_templates_api, "WishlistTemplateService", lambda _: service)

    response = await wishlist_templates_api.list_wishlist_templates(
        include_inactive=True,
        db=db,
        current_user=current_user,
    )

    service.list_templates.assert_awaited_once_with(active_only=True, load_products=True)
    assert len(response) == 1
    assert response[0].name == template.name


@pytest.mark.asyncio
async def test_super_admin_can_include_inactive_templates(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.SUPER_ADMIN)
    service = SimpleNamespace(list_templates=AsyncMock(return_value=[]))

    monkeypatch.setattr(wishlist_templates_api, "WishlistTemplateService", lambda _: service)

    await wishlist_templates_api.list_wishlist_templates(
        include_inactive=True,
        db=db,
        current_user=current_user,
    )

    service.list_templates.assert_awaited_once_with(active_only=False, load_products=True)


@pytest.mark.asyncio
async def test_manager_cannot_access_inactive_template(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.MANAGER)
    service = SimpleNamespace(get_by_id=AsyncMock(return_value=make_template(is_active=False)))

    monkeypatch.setattr(wishlist_templates_api, "WishlistTemplateService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await wishlist_templates_api.get_wishlist_template(
            template_id=uuid4(),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_template_requires_super_admin():
    db = SimpleNamespace()
    current_user = make_user(UserRole.ADMIN, manager_id=uuid4())

    with pytest.raises(HTTPException) as exc:
        await wishlist_templates_api.create_wishlist_template(
            template_data=WishlistTemplateCreate(name="Test template"),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_can_create_and_deactivate_template(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    created_template = make_template(created_by=current_user.id)
    service = SimpleNamespace(
        create=AsyncMock(return_value=created_template),
        get_by_id=AsyncMock(return_value=created_template),
        deactivate=AsyncMock(return_value=created_template),
    )

    monkeypatch.setattr(wishlist_templates_api, "WishlistTemplateService", lambda _: service)

    created = await wishlist_templates_api.create_wishlist_template(
        template_data=WishlistTemplateCreate(
            name="Test template",
            wishlist_title="Template title",
        ),
        db=db,
        current_user=current_user,
    )
    await wishlist_templates_api.delete_wishlist_template(
        template_id=created_template.id,
        db=db,
        current_user=current_user,
    )

    service.create.assert_awaited_once()
    service.deactivate.assert_awaited_once_with(created_template.id)
    assert created.created_by == current_user.id


@pytest.mark.asyncio
async def test_super_admin_can_update_template(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    updated_template = make_template(created_by=current_user.id, name="Updated name")
    service = SimpleNamespace(
        update=AsyncMock(return_value=updated_template),
        get_by_id=AsyncMock(return_value=updated_template),
    )

    monkeypatch.setattr(wishlist_templates_api, "WishlistTemplateService", lambda _: service)

    response = await wishlist_templates_api.update_wishlist_template(
        template_id=updated_template.id,
        template_data=WishlistTemplateUpdate(name="Updated name"),
        db=db,
        current_user=current_user,
    )

    service.update.assert_awaited_once()
    assert response.name == "Updated name"


@pytest.mark.asyncio
async def test_admin_cannot_update_template():
    db = SimpleNamespace()
    current_user = make_user(UserRole.ADMIN, manager_id=uuid4())

    with pytest.raises(HTTPException) as exc:
        await wishlist_templates_api.update_wishlist_template(
            template_id=uuid4(),
            template_data=WishlistTemplateUpdate(name="Blocked"),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_manager_can_create_wishlist_from_template(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    current_user = make_user(UserRole.MANAGER)
    admin_user = make_user(UserRole.ADMIN, manager_id=current_user.id, email="admin@example.com")
    created_wishlist = make_wishlist(admin_id=admin_user.id, manager_id=current_user.id)
    template = make_template(products=[])
    background_tasks = BackgroundTasks()

    user_service = SimpleNamespace(get_by_email=AsyncMock(return_value=admin_user))
    template_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=template),
        build_wishlist_payload=lambda _: {"title": "Template title", "products": []},
    )
    wishlist_service = SimpleNamespace(
        create_from_template=AsyncMock(return_value=created_wishlist),
        create_with_products=AsyncMock(),
        create=AsyncMock(),
    )

    monkeypatch.setattr(manager_api, "UserService", lambda _: user_service)
    monkeypatch.setattr(manager_api, "WishlistTemplateService", lambda _: template_service)
    monkeypatch.setattr(manager_api, "WishlistService", lambda _: wishlist_service)

    response = await manager_api.create_wishlist(
        wishlist_data=WishlistCreate(
            admin_email=admin_user.email,
            admin_full_name=admin_user.full_name,
            template_id=template.id,
            title="Manager override",
        ),
        background_tasks=background_tasks,
        db=db,
        current_user=current_user,
    )

    wishlist_service.create_from_template.assert_awaited_once()
    wishlist_service.create.assert_not_called()
    wishlist_service.create_with_products.assert_not_called()
    assert response.title == "Starter wishlist"


@pytest.mark.asyncio
async def test_admin_can_still_create_manual_wishlist_with_products(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    current_user = make_user(UserRole.ADMIN, manager_id=uuid4())
    created_wishlist = make_wishlist(admin_id=current_user.id, manager_id=current_user.manager_id)
    wishlist_service = SimpleNamespace(
        create_with_products=AsyncMock(return_value=created_wishlist),
        create=AsyncMock(),
    )

    monkeypatch.setattr(admin_wishlist_api, "WishlistService", lambda _: wishlist_service)
    monkeypatch.setattr(
        admin_wishlist_api,
        "WishlistTemplateService",
        lambda _: SimpleNamespace(get_by_id=AsyncMock()),
    )

    response = await admin_wishlist_api.create_my_wishlist(
        wishlist_data=WishlistCreateByAdmin(
            title="Manual wishlist",
            products=[{"product_id": uuid4(), "quantity": 1}],
        ),
        db=db,
        current_user=current_user,
    )

    wishlist_service.create_with_products.assert_awaited_once()
    wishlist_service.create.assert_not_called()
    assert response.admin_id == current_user.id
