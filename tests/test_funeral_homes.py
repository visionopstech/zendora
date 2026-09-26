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

from app.api import funeral_homes as funeral_homes_api
from app.core.exceptions import ConflictError, PermissionDenied
from app.models.user import UserRole
from app.schemas.funeral_home import AssignDirectorRequest, FuneralHomeCreate, SetMainDirectorRequest
from app.services.funeral_home_service import FuneralHomeService


def make_user(role: UserRole, **kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        role=role.value,
        funeral_home_id=kwargs.get("funeral_home_id"),
        director_id=kwargs.get("director_id"),
        email=kwargs.get("email", "user@example.com"),
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "User"),
        funeral_home=kwargs.get("funeral_home"),
        directed_funeral_home=kwargs.get("directed_funeral_home"),
    )


def make_funeral_home(**kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        name=kwargs.get("name", "Riverside Chapel"),
        description=kwargs.get("description"),
        email=kwargs.get("email", "chapel@example.com"),
        phone=kwargs.get("phone"),
        address=kwargs.get("address"),
        logo_url=kwargs.get("logo_url"),
        director_id=kwargs.get("director_id"),
        director=kwargs.get("director"),
        members=kwargs.get("members", []),
        is_active=kwargs.get("is_active", True),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        updated_at=kwargs.get("updated_at"),
    )


@pytest.mark.asyncio
async def test_add_director_rejects_non_director_role():
    funeral_home = make_funeral_home()
    family_admin = make_user(UserRole.FAMILY_ADMIN)
    service = FuneralHomeService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=funeral_home)
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: family_admin)
    )

    with pytest.raises(PermissionDenied):
        await service.add_director(funeral_home.id, family_admin.id)


@pytest.mark.asyncio
async def test_add_director_rejects_director_already_assigned_elsewhere():
    funeral_home = make_funeral_home()
    director = make_user(UserRole.DIRECTOR, funeral_home_id=uuid4())
    service = FuneralHomeService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=funeral_home)
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: director)
    )

    with pytest.raises(ConflictError) as exc:
        await service.add_director(funeral_home.id, director.id)

    assert "already assigned" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_add_director_allows_second_director_without_replacing_main():
    existing_director_id = uuid4()
    funeral_home = make_funeral_home(director_id=existing_director_id)
    director = make_user(UserRole.DIRECTOR, funeral_home_id=None)
    service = FuneralHomeService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=funeral_home)
    service.get_by_director = AsyncMock(return_value=None)
    service._cascade_funeral_home = AsyncMock()
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: director)
    )
    service.db.flush = AsyncMock()

    result = await service.add_director(funeral_home.id, director.id)

    assert funeral_home.director_id == existing_director_id
    assert director.funeral_home_id == funeral_home.id
    assert result == funeral_home


@pytest.mark.asyncio
async def test_remove_director_rejects_main_director():
    director_id = uuid4()
    funeral_home = make_funeral_home(director_id=director_id)
    director = make_user(UserRole.DIRECTOR, id=director_id, funeral_home_id=funeral_home.id)
    service = FuneralHomeService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=funeral_home)
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: director)
    )

    with pytest.raises(ConflictError) as exc:
        await service.remove_director(funeral_home.id, director.id)

    assert "main director" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_remove_director_main_can_remove_other():
    home_id = uuid4()
    main = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    main.funeral_home = make_funeral_home(id=home_id, director_id=main.id)
    funeral_home = make_funeral_home(id=home_id, director_id=main.id)
    other = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    service = FuneralHomeService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=funeral_home)
    service._cascade_funeral_home = AsyncMock()
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: other)
    )
    service.db.flush = AsyncMock()

    result = await service.remove_director(funeral_home.id, other.id, actor=main)

    assert other.funeral_home_id is None
    assert result == funeral_home


@pytest.mark.asyncio
async def test_remove_director_other_director_forbidden():
    home_id = uuid4()
    main_id = uuid4()
    actor = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    actor.funeral_home = make_funeral_home(id=home_id, director_id=main_id)
    funeral_home = make_funeral_home(id=home_id, director_id=main_id)
    other = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    service = FuneralHomeService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=funeral_home)
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: other)
    )

    with pytest.raises(PermissionDenied):
        await service.remove_director(funeral_home.id, other.id, actor=actor)


@pytest.mark.asyncio
async def test_create_funeral_home_assigns_director_when_provided(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    director = make_user(UserRole.DIRECTOR)
    created = make_funeral_home(director_id=director.id, director=director)
    service = SimpleNamespace(
        create=AsyncMock(return_value=created),
        get_by_id=AsyncMock(return_value=created),
        list_directors=AsyncMock(return_value=[director]),
        count_families=AsyncMock(return_value=0),
    )
    current_user = make_user(UserRole.SUPER_ADMIN)

    monkeypatch.setattr(funeral_homes_api, "FuneralHomeService", lambda _: service)

    response = await funeral_homes_api.create_funeral_home(
        funeral_home_data=FuneralHomeCreate(name="Riverside Chapel", director_id=director.id),
        db=db,
        current_user=current_user,
    )

    service.create.assert_awaited_once()
    assert response.director_id == director.id
    assert response.family_count == 0
    assert len(response.directors) == 1


@pytest.mark.asyncio
async def test_get_my_funeral_home_returns_409_when_unassigned():
    db = SimpleNamespace()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=None)

    with pytest.raises(HTTPException) as exc:
        await funeral_homes_api.get_my_funeral_home(db=db, current_user=current_user)

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_add_director_endpoint_maps_conflict(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    service = SimpleNamespace(
        add_director=AsyncMock(side_effect=ConflictError("already assigned"))
    )

    monkeypatch.setattr(funeral_homes_api, "FuneralHomeService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await funeral_homes_api.add_director(
            funeral_home_id=uuid4(),
            request=AssignDirectorRequest(user_id=uuid4()),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_set_main_director_endpoint_maps_conflict(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    service = SimpleNamespace(
        set_main_director=AsyncMock(side_effect=ConflictError("must already belong"))
    )

    monkeypatch.setattr(funeral_homes_api, "FuneralHomeService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await funeral_homes_api.set_main_director(
            funeral_home_id=uuid4(),
            request=SetMainDirectorRequest(user_id=uuid4()),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 409
