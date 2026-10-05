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
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")

from app.api import default_gift_collections as default_collections_api
from app.api import gift_collections as gift_collections_api
from app.models.default_gift_collection import DefaultCollectionScope
from app.models.gift_collection import GiftCollectionStatus
from app.models.user import UserRole
from app.schemas.default_gift_collection import (
    DefaultGiftCollectionCreate,
    DefaultGiftCollectionUpdate,
)
from app.schemas.gift_collection import GiftCollectionCreate, GiftCollectionCreateByFamilyAdmin
from app.services.default_gift_collection_service import DefaultGiftCollectionService
from app.services.gift_collection_service import GiftCollectionService


def make_pagination(page=1, page_size=20):
    return SimpleNamespace(
        page=page,
        page_size=page_size,
        offset=(page - 1) * page_size,
        limit=page_size,
    )


def make_user(role: UserRole, **kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        role=role.value,
        director_id=kwargs.get("director_id"),
        funeral_home_id=kwargs.get("funeral_home_id"),
        email=kwargs.get("email", "user@example.com"),
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "User"),
        funeral_home=kwargs.get("funeral_home"),
    )


def make_collection(**kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        family_admin_id=kwargs.get("family_admin_id", uuid4()),
        director_id=kwargs.get("director_id", uuid4()),
        funeral_home_id=kwargs.get("funeral_home_id"),
        source_default_collection_id=kwargs.get("source_default_collection_id"),
        public_slug=kwargs.get("public_slug", "template-copy"),
        status=kwargs.get("status", GiftCollectionStatus.DRAFT),
        title=kwargs.get("title", "Starter collection"),
        description=kwargs.get("description", "Copied from default"),
        logo_url=kwargs.get("logo_url"),
        header_image_url=kwargs.get("header_image_url"),
        primary_color=kwargs.get("primary_color"),
        secondary_color=kwargs.get("secondary_color"),
        delivery_address=kwargs.get("delivery_address"),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        published_at=kwargs.get("published_at"),
        products=kwargs.get("products", []),
        settings=kwargs.get("settings"),
        family_admin=kwargs.get("family_admin"),
        funeral_home=kwargs.get("funeral_home"),
        director=kwargs.get("director"),
    )


def make_default(**kwargs):
    owner_scope = kwargs.get("owner_scope", DefaultCollectionScope.ZENDORA.value)
    owner_user_id = kwargs.get("owner_user_id")
    if owner_scope == DefaultCollectionScope.ZENDORA.value:
        owner_user_id = None

    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        name=kwargs.get("name", "New baby"),
        description=kwargs.get("description", "Starter bundle"),
        owner_scope=owner_scope,
        owner_user_id=owner_user_id,
        owner_level_id=owner_user_id,
        funeral_home_id=kwargs.get("funeral_home_id"),
        collection_title=kwargs.get("collection_title", "Baby essentials"),
        collection_description=kwargs.get("collection_description", "Default description"),
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


def test_build_collection_payload_creates_detached_product_snapshot():
    service = DefaultGiftCollectionService(AsyncMock())
    product_id = uuid4()
    default_collection = make_default(
        collection_title="Template title",
        products=[SimpleNamespace(product_id=product_id, quantity=2)],
    )

    payload = service.build_collection_payload(default_collection)
    default_collection.products[0].quantity = 5

    assert payload["title"] == "Template title"
    assert payload["products"] == [{"product_id": product_id, "quantity": 2}]


@pytest.mark.asyncio
async def test_create_from_default_uses_defaults_when_not_overridden():
    service = GiftCollectionService(AsyncMock())
    service.create_with_products = AsyncMock(return_value="created-from-default")

    result = await service.create_from_default_collection(
        family_admin_id=uuid4(),
        director_id=uuid4(),
        default_collection_data={
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

    assert result == "created-from-default"
    service.create_with_products.assert_awaited_once()
    create_call = service.create_with_products.await_args.kwargs
    assert create_call["title"] == "Custom title"
    assert create_call["description"] == "Template description"
    assert create_call["products"][0]["quantity"] == 2


@pytest.mark.asyncio
async def test_create_from_default_allows_explicit_empty_product_override():
    service = GiftCollectionService(AsyncMock())
    service.create = AsyncMock(return_value="manual-empty-copy")
    service.create_with_products = AsyncMock()

    result = await service.create_from_default_collection(
        family_admin_id=uuid4(),
        director_id=uuid4(),
        default_collection_data={
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


def make_hierarchy_service(users, main_director_ids):
    """A service whose hierarchy lookups are served from dicts instead of the DB."""
    service = DefaultGiftCollectionService(AsyncMock())

    async def get_user(user_id):
        return users.get(user_id)

    async def get_main_director_id(funeral_home_id):
        return main_director_ids.get(funeral_home_id)

    service.get_user = get_user
    service.get_main_director_id = get_main_director_id
    return service


@pytest.mark.asyncio
async def test_owner_chain_walks_family_admin_up_to_zendora():
    funeral_home_id = uuid4()
    main_director = make_user(UserRole.DIRECTOR, funeral_home_id=funeral_home_id)
    director = make_user(UserRole.DIRECTOR, funeral_home_id=funeral_home_id)
    family_admin = make_user(
        UserRole.FAMILY_ADMIN,
        director_id=director.id,
        funeral_home_id=funeral_home_id,
    )
    service = make_hierarchy_service(
        {user.id: user for user in (main_director, director, family_admin)},
        {funeral_home_id: main_director.id},
    )

    chain = await service.owner_chain(family_admin)

    assert chain == [family_admin.id, director.id, main_director.id, None]


@pytest.mark.asyncio
async def test_owner_chain_of_main_director_is_self_then_zendora():
    funeral_home_id = uuid4()
    main_director = make_user(UserRole.DIRECTOR, funeral_home_id=funeral_home_id)
    service = make_hierarchy_service(
        {main_director.id: main_director}, {funeral_home_id: main_director.id}
    )

    assert await service.owner_chain(main_director) == [main_director.id, None]


@pytest.mark.asyncio
async def test_owner_chain_of_family_admin_without_director_uses_main_director():
    funeral_home_id = uuid4()
    main_director = make_user(UserRole.DIRECTOR, funeral_home_id=funeral_home_id)
    family_admin = make_user(
        UserRole.FAMILY_ADMIN, director_id=None, funeral_home_id=funeral_home_id
    )
    service = make_hierarchy_service(
        {main_director.id: main_director, family_admin.id: family_admin},
        {funeral_home_id: main_director.id},
    )

    chain = await service.owner_chain(family_admin)

    assert chain == [family_admin.id, main_director.id, None]


@pytest.mark.asyncio
async def test_owner_chain_of_super_admin_is_zendora_only():
    service = make_hierarchy_service({}, {})
    assert await service.owner_chain(make_user(UserRole.SUPER_ADMIN)) == [None]


@pytest.mark.asyncio
async def test_resolve_for_user_prefers_own_defaults():
    service = DefaultGiftCollectionService(AsyncMock())
    director = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    own = [make_default(
        owner_scope=DefaultCollectionScope.FUNERAL_HOME.value,
        owner_user_id=director.id,
    )]

    service.owner_chain = AsyncMock(return_value=[director.id, uuid4(), None])
    service.list_owned_by = AsyncMock(return_value=own)

    assert await service.resolve_for_user(director) == own
    assert service.list_owned_by.await_count == 1


@pytest.mark.asyncio
async def test_resolve_for_user_falls_back_to_nearest_upper_hand():
    service = DefaultGiftCollectionService(AsyncMock())
    main_director_id = uuid4()
    director = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    inherited = [make_default(
        owner_scope=DefaultCollectionScope.FUNERAL_HOME.value,
        owner_user_id=main_director_id,
    )]
    zendora = [make_default()]
    owned = {director.id: [], main_director_id: inherited, None: zendora}

    service.owner_chain = AsyncMock(return_value=[director.id, main_director_id, None])
    service.list_owned_by = AsyncMock(side_effect=lambda owner_id, **_: owned[owner_id])

    # The walk stops at the main director, so Zendora defaults stay hidden.
    assert await service.resolve_for_user(director) == inherited


@pytest.mark.asyncio
async def test_resolve_for_user_falls_back_to_zendora_when_hierarchy_is_empty():
    service = DefaultGiftCollectionService(AsyncMock())
    family_admin = make_user(UserRole.FAMILY_ADMIN, director_id=uuid4())
    zendora = [make_default()]

    service.owner_chain = AsyncMock(
        return_value=[family_admin.id, family_admin.director_id, None]
    )
    service.list_owned_by = AsyncMock(
        side_effect=lambda owner_id, **_: zendora if owner_id is None else []
    )

    assert await service.resolve_for_user(family_admin) == zendora


@pytest.mark.asyncio
async def test_can_manage_owner_covers_own_and_managed_families():
    funeral_home_id = uuid4()
    director = make_user(UserRole.DIRECTOR, funeral_home_id=funeral_home_id)
    own_family = make_user(
        UserRole.FAMILY_ADMIN, director_id=director.id, funeral_home_id=funeral_home_id
    )
    other_family = make_user(
        UserRole.FAMILY_ADMIN, director_id=uuid4(), funeral_home_id=uuid4()
    )
    other_director = make_user(UserRole.DIRECTOR, funeral_home_id=funeral_home_id)
    service = make_hierarchy_service(
        {user.id: user for user in (own_family, other_family, other_director)},
        {funeral_home_id: other_director.id},
    )

    assert await service.can_manage_owner(director, director.id) is True
    assert await service.can_manage_owner(director, own_family.id) is True
    assert await service.can_manage_owner(director, other_family.id) is False
    # The main director is an upper hand, so their defaults stay read-only.
    assert await service.can_manage_owner(director, other_director.id) is False
    # Only super admins own the Zendora pool.
    assert await service.can_manage_owner(director, None) is False


@pytest.mark.asyncio
async def test_main_director_manages_every_family_in_the_funeral_home():
    funeral_home_id = uuid4()
    main_director = make_user(UserRole.DIRECTOR, funeral_home_id=funeral_home_id)
    family_of_other_director = make_user(
        UserRole.FAMILY_ADMIN, director_id=uuid4(), funeral_home_id=funeral_home_id
    )
    service = make_hierarchy_service(
        {family_of_other_director.id: family_of_other_director},
        {funeral_home_id: main_director.id},
    )

    assert await service.can_manage_owner(main_director, family_of_other_director.id) is True


@pytest.mark.asyncio
async def test_family_admin_cannot_manage_any_defaults():
    family_admin = make_user(UserRole.FAMILY_ADMIN, director_id=uuid4())
    service = make_hierarchy_service({family_admin.id: family_admin}, {})

    assert await service.can_manage_owner(family_admin, family_admin.id) is False
    assert await service.can_manage_owner(family_admin, None) is False


@pytest.mark.asyncio
async def test_director_listing_returns_resolved_defaults(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    own = make_default(
        owner_scope=DefaultCollectionScope.FUNERAL_HOME.value,
        owner_user_id=current_user.id,
        products=[],
    )
    service = SimpleNamespace(
        resolve_for_user=AsyncMock(return_value=[own]),
        can_manage_owner=AsyncMock(return_value=True),
    )
    pagination = make_pagination()

    monkeypatch.setattr(
        default_collections_api, "DefaultGiftCollectionService", lambda _: service
    )

    response = await default_collections_api.list_default_gift_collections(
        owner_scope=None,
        funeral_home_id=None,
        owner_user_id=None,
        include_inactive=True,
        search=None,
        pagination=pagination,
        db=db,
        current_user=current_user,
    )

    assert service.resolve_for_user.await_args.kwargs["active_only"] is False
    assert len(response.items) == 1
    assert response.items[0].name == own.name
    assert response.items[0].can_edit is True
    assert response.items[0].is_inherited is False


@pytest.mark.asyncio
async def test_inherited_defaults_are_flagged_read_only(monkeypatch):
    db = SimpleNamespace()
    funeral_home_id = uuid4()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=funeral_home_id)
    inherited = make_default(
        owner_scope=DefaultCollectionScope.FUNERAL_HOME.value,
        owner_user_id=uuid4(),
        products=[],
    )
    service = SimpleNamespace(
        resolve_for_user=AsyncMock(return_value=[inherited]),
        can_manage_owner=AsyncMock(return_value=False),
    )

    monkeypatch.setattr(
        default_collections_api, "DefaultGiftCollectionService", lambda _: service
    )

    response = await default_collections_api.list_default_gift_collections(
        owner_scope=None,
        funeral_home_id=None,
        owner_user_id=None,
        include_inactive=False,
        search=None,
        pagination=make_pagination(),
        db=db,
        current_user=current_user,
    )

    assert response.items[0].can_edit is False
    assert response.items[0].is_inherited is True


@pytest.mark.asyncio
async def test_family_admin_sees_own_defaults_without_edit_rights(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.FAMILY_ADMIN, director_id=uuid4())
    own = make_default(
        owner_scope=DefaultCollectionScope.FUNERAL_HOME.value,
        owner_user_id=current_user.id,
        products=[],
    )
    service = SimpleNamespace(
        resolve_for_user=AsyncMock(return_value=[own]),
        can_manage_owner=AsyncMock(return_value=False),
    )

    monkeypatch.setattr(
        default_collections_api, "DefaultGiftCollectionService", lambda _: service
    )

    response = await default_collections_api.list_default_gift_collections(
        owner_scope=None,
        funeral_home_id=None,
        owner_user_id=None,
        include_inactive=False,
        search=None,
        pagination=make_pagination(),
        db=db,
        current_user=current_user,
    )

    assert response.items[0].owner_user_id == current_user.id
    assert response.items[0].is_inherited is False
    assert response.items[0].can_edit is False


@pytest.mark.asyncio
async def test_listing_another_users_defaults_requires_management(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    service = SimpleNamespace(can_manage_owner=AsyncMock(return_value=False))

    monkeypatch.setattr(
        default_collections_api, "DefaultGiftCollectionService", lambda _: service
    )

    with pytest.raises(HTTPException) as exc:
        await default_collections_api.list_default_gift_collections(
            owner_scope=None,
            funeral_home_id=None,
            owner_user_id=uuid4(),
            include_inactive=False,
            search=None,
            pagination=make_pagination(),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_can_include_inactive_defaults(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.SUPER_ADMIN)
    service = SimpleNamespace(
        list_collections=AsyncMock(return_value=([], 0)),
        can_manage_owner=AsyncMock(return_value=True),
    )
    pagination = make_pagination()

    monkeypatch.setattr(
        default_collections_api, "DefaultGiftCollectionService", lambda _: service
    )

    await default_collections_api.list_default_gift_collections(
        owner_scope=None,
        funeral_home_id=None,
        owner_user_id=None,
        include_inactive=True,
        search=None,
        pagination=pagination,
        db=db,
        current_user=current_user,
    )

    assert service.list_collections.await_args.kwargs["active_only"] is False


@pytest.mark.asyncio
async def test_director_cannot_modify_inherited_default(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    default_collection = make_default(
        owner_scope=DefaultCollectionScope.ZENDORA.value, is_active=True
    )
    service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=default_collection),
        can_manage_owner=AsyncMock(return_value=False),
        can_read=AsyncMock(return_value=True),
    )

    monkeypatch.setattr(
        default_collections_api, "DefaultGiftCollectionService", lambda _: service
    )

    with pytest.raises(HTTPException) as exc:
        await default_collections_api.update_default_gift_collection(
            default_collection_id=default_collection.id,
            collection_data=DefaultGiftCollectionUpdate(name="Blocked"),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403
    assert "read-only" in exc.value.detail


@pytest.mark.asyncio
async def test_director_creates_defaults_owned_by_themselves(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    created = make_default(
        owner_scope=DefaultCollectionScope.FUNERAL_HOME.value,
        owner_user_id=current_user.id,
        created_by=current_user.id,
    )
    service = SimpleNamespace(
        can_manage_owner=AsyncMock(return_value=True),
        create=AsyncMock(return_value=created),
        get_by_id=AsyncMock(return_value=created),
    )

    monkeypatch.setattr(
        default_collections_api, "DefaultGiftCollectionService", lambda _: service
    )

    response = await default_collections_api.create_default_gift_collection(
        collection_data=DefaultGiftCollectionCreate(name="Test default"),
        db=db,
        current_user=current_user,
    )

    assert service.create.await_args.kwargs["owner_user_id"] == current_user.id
    assert (
        service.create.await_args.kwargs["owner_scope"]
        == DefaultCollectionScope.FUNERAL_HOME
    )
    assert response.owner_user_id == current_user.id


@pytest.mark.asyncio
async def test_director_cannot_create_default_for_unmanaged_user(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    service = SimpleNamespace(can_manage_owner=AsyncMock(return_value=False))

    monkeypatch.setattr(
        default_collections_api, "DefaultGiftCollectionService", lambda _: service
    )

    with pytest.raises(HTTPException) as exc:
        await default_collections_api.create_default_gift_collection(
            collection_data=DefaultGiftCollectionCreate(
                name="Test default", owner_user_id=uuid4()
            ),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_family_admin_cannot_create_default(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.FAMILY_ADMIN, director_id=uuid4())
    service = SimpleNamespace(can_manage_owner=AsyncMock(return_value=False))

    monkeypatch.setattr(
        default_collections_api, "DefaultGiftCollectionService", lambda _: service
    )

    with pytest.raises(HTTPException) as exc:
        await default_collections_api.create_default_gift_collection(
            collection_data=DefaultGiftCollectionCreate(name="Test default"),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_can_create_and_deactivate_default(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    created = make_default(created_by=current_user.id)
    service = SimpleNamespace(
        can_manage_owner=AsyncMock(return_value=True),
        create=AsyncMock(return_value=created),
        get_by_id=AsyncMock(return_value=created),
        deactivate=AsyncMock(return_value=created),
    )

    monkeypatch.setattr(
        default_collections_api, "DefaultGiftCollectionService", lambda _: service
    )

    created_response = await default_collections_api.create_default_gift_collection(
        collection_data=DefaultGiftCollectionCreate(
            name="Test default",
            collection_title="Template title",
        ),
        db=db,
        current_user=current_user,
    )
    await default_collections_api.deactivate_default_gift_collection(
        default_collection_id=created.id,
        db=db,
        current_user=current_user,
    )

    service.create.assert_awaited_once()
    assert service.create.await_args.kwargs["owner_user_id"] is None
    assert (
        service.create.await_args.kwargs["owner_scope"] == DefaultCollectionScope.ZENDORA
    )
    service.deactivate.assert_awaited_once_with(created.id)
    assert created_response.created_by == current_user.id


@pytest.mark.asyncio
async def test_director_can_create_collection_from_default(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    funeral_home_id = uuid4()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=funeral_home_id)
    family_admin = make_user(
        UserRole.FAMILY_ADMIN,
        director_id=current_user.id,
        funeral_home_id=funeral_home_id,
        email="family@example.com",
    )
    created_collection = make_collection(
        family_admin_id=family_admin.id,
        director_id=current_user.id,
        funeral_home_id=funeral_home_id,
        family_admin=family_admin,
    )
    default_collection = make_default(products=[])
    background_tasks = BackgroundTasks()

    user_service = SimpleNamespace(get_by_email=AsyncMock(return_value=family_admin))
    default_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=default_collection),
        is_applicable_to_user=AsyncMock(return_value=True),
        build_collection_payload=lambda _: {"title": "Template title", "products": []},
    )
    collection_service = SimpleNamespace(
        create_from_default_collection=AsyncMock(return_value=created_collection),
        create_with_products=AsyncMock(),
        create=AsyncMock(),
        get_by_id=AsyncMock(return_value=created_collection),
    )

    monkeypatch.setattr(gift_collections_api, "UserService", lambda _: user_service)
    monkeypatch.setattr(
        gift_collections_api, "DefaultGiftCollectionService", lambda _: default_service
    )
    monkeypatch.setattr(
        gift_collections_api, "GiftCollectionService", lambda _: collection_service
    )

    response = await gift_collections_api.create_gift_collection(
        collection_data=GiftCollectionCreate(
            family_admin_email=family_admin.email,
            family_admin_first_name=family_admin.first_name,
            family_admin_last_name=family_admin.last_name,
            default_collection_id=default_collection.id,
            title="Director override",
        ),
        background_tasks=background_tasks,
        db=db,
        current_user=current_user,
    )

    collection_service.create_from_default_collection.assert_awaited_once()
    collection_service.create.assert_not_called()
    collection_service.create_with_products.assert_not_called()
    assert response.title == "Starter collection"


@pytest.mark.asyncio
async def test_family_admin_can_create_manual_collection_with_products(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    director_id = uuid4()
    current_user = make_user(
        UserRole.FAMILY_ADMIN, director_id=director_id, funeral_home_id=uuid4()
    )
    created_collection = make_collection(
        family_admin_id=current_user.id,
        director_id=director_id,
        funeral_home_id=current_user.funeral_home_id,
        family_admin=current_user,
    )
    collection_service = SimpleNamespace(
        create_with_products=AsyncMock(return_value=created_collection),
        create=AsyncMock(),
        get_by_id=AsyncMock(return_value=created_collection),
    )

    monkeypatch.setattr(
        gift_collections_api, "GiftCollectionService", lambda _: collection_service
    )
    monkeypatch.setattr(
        gift_collections_api,
        "DefaultGiftCollectionService",
        lambda _: SimpleNamespace(get_by_id=AsyncMock()),
    )
    monkeypatch.setattr(
        gift_collections_api, "UserService", lambda _: SimpleNamespace()
    )

    response = await gift_collections_api.create_gift_collection(
        collection_data=GiftCollectionCreateByFamilyAdmin(
            title="Manual collection",
            products=[{"product_id": uuid4(), "quantity": 1}],
        ),
        background_tasks=BackgroundTasks(),
        db=db,
        current_user=current_user,
    )

    collection_service.create_with_products.assert_awaited_once()
    collection_service.create.assert_not_called()
    assert response.family_admin_id == current_user.id


@pytest.mark.asyncio
async def test_family_admin_without_director_can_create_collection(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    current_user = make_user(UserRole.FAMILY_ADMIN, director_id=None, funeral_home_id=None)
    created_collection = make_collection(
        family_admin_id=current_user.id,
        director_id=None,
        funeral_home_id=None,
        family_admin=current_user,
    )
    collection_service = SimpleNamespace(
        create_with_products=AsyncMock(return_value=created_collection),
        create=AsyncMock(),
        get_by_id=AsyncMock(return_value=created_collection),
    )

    monkeypatch.setattr(
        gift_collections_api, "GiftCollectionService", lambda _: collection_service
    )
    monkeypatch.setattr(
        gift_collections_api,
        "DefaultGiftCollectionService",
        lambda _: SimpleNamespace(get_by_id=AsyncMock()),
    )
    monkeypatch.setattr(
        gift_collections_api, "UserService", lambda _: SimpleNamespace()
    )

    response = await gift_collections_api.create_gift_collection(
        collection_data=GiftCollectionCreateByFamilyAdmin(
            title="Unassigned collection",
            products=[{"product_id": uuid4(), "quantity": 1}],
        ),
        background_tasks=BackgroundTasks(),
        db=db,
        current_user=current_user,
    )

    collection_service.create_with_products.assert_awaited_once()
    assert collection_service.create_with_products.await_args.kwargs["director_id"] is None
    assert response.director_id is None
    assert response.family_admin_id == current_user.id


@pytest.mark.asyncio
async def test_list_gift_collections_is_scoped_to_director_funeral_home(monkeypatch):
    db = SimpleNamespace()
    funeral_home_id = uuid4()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=funeral_home_id)
    current_user.funeral_home = SimpleNamespace(
        id=funeral_home_id, director_id=current_user.id
    )
    collection = make_collection(funeral_home_id=funeral_home_id, director=current_user)
    service = SimpleNamespace(list_collections=AsyncMock(return_value=([collection], 1)))
    pagination = make_pagination()

    monkeypatch.setattr(gift_collections_api, "GiftCollectionService", lambda _: service)

    response = await gift_collections_api.list_gift_collections(
        funeral_home_id=uuid4(),
        director_id=None,
        family_admin_id=None,
        collection_status=None,
        search=None,
        pagination=pagination,
        db=db,
        current_user=current_user,
    )

    kwargs = service.list_collections.await_args.kwargs
    assert kwargs["funeral_home_id"] == funeral_home_id
    assert len(response.items) == 1
