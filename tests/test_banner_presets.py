import os
from datetime import datetime
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

from app.api import banner_presets as banner_presets_api
from app.core.exceptions import PermissionDenied
from app.models.banner_preset import BannerPresetScope
from app.models.user import UserRole
from app.schemas.banner_preset import BannerPresetCreate, BannerPresetUpdate
from app.services.banner_preset_service import BannerPresetService


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
        funeral_home_id=kwargs.get("funeral_home_id"),
        email=kwargs.get("email", "user@example.com"),
    )


def make_banner(**kwargs):
    owner_scope = kwargs.get("owner_scope", BannerPresetScope.ZENDORA.value)
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        name=kwargs.get("name", "Floral"),
        image_url=kwargs.get("image_url", "https://example.com/floral.jpg"),
        owner_scope=owner_scope,
        funeral_home_id=kwargs.get("funeral_home_id"),
        created_by=kwargs.get("created_by"),
        sort_order=kwargs.get("sort_order", 0),
        is_active=kwargs.get("is_active", True),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        updated_at=kwargs.get("updated_at"),
        is_zendora_banner=owner_scope == BannerPresetScope.ZENDORA.value,
    )


def test_super_admin_can_read_and_edit_any_banner():
    service = BannerPresetService(AsyncMock())
    admin = make_user(UserRole.SUPER_ADMIN)
    zendora = make_banner()
    home_banner = make_banner(
        owner_scope=BannerPresetScope.FUNERAL_HOME.value,
        funeral_home_id=uuid4(),
    )

    assert service.can_read(admin, zendora) is True
    assert service.can_edit(admin, zendora) is True
    assert service.can_read(admin, home_banner) is True
    assert service.can_edit(admin, home_banner) is True


def test_director_sees_zendora_read_only_and_edits_own_home():
    service = BannerPresetService(AsyncMock())
    home_id = uuid4()
    other_home_id = uuid4()
    director = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    zendora = make_banner()
    own = make_banner(
        owner_scope=BannerPresetScope.FUNERAL_HOME.value,
        funeral_home_id=home_id,
    )
    other = make_banner(
        owner_scope=BannerPresetScope.FUNERAL_HOME.value,
        funeral_home_id=other_home_id,
    )

    assert service.can_read(director, zendora) is True
    assert service.can_edit(director, zendora) is False
    assert service.can_read(director, own) is True
    assert service.can_edit(director, own) is True
    assert service.can_read(director, other) is False
    assert service.can_edit(director, other) is False


def test_family_sees_zendora_and_own_home_but_cannot_edit():
    service = BannerPresetService(AsyncMock())
    home_id = uuid4()
    family = make_user(UserRole.FAMILY_ADMIN, funeral_home_id=home_id)
    zendora = make_banner()
    own = make_banner(
        owner_scope=BannerPresetScope.FUNERAL_HOME.value,
        funeral_home_id=home_id,
    )
    other = make_banner(
        owner_scope=BannerPresetScope.FUNERAL_HOME.value,
        funeral_home_id=uuid4(),
    )

    assert service.can_read(family, zendora) is True
    assert service.can_edit(family, zendora) is False
    assert service.can_read(family, own) is True
    assert service.can_edit(family, own) is False
    assert service.can_read(family, other) is False


def test_create_scope_is_forced_from_caller():
    service = BannerPresetService(AsyncMock())
    admin = make_user(UserRole.SUPER_ADMIN)
    home_id = uuid4()
    director = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    family = make_user(UserRole.FAMILY_ADMIN, funeral_home_id=home_id)

    assert service.resolve_create_scope(admin) == (BannerPresetScope.ZENDORA, None)
    assert service.resolve_create_scope(director) == (
        BannerPresetScope.FUNERAL_HOME,
        home_id,
    )

    with pytest.raises(PermissionDenied):
        service.resolve_create_scope(family)

    with pytest.raises(PermissionDenied):
        service.resolve_create_scope(make_user(UserRole.DIRECTOR, funeral_home_id=None))


@pytest.mark.asyncio
async def test_create_funeral_home_banner_requires_home():
    service = BannerPresetService(AsyncMock())
    with pytest.raises(PermissionDenied):
        await service.create(
            created_by=uuid4(),
            name="Missing home",
            image_url="https://example.com/b.jpg",
            owner_scope=BannerPresetScope.FUNERAL_HOME,
            funeral_home_id=None,
        )


@pytest.mark.asyncio
async def test_family_cannot_create_banner(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.FAMILY_ADMIN, funeral_home_id=uuid4())
    service = BannerPresetService(AsyncMock())

    monkeypatch.setattr(banner_presets_api, "BannerPresetService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await banner_presets_api.create_banner_preset(
            banner_data=BannerPresetCreate(
                name="Custom",
                image_url="https://example.com/b.jpg",
            ),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_director_creates_funeral_home_banner(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    home_id = uuid4()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    created = make_banner(
        owner_scope=BannerPresetScope.FUNERAL_HOME.value,
        funeral_home_id=home_id,
        created_by=current_user.id,
    )
    service = SimpleNamespace(
        resolve_create_scope=BannerPresetService(AsyncMock()).resolve_create_scope,
        create=AsyncMock(return_value=created),
        get_by_id=AsyncMock(return_value=created),
        can_edit=lambda user, banner: True,
    )

    monkeypatch.setattr(banner_presets_api, "BannerPresetService", lambda _: service)

    response = await banner_presets_api.create_banner_preset(
        banner_data=BannerPresetCreate(
            name="Chapel",
            image_url="https://example.com/chapel.jpg",
        ),
        db=db,
        current_user=current_user,
    )

    assert service.create.await_args.kwargs["owner_scope"] == BannerPresetScope.FUNERAL_HOME
    assert service.create.await_args.kwargs["funeral_home_id"] == home_id
    assert response.can_edit is True
    assert response.funeral_home_id == home_id


@pytest.mark.asyncio
async def test_super_admin_creates_zendora_banner_and_can_deactivate(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    created = make_banner(created_by=current_user.id)
    service = SimpleNamespace(
        resolve_create_scope=BannerPresetService(AsyncMock()).resolve_create_scope,
        create=AsyncMock(return_value=created),
        get_by_id=AsyncMock(return_value=created),
        deactivate=AsyncMock(return_value=make_banner(is_active=False, id=created.id)),
        can_edit=lambda user, banner: True,
        can_read=lambda user, banner: True,
    )

    monkeypatch.setattr(banner_presets_api, "BannerPresetService", lambda _: service)

    created_response = await banner_presets_api.create_banner_preset(
        banner_data=BannerPresetCreate(
            name="Floral",
            image_url="https://example.com/floral.jpg",
        ),
        db=db,
        current_user=current_user,
    )
    assert service.create.await_args.kwargs["owner_scope"] == BannerPresetScope.ZENDORA
    assert created_response.owner_scope == BannerPresetScope.ZENDORA

    deactivated = await banner_presets_api.deactivate_banner_preset(
        banner_id=created.id,
        db=db,
        current_user=current_user,
    )
    assert deactivated.is_active is False


@pytest.mark.asyncio
async def test_director_cannot_edit_zendora_banner(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    banner = make_banner()
    real = BannerPresetService(AsyncMock())
    service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=banner),
        can_edit=real.can_edit,
        can_read=real.can_read,
    )

    monkeypatch.setattr(banner_presets_api, "BannerPresetService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await banner_presets_api.update_banner_preset(
            banner_id=banner.id,
            banner_data=BannerPresetUpdate(name="Blocked"),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403
    assert "read-only" in exc.value.detail


@pytest.mark.asyncio
async def test_family_list_uses_active_only_even_when_include_inactive(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.FAMILY_ADMIN, funeral_home_id=uuid4())
    service = SimpleNamespace(
        list_for_user=AsyncMock(return_value=([], 0)),
        can_edit=lambda user, banner: False,
    )

    monkeypatch.setattr(banner_presets_api, "BannerPresetService", lambda _: service)

    await banner_presets_api.list_banner_presets(
        include_inactive=True,
        pagination=make_pagination(),
        db=db,
        current_user=current_user,
    )

    assert service.list_for_user.await_args.kwargs["active_only"] is True


@pytest.mark.asyncio
async def test_director_can_include_inactive(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    service = SimpleNamespace(
        list_for_user=AsyncMock(return_value=([], 0)),
        can_edit=lambda user, banner: False,
    )

    monkeypatch.setattr(banner_presets_api, "BannerPresetService", lambda _: service)

    await banner_presets_api.list_banner_presets(
        include_inactive=True,
        pagination=make_pagination(),
        db=db,
        current_user=current_user,
    )

    assert service.list_for_user.await_args.kwargs["active_only"] is False


@pytest.mark.asyncio
async def test_family_cannot_view_other_home_banner(monkeypatch):
    db = SimpleNamespace()
    current_user = make_user(UserRole.FAMILY_ADMIN, funeral_home_id=uuid4())
    banner = make_banner(
        owner_scope=BannerPresetScope.FUNERAL_HOME.value,
        funeral_home_id=uuid4(),
    )
    real = BannerPresetService(AsyncMock())
    service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=banner),
        can_read=real.can_read,
        can_edit=real.can_edit,
    )

    monkeypatch.setattr(banner_presets_api, "BannerPresetService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await banner_presets_api.get_banner_preset(
            banner_id=banner.id,
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_vendor_cannot_list_banners():
    with pytest.raises(HTTPException) as exc:
        await banner_presets_api.list_banner_presets(
            include_inactive=False,
            pagination=make_pagination(),
            db=SimpleNamespace(),
            current_user=make_user(UserRole.VENDOR),
        )

    assert exc.value.status_code == 403
