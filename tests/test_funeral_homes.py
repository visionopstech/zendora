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
os.environ.setdefault("SENDGRID_API_KEY", "test")
os.environ.setdefault("SENDGRID_FROM_EMAIL", "test@example.com")

from app.api import funeral_homes as funeral_homes_api
from app.core.exceptions import ConflictError, PermissionDenied
from app.models.user import UserRole
from app.schemas.funeral_home import AssignDirectorRequest, FuneralHomeCreate
from app.services.funeral_home_service import FuneralHomeService


def make_user(role: UserRole, **kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        role=role.value,
        funeral_home_id=kwargs.get("funeral_home_id"),
        director_id=kwargs.get("director_id"),
        email=kwargs.get("email", "user@example.com"),
        full_name=kwargs.get("full_name", "Test User"),
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
        is_active=kwargs.get("is_active", True),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        updated_at=kwargs.get("updated_at"),
    )


@pytest.mark.asyncio
async def test_assign_director_rejects_non_director_role():
    funeral_home = make_funeral_home()
    family_admin = make_user(UserRole.FAMILY_ADMIN)
    service = FuneralHomeService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=funeral_home)
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: family_admin)
    )

    with pytest.raises(PermissionDenied):
        await service.assign_director(funeral_home.id, family_admin.id)


@pytest.mark.asyncio
async def test_assign_director_rejects_director_already_assigned_elsewhere():
    funeral_home = make_funeral_home()
    other_home = make_funeral_home(name="Other Chapel")
    director = make_user(UserRole.DIRECTOR)
    service = FuneralHomeService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=funeral_home)
    service.get_by_director = AsyncMock(return_value=other_home)
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: director)
    )

    with pytest.raises(ConflictError) as exc:
        await service.assign_director(funeral_home.id, director.id)

    assert "already assigned" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_assign_director_rejects_home_that_already_has_a_director():
    existing_director_id = uuid4()
    funeral_home = make_funeral_home(director_id=existing_director_id)
    director = make_user(UserRole.DIRECTOR)
    service = FuneralHomeService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=funeral_home)
    service.get_by_director = AsyncMock(return_value=None)
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: director)
    )

    with pytest.raises(ConflictError) as exc:
        await service.assign_director(funeral_home.id, director.id)

    assert "already has a director" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_create_funeral_home_assigns_director_when_provided(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    director = make_user(UserRole.DIRECTOR)
    created = make_funeral_home(director_id=director.id, director=director)
    service = SimpleNamespace(
        create=AsyncMock(return_value=created),
        get_by_id=AsyncMock(return_value=created),
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


@pytest.mark.asyncio
async def test_get_my_funeral_home_returns_409_when_unassigned():
    db = SimpleNamespace()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=None)

    with pytest.raises(HTTPException) as exc:
        await funeral_homes_api.get_my_funeral_home(db=db, current_user=current_user)

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_assign_director_endpoint_maps_conflict(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    service = SimpleNamespace(
        assign_director=AsyncMock(side_effect=ConflictError("already assigned"))
    )

    monkeypatch.setattr(funeral_homes_api, "FuneralHomeService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await funeral_homes_api.assign_director(
            funeral_home_id=uuid4(),
            request=AssignDirectorRequest(user_id=uuid4()),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 409
