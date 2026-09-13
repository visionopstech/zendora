import os
from datetime import datetime
from decimal import Decimal
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

from app.api import directors as directors_api
from app.api import families as families_api
from app.core.exceptions import ConflictError, PermissionDenied
from app.models.gift_collection import GiftCollectionStatus
from app.models.user import UserRole
from app.schemas.common import DeliveryAddress
from app.schemas.family import FamilyCreate
from app.schemas.user import DirectorStatusUpdate
from app.services.director_scope import director_can_read_family, director_data_scope, is_main_director
from app.services.director_status_service import DirectorStatusService
from app.services.gift_collection_service import (
    MAX_COLLECTIONS_PER_DIRECTOR,
    MAX_PUBLISHED_PER_DIRECTOR,
    GiftCollectionService,
)
from app.services.vendor_service import VendorService


def make_home(**kwargs):
    home_id = kwargs.get("id", uuid4())
    director_id = kwargs.get("director_id")
    return SimpleNamespace(
        id=home_id,
        director_id=director_id,
        name=kwargs.get("name", "Chapel"),
    )


def make_user(role: UserRole, **kwargs):
    funeral_home = kwargs.get("funeral_home")
    user_id = kwargs.get("id", uuid4())
    if funeral_home is None and kwargs.get("funeral_home_id") and kwargs.get("is_main"):
        funeral_home = make_home(
            id=kwargs["funeral_home_id"],
            director_id=user_id,
        )
    return SimpleNamespace(
        id=user_id,
        role=role.value,
        email=kwargs.get("email", "user@example.com"),
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "User"),
        funeral_home_id=kwargs.get("funeral_home_id"),
        director_id=kwargs.get("director_id"),
        funeral_home=funeral_home,
        directed_funeral_home=kwargs.get("directed_funeral_home"),
        is_active=kwargs.get("is_active", True),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        deceased_name=kwargs.get("deceased_name"),
        address=kwargs.get("address"),
        director=kwargs.get("director"),
    )


def test_main_director_scope_uses_funeral_home():
    home_id = uuid4()
    director = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)

    assert is_main_director(director) is True
    scope = director_data_scope(director)
    assert scope.is_main is True
    assert scope.funeral_home_id == home_id
    assert scope.director_id is None


def test_other_director_scope_uses_own_id():
    home_id = uuid4()
    main_id = uuid4()
    director = make_user(
        UserRole.DIRECTOR,
        funeral_home_id=home_id,
        funeral_home=make_home(id=home_id, director_id=main_id),
    )

    assert is_main_director(director) is False
    scope = director_data_scope(director)
    assert scope.is_main is False
    assert scope.director_id == director.id
    assert scope.funeral_home_id is None


def test_main_director_can_read_home_family_but_other_cannot():
    home_id = uuid4()
    main = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    other = make_user(
        UserRole.DIRECTOR,
        funeral_home_id=home_id,
        funeral_home=make_home(id=home_id, director_id=main.id),
    )
    family = make_user(
        UserRole.FAMILY_ADMIN,
        funeral_home_id=home_id,
        director_id=other.id,
    )

    assert director_can_read_family(main, family) is True
    assert director_can_read_family(other, family) is True
    stranger = make_user(UserRole.DIRECTOR, funeral_home_id=home_id)
    stranger.funeral_home = make_home(id=home_id, director_id=main.id)
    other_family = make_user(
        UserRole.FAMILY_ADMIN,
        funeral_home_id=home_id,
        director_id=main.id,
    )
    assert director_can_read_family(other, other_family) is False


@pytest.mark.asyncio
async def test_create_rejects_sixth_collection_for_director():
    service = GiftCollectionService(AsyncMock())
    service.count_by_director = AsyncMock(return_value=MAX_COLLECTIONS_PER_DIRECTOR)

    with pytest.raises(ConflictError) as exc:
        await service.create(
            family_admin_id=uuid4(),
            director_id=uuid4(),
        )

    assert "at most 5" in str(exc.value)


@pytest.mark.asyncio
async def test_publish_rejects_fourth_published_collection_for_director():
    collection = SimpleNamespace(
        id=uuid4(),
        family_admin_id=uuid4(),
        director_id=uuid4(),
        status=GiftCollectionStatus.DRAFT.value,
    )
    service = GiftCollectionService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=collection)
    service.get_published_by_family_admin = AsyncMock(return_value=None)
    service.count_by_director = AsyncMock(return_value=MAX_PUBLISHED_PER_DIRECTOR)

    with pytest.raises(ConflictError) as exc:
        await service.publish(collection.id, collection.family_admin_id)

    assert "at most 3" in str(exc.value)


@pytest.mark.asyncio
async def test_vendor_create_rejects_duplicate_email():
    existing = make_user(UserRole.VENDOR, email="vendor@example.com")
    db = AsyncMock()
    service = VendorService(db)
    user_service = SimpleNamespace(get_by_email=AsyncMock(return_value=existing))

    from app.services import vendor_service as vendor_service_module

    original = vendor_service_module.UserManagementService
    vendor_service_module.UserManagementService = lambda _: user_service
    try:
        with pytest.raises(ConflictError):
            await service.create(
                name="Flowers Co",
                email="vendor@example.com",
                password="password1",
                first_name="Pat",
                last_name="Lee",
                standard_processing_time=3,
            )
    finally:
        vendor_service_module.UserManagementService = original


@pytest.mark.asyncio
async def test_family_create_requires_funeral_home():
    from app.core.exceptions import ConflictError as AppConflict
    from app.dependencies.auth import require_director_with_funeral_home

    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=None)

    with pytest.raises(AppConflict) as exc:
        await require_director_with_funeral_home(current_user=current_user)

    assert "not assigned to a funeral home" in str(exc.value)


@pytest.mark.asyncio
async def test_family_create_endpoint(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    home_id = uuid4()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    created = make_user(
        UserRole.FAMILY_ADMIN,
        first_name="Alex",
        last_name="Rivera",
        email="family@example.com",
        director_id=current_user.id,
        funeral_home_id=home_id,
        deceased_name="Sam Rivera",
        address={
            "street": "1 Main",
            "city": "Austin",
            "state": "TX",
            "zip_code": "78701",
            "country": "USA",
        },
        funeral_home=make_home(id=home_id, director_id=current_user.id),
        director=current_user,
    )
    user_service = SimpleNamespace(
        get_by_email=AsyncMock(return_value=None),
        create_family_admin_with_director=AsyncMock(return_value=(created, "tmp-pass")),
    )
    family_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=created),
        get_collection_stats=AsyncMock(return_value={created.id: {"count": 0}}),
    )

    monkeypatch.setattr(families_api, "UserService", lambda _: user_service)
    monkeypatch.setattr(families_api, "FamilyService", lambda _: family_service)
    monkeypatch.setattr(families_api, "EmailService", lambda: SimpleNamespace(
        send_family_admin_credentials_email=AsyncMock()
    ), raising=False)

    class FakeEmail:
        async def send_family_admin_credentials_email(self, *_args, **_kwargs):
            return True

    import app.services.email_service as email_module
    monkeypatch.setattr(email_module, "EmailService", FakeEmail)

    response = await families_api.create_family(
        family_data=FamilyCreate(
            first_name="Alex",
            last_name="Rivera",
            email="family@example.com",
            deceased_name="Sam Rivera",
            address=DeliveryAddress(
                street="1 Main",
                city="Austin",
                state="TX",
                zip_code="78701",
            ),
        ),
        background_tasks=BackgroundTasks(),
        db=db,
        current_user=current_user,
    )

    assert response.email == "family@example.com"
    assert response.first_name == "Alex"
    assert response.deceased_name == "Sam Rivera"
    user_service.create_family_admin_with_director.assert_awaited_once()


@pytest.mark.asyncio
async def test_director_status_rejects_main_target():
    home_id = uuid4()
    main = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    service = DirectorStatusService(AsyncMock())
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: main)
    )

    with pytest.raises(ConflictError) as exc:
        await service.set_active(main, main.id, False)

    assert "main director" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_director_status_main_can_toggle_other():
    home_id = uuid4()
    main = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    other = make_user(
        UserRole.DIRECTOR,
        funeral_home_id=home_id,
        funeral_home=make_home(id=home_id, director_id=main.id),
        is_active=True,
    )
    service = DirectorStatusService(AsyncMock())
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: other)
    )
    service.db.flush = AsyncMock()
    service.db.refresh = AsyncMock()

    updated = await service.set_active(main, other.id, False)
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_director_status_other_director_forbidden():
    home_id = uuid4()
    main_id = uuid4()
    actor = make_user(
        UserRole.DIRECTOR,
        funeral_home_id=home_id,
        funeral_home=make_home(id=home_id, director_id=main_id),
    )
    target = make_user(
        UserRole.DIRECTOR,
        funeral_home_id=home_id,
        funeral_home=make_home(id=home_id, director_id=main_id),
    )
    service = DirectorStatusService(AsyncMock())
    service.db.execute = AsyncMock(
        return_value=SimpleNamespace(scalar_one_or_none=lambda: target)
    )

    with pytest.raises(PermissionDenied):
        await service.set_active(actor, target.id, False)


@pytest.mark.asyncio
async def test_director_statistics_endpoint(monkeypatch):
    db = SimpleNamespace()
    home_id = uuid4()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    stats = {
        "total_gift_collections": 4,
        "total_families_enrolled": 2,
        "orders_count": 7,
        "sales": Decimal("120.50"),
        "total_commissions": Decimal("18.00"),
    }
    service = SimpleNamespace(get_statistics=AsyncMock(return_value=stats))
    monkeypatch.setattr(directors_api, "DirectorStatisticsService", lambda _: service)

    response = await directors_api.get_director_statistics(
        db=db, current_user=current_user
    )

    assert response.total_gift_collections == 4
    assert response.sales == Decimal("120.50")
    assert response.total_commissions == Decimal("18.00")


@pytest.mark.asyncio
async def test_director_status_endpoint_maps_conflict(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    service = SimpleNamespace(
        set_active=AsyncMock(side_effect=ConflictError("Cannot change the main director"))
    )
    monkeypatch.setattr(directors_api, "DirectorStatusService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await directors_api.update_director_status(
            user_id=uuid4(),
            payload=DirectorStatusUpdate(is_active=False),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 409
