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
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")

from app.api import directors as directors_api
from app.api import families as families_api
from app.core.exceptions import ConflictError, NotFoundException, PermissionDenied
from app.models.gift_collection import GiftCollectionStatus
from app.models.user import UserRole
from app.schemas.common import DeliveryAddress
from app.schemas.family import FamilyCreate, FamilyUpdate
from app.schemas.user import DirectorStatusUpdate
from app.services.director_scope import (
    assert_can_delete_director,
    director_can_read_family,
    director_data_scope,
    is_main_director,
)
from app.services.director_status_service import DirectorStatusService
from app.services.gift_collection_service import (
    MAX_COLLECTIONS_PER_DIRECTOR,
    MAX_PUBLISHED_PER_DIRECTOR,
    GiftCollectionService,
)
from app.services.user_management_service import UserManagementService
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
        deceased_first_name=kwargs.get("deceased_first_name"),
        deceased_last_name=kwargs.get("deceased_last_name"),
        address=kwargs.get("address"),
        director=kwargs.get("director"),
    )


def family_create_payload(**kwargs) -> FamilyCreate:
    return FamilyCreate(
        first_name=kwargs.get("first_name", "Alex"),
        last_name=kwargs.get("last_name", "Rivera"),
        email=kwargs.get("email", "family@example.com"),
        deceased_first_name=kwargs.get("deceased_first_name", "Sam"),
        deceased_last_name=kwargs.get("deceased_last_name", "Rivera"),
        address=kwargs.get(
            "address",
            DeliveryAddress(
                street="1 Main",
                city="Austin",
                state="TX",
                zip_code="78701",
            ),
        ),
        director_id=kwargs.get("director_id"),
        funeral_home_id=kwargs.get("funeral_home_id"),
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
async def test_create_without_director_skips_director_collection_limit():
    service = GiftCollectionService(AsyncMock())
    service.count_by_director = AsyncMock(return_value=MAX_COLLECTIONS_PER_DIRECTOR)
    service._ensure_unique_slug = AsyncMock(return_value="slug123abcde")
    service.db.add = lambda _collection: None
    service.db.flush = AsyncMock()
    service.db.refresh = AsyncMock()

    collection = await service.create(family_admin_id=uuid4(), director_id=None)

    service.count_by_director.assert_not_awaited()
    assert collection.director_id is None


@pytest.mark.asyncio
async def test_publish_without_director_skips_director_published_limit():
    collection = SimpleNamespace(
        id=uuid4(),
        family_admin_id=uuid4(),
        director_id=None,
        status=GiftCollectionStatus.DRAFT.value,
    )
    service = GiftCollectionService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=collection)
    service.get_published_by_family_admin = AsyncMock(return_value=None)
    service.count_by_director = AsyncMock(return_value=MAX_PUBLISHED_PER_DIRECTOR)
    service.db.flush = AsyncMock()
    service.db.refresh = AsyncMock()

    published = await service.publish(collection.id, collection.family_admin_id)

    service.count_by_director.assert_not_awaited()
    assert published.status == GiftCollectionStatus.PUBLISHED.value


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


def _mock_family_create(monkeypatch, created, user_service=None, funeral_home=None):
    user_service = user_service or SimpleNamespace(
        get_by_email=AsyncMock(return_value=None),
        get_by_id=AsyncMock(return_value=None),
        create_family_admin_with_director=AsyncMock(return_value=(created, "tmp-pass")),
        db=SimpleNamespace(),
    )
    family_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=created),
        get_collection_stats=AsyncMock(return_value={created.id: {"count": 0}}),
    )
    funeral_home_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=funeral_home),
    )

    monkeypatch.setattr(families_api, "UserService", lambda _: user_service)
    monkeypatch.setattr(families_api, "FamilyService", lambda _: family_service)
    monkeypatch.setattr(families_api, "FuneralHomeService", lambda _: funeral_home_service)

    class FakeEmail:
        async def send_family_admin_credentials_email(self, *_args, **_kwargs):
            return True

    import app.services.email_service as email_module
    monkeypatch.setattr(email_module, "EmailService", FakeEmail)
    return user_service, funeral_home_service


@pytest.mark.asyncio
async def test_family_create_requires_funeral_home():
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=None)

    with pytest.raises(ConflictError) as exc:
        await families_api.create_family(
            family_data=family_create_payload(),
            background_tasks=BackgroundTasks(),
            db=SimpleNamespace(),
            current_user=current_user,
        )

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
        deceased_first_name="Sam",
        deceased_last_name="Rivera",
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
    user_service, _ = _mock_family_create(monkeypatch, created)

    response = await families_api.create_family(
        family_data=family_create_payload(),
        background_tasks=BackgroundTasks(),
        db=db,
        current_user=current_user,
    )

    assert response.email == "family@example.com"
    assert response.first_name == "Alex"
    assert response.deceased_first_name == "Sam"
    assert response.deceased_last_name == "Rivera"
    user_service.create_family_admin_with_director.assert_awaited_once()
    kwargs = user_service.create_family_admin_with_director.await_args.kwargs
    assert kwargs["director_id"] == current_user.id
    assert kwargs["funeral_home_id"] == home_id


@pytest.mark.asyncio
async def test_super_admin_can_create_family_without_assignment(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    created = make_user(
        UserRole.FAMILY_ADMIN,
        email="family@example.com",
        director_id=None,
        funeral_home_id=None,
        deceased_first_name="Sam",
        deceased_last_name="Rivera",
        address={
            "street": "1 Main",
            "city": "Austin",
            "state": "TX",
            "zip_code": "78701",
            "country": "USA",
        },
    )
    user_service, _ = _mock_family_create(monkeypatch, created)

    response = await families_api.create_family(
        family_data=family_create_payload(),
        background_tasks=BackgroundTasks(),
        db=db,
        current_user=current_user,
    )

    assert response.email == "family@example.com"
    assert response.director is None
    assert response.funeral_home is None
    kwargs = user_service.create_family_admin_with_director.await_args.kwargs
    assert kwargs["director_id"] is None
    assert kwargs["funeral_home_id"] is None


@pytest.mark.asyncio
async def test_super_admin_can_create_family_with_director(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    home_id = uuid4()
    director = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    current_user = make_user(UserRole.SUPER_ADMIN)
    created = make_user(
        UserRole.FAMILY_ADMIN,
        email="family@example.com",
        director_id=director.id,
        funeral_home_id=home_id,
        deceased_first_name="Sam",
        deceased_last_name="Rivera",
        funeral_home=make_home(id=home_id, director_id=director.id),
        director=director,
    )
    user_service = SimpleNamespace(
        get_by_email=AsyncMock(return_value=None),
        get_by_id=AsyncMock(return_value=director),
        create_family_admin_with_director=AsyncMock(return_value=(created, "tmp-pass")),
        db=SimpleNamespace(),
    )
    _mock_family_create(monkeypatch, created, user_service=user_service)

    response = await families_api.create_family(
        family_data=family_create_payload(director_id=director.id),
        background_tasks=BackgroundTasks(),
        db=db,
        current_user=current_user,
    )

    assert response.director.id == director.id
    kwargs = user_service.create_family_admin_with_director.await_args.kwargs
    assert kwargs["director_id"] == director.id
    assert kwargs["funeral_home_id"] == home_id


@pytest.mark.asyncio
async def test_super_admin_can_create_family_with_funeral_home_only(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    home_id = uuid4()
    home = make_home(id=home_id)
    current_user = make_user(UserRole.SUPER_ADMIN)
    created = make_user(
        UserRole.FAMILY_ADMIN,
        email="family@example.com",
        director_id=None,
        funeral_home_id=home_id,
        deceased_first_name="Sam",
        deceased_last_name="Rivera",
        funeral_home=home,
    )
    user_service, funeral_home_service = _mock_family_create(
        monkeypatch, created, funeral_home=home
    )

    response = await families_api.create_family(
        family_data=family_create_payload(funeral_home_id=home_id),
        background_tasks=BackgroundTasks(),
        db=db,
        current_user=current_user,
    )

    assert response.funeral_home.id == home_id
    funeral_home_service.get_by_id.assert_awaited_once_with(home_id)
    kwargs = user_service.create_family_admin_with_director.await_args.kwargs
    assert kwargs["director_id"] is None
    assert kwargs["funeral_home_id"] == home_id


@pytest.mark.asyncio
async def test_super_admin_family_create_rejects_unknown_director(monkeypatch):
    current_user = make_user(UserRole.SUPER_ADMIN)
    missing_director_id = uuid4()
    user_service = SimpleNamespace(
        get_by_email=AsyncMock(return_value=None),
        get_by_id=AsyncMock(return_value=None),
        create_family_admin_with_director=AsyncMock(),
        db=SimpleNamespace(),
    )
    monkeypatch.setattr(families_api, "UserService", lambda _: user_service)

    with pytest.raises(NotFoundException) as exc:
        await families_api.create_family(
            family_data=family_create_payload(director_id=missing_director_id),
            background_tasks=BackgroundTasks(),
            db=SimpleNamespace(),
            current_user=current_user,
        )

    assert "Director not found" in str(exc.value)
    user_service.create_family_admin_with_director.assert_not_awaited()


@pytest.mark.asyncio
async def test_super_admin_family_create_rejects_non_director(monkeypatch):
    current_user = make_user(UserRole.SUPER_ADMIN)
    family_admin = make_user(UserRole.FAMILY_ADMIN)
    user_service = SimpleNamespace(
        get_by_email=AsyncMock(return_value=None),
        get_by_id=AsyncMock(return_value=family_admin),
        create_family_admin_with_director=AsyncMock(),
        db=SimpleNamespace(),
    )
    monkeypatch.setattr(families_api, "UserService", lambda _: user_service)

    with pytest.raises(PermissionDenied) as exc:
        await families_api.create_family(
            family_data=family_create_payload(director_id=family_admin.id),
            background_tasks=BackgroundTasks(),
            db=SimpleNamespace(),
            current_user=current_user,
        )

    assert "must belong to a DIRECTOR user" in str(exc.value)
    user_service.create_family_admin_with_director.assert_not_awaited()


@pytest.mark.asyncio
async def test_family_update_endpoint(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    home_id = uuid4()
    current_user = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    family = make_user(
        UserRole.FAMILY_ADMIN,
        first_name="Alex",
        last_name="Rivera",
        email="family@example.com",
        director_id=current_user.id,
        funeral_home_id=home_id,
        deceased_first_name="Sam",
        deceased_last_name="Rivera",
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
    updated = make_user(
        UserRole.FAMILY_ADMIN,
        id=family.id,
        first_name="Alex",
        last_name="Rivera",
        email="family@example.com",
        director_id=current_user.id,
        funeral_home_id=home_id,
        deceased_first_name="Jordan",
        deceased_last_name="Lee",
        address={
            "street": "9 Oak",
            "city": "Dallas",
            "state": "TX",
            "zip_code": "75201",
            "country": "USA",
        },
        funeral_home=family.funeral_home,
        director=current_user,
    )
    family_service = SimpleNamespace(
        get_by_id=AsyncMock(side_effect=[family, updated]),
        update=AsyncMock(return_value=updated),
        get_collection_stats=AsyncMock(return_value={family.id: {"count": 1}}),
    )
    monkeypatch.setattr(families_api, "FamilyService", lambda _: family_service)

    response = await families_api.update_family(
        family_admin_id=family.id,
        family_data=FamilyUpdate(
            deceased_first_name="Jordan",
            deceased_last_name="Lee",
            address=DeliveryAddress(
                street="9 Oak",
                city="Dallas",
                state="TX",
                zip_code="75201",
            ),
        ),
        db=db,
        current_user=current_user,
    )

    assert response.deceased_first_name == "Jordan"
    assert response.deceased_last_name == "Lee"
    assert response.address.street == "9 Oak"
    family_service.update.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_family_update_rejects_unassigned_director(monkeypatch):
    home_id = uuid4()
    current_user = make_user(
        UserRole.DIRECTOR,
        funeral_home_id=home_id,
        funeral_home=make_home(id=home_id, director_id=uuid4()),
    )
    family = make_user(
        UserRole.FAMILY_ADMIN,
        director_id=uuid4(),
        funeral_home_id=home_id,
    )
    family_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=family),
        update=AsyncMock(),
    )
    monkeypatch.setattr(families_api, "FamilyService", lambda _: family_service)
    db = SimpleNamespace(commit=AsyncMock())

    with pytest.raises(HTTPException) as exc:
        await families_api.update_family(
            family_admin_id=family.id,
            family_data=FamilyUpdate(first_name="Alex"),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403
    family_service.update.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_family_admin_cannot_change_active_status(monkeypatch):
    family = make_user(UserRole.FAMILY_ADMIN)
    family_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=family),
        update=AsyncMock(),
    )
    monkeypatch.setattr(families_api, "FamilyService", lambda _: family_service)

    with pytest.raises(HTTPException) as exc:
        await families_api.update_family(
            family_admin_id=family.id,
            family_data=FamilyUpdate(is_active=False),
            db=SimpleNamespace(commit=AsyncMock()),
            current_user=family,
        )

    assert exc.value.status_code == 403
    family_service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_family_admin_can_be_created_without_director():
    created = make_user(UserRole.FAMILY_ADMIN, director_id=None)
    service = UserManagementService(AsyncMock())
    service.get_by_email = AsyncMock(return_value=None)
    service.get_by_id = AsyncMock(return_value=created)
    service.db.add = lambda _user: None
    service.db.flush = AsyncMock()

    user = await service.create(
        email="family@example.com",
        password="password123",
        role=UserRole.FAMILY_ADMIN,
        first_name="Alex",
        last_name="Rivera",
        deceased_first_name="Sam",
        deceased_last_name="Rivera",
    )

    assert user.director_id is None
    assert user.role == UserRole.FAMILY_ADMIN.value


@pytest.mark.asyncio
async def test_family_admin_update_can_clear_director_id(monkeypatch):
    family = make_user(UserRole.FAMILY_ADMIN, director_id=uuid4())
    service = UserManagementService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=family)
    service.db.flush = AsyncMock()
    monkeypatch.setattr(
        "app.services.user_management_service.FinancialService",
        lambda _db: SimpleNamespace(
            get_director_commission=AsyncMock(return_value=None),
            upsert_director_commission=AsyncMock(),
        ),
    )

    user = await service.update(
        user_id=family.id,
        director_id=None,
        director_id_provided=True,
    )

    assert user.director_id is None


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


def test_super_admin_can_delete_any_director():
    admin = make_user(UserRole.SUPER_ADMIN)
    home_id = uuid4()
    main = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    other = make_user(
        UserRole.DIRECTOR,
        funeral_home_id=home_id,
        funeral_home=make_home(id=home_id, director_id=main.id),
    )

    assert_can_delete_director(admin, main)
    assert_can_delete_director(admin, other)


def test_main_director_can_delete_other_non_main_director():
    home_id = uuid4()
    main = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    other = make_user(
        UserRole.DIRECTOR,
        funeral_home_id=home_id,
        funeral_home=make_home(id=home_id, director_id=main.id),
    )

    assert_can_delete_director(main, other)


def test_main_director_cannot_delete_self():
    home_id = uuid4()
    main = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)

    with pytest.raises(PermissionDenied):
        assert_can_delete_director(main, main)


def test_main_director_cannot_delete_director_from_other_home():
    home_id = uuid4()
    main = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    stranger = make_user(
        UserRole.DIRECTOR,
        funeral_home_id=uuid4(),
        funeral_home=make_home(id=uuid4(), director_id=uuid4()),
    )

    with pytest.raises(PermissionDenied):
        assert_can_delete_director(main, stranger)


def test_non_main_director_cannot_delete_directors():
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

    with pytest.raises(PermissionDenied):
        assert_can_delete_director(actor, target)


@pytest.mark.asyncio
async def test_delete_director_super_admin_clears_main_assignment():
    home_id = uuid4()
    home = make_home(id=home_id, director_id=uuid4())
    target = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, funeral_home=home)
    home.director_id = target.id
    admin = make_user(UserRole.SUPER_ADMIN)
    service = UserManagementService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=target)
    service.db.flush = AsyncMock()
    service.db.delete = AsyncMock()

    await service.delete_director(target.id, actor=admin)

    assert home.director_id is None
    service.db.delete.assert_awaited_once_with(target)


@pytest.mark.asyncio
async def test_delete_director_main_can_delete_other():
    home_id = uuid4()
    main = make_user(UserRole.DIRECTOR, funeral_home_id=home_id, is_main=True)
    other = make_user(
        UserRole.DIRECTOR,
        funeral_home_id=home_id,
        funeral_home=make_home(id=home_id, director_id=main.id),
    )
    service = UserManagementService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=other)
    service.db.flush = AsyncMock()
    service.db.delete = AsyncMock()

    await service.delete_director(other.id, actor=main)

    service.db.delete.assert_awaited_once_with(other)


@pytest.mark.asyncio
async def test_delete_director_endpoint_allows_super_admin(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.SUPER_ADMIN)
    service = SimpleNamespace(delete_director=AsyncMock())
    monkeypatch.setattr(directors_api, "UserManagementService", lambda _: service)

    await directors_api.delete_director(
        user_id=uuid4(),
        db=db,
        current_user=current_user,
    )

    service.delete_director.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_director_endpoint_maps_permission_denied(monkeypatch):
    db = SimpleNamespace(commit=AsyncMock())
    current_user = make_user(UserRole.DIRECTOR)
    service = SimpleNamespace(
        delete_director=AsyncMock(side_effect=PermissionDenied("Only the main director"))
    )
    monkeypatch.setattr(directors_api, "UserManagementService", lambda _: service)

    with pytest.raises(HTTPException) as exc:
        await directors_api.delete_director(
            user_id=uuid4(),
            db=db,
            current_user=current_user,
        )

    assert exc.value.status_code == 403
