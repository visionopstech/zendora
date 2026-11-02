import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from passlib.hash import django_pbkdf2_sha256
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")

from app.api.integrations_foveo import require_foveo_sync_secret, sync_foveo
from app.core.exceptions import PermissionDenied
from app.core.security import hash_password, verify_password
from app.models.foveo_sync_event import FoveoSyncEvent
from app.models.funeral_home import FuneralHome
from app.models.user import User, UserRole
from app.schemas.foveo_sync import (
    FoveoAddress,
    FoveoEntityStatus,
    FoveoEventType,
    FoveoFamilyBlock,
    FoveoFuneralHomeBlock,
    FoveoSyncRequest,
    FoveoUserBlock,
)
from app.services.auth_service import AuthService
from app.services.foveo_sync_service import FoveoSyncService
from app.services.user_management_service import UserManagementService
from app.services.user_service import UserService
from app.utils.foveo import FOVEO_PASSWORD_MANAGED_MESSAGE, is_placeholder_email

DJANGO_HASH = django_pbkdf2_sha256.hash("foveo-password")
FOVEO_SECRET = "test-foveo-secret"


def _column_key(expr):
    key = getattr(expr, "key", None)
    if key:
        return key
    clauses = getattr(expr, "clauses", None)
    if clauses is not None:
        for clause in clauses:
            found = _column_key(clause)
            if found:
                return found
    for attr in ("clause_expr", "element", "orig"):
        inner = getattr(expr, attr, None)
        if inner is not None and inner is not expr:
            found = _column_key(inner)
            if found:
                return found
    return None


def _bind_value(expr):
    if isinstance(expr, BindParameter):
        return expr.value
    return getattr(expr, "value", expr)


def _extract_filters(clause):
    filters = {}

    def walk(node):
        if node is None:
            return
        if isinstance(node, BooleanClauseList):
            for child in node.clauses:
                walk(child)
            return
        if isinstance(node, BinaryExpression):
            key = _column_key(node.left)
            if key:
                filters[key] = _bind_value(node.right)

    walk(clause)
    return filters


class FakeResult:
    def __init__(self, row=None):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class FakeSession:
    def __init__(self):
        self.users = []
        self.funeral_homes = []
        self.events = []

    def add(self, obj):
        if isinstance(obj, User) and obj not in self.users:
            if obj.id is None:
                obj.id = uuid4()
            self.users.append(obj)
        elif isinstance(obj, FuneralHome) and obj not in self.funeral_homes:
            if obj.id is None:
                obj.id = uuid4()
            self.funeral_homes.append(obj)
        elif isinstance(obj, FoveoSyncEvent) and obj not in self.events:
            self.events.append(obj)

    async def flush(self):
        for user in self.users:
            if user.id is None:
                user.id = uuid4()
        for home in self.funeral_homes:
            if home.id is None:
                home.id = uuid4()

    async def commit(self):
        return None

    async def execute(self, stmt):
        entity = stmt.column_descriptions[0]["entity"]
        filters = _extract_filters(stmt.whereclause)
        if entity is User:
            collection = self.users
        elif entity is FuneralHome:
            collection = self.funeral_homes
        elif entity is FoveoSyncEvent:
            collection = self.events
        else:
            collection = []

        matches = []
        for obj in collection:
            if _matches(obj, filters):
                matches.append(obj)
        return FakeResult(matches[0] if matches else None)


def _matches(obj, filters) -> bool:
    for key, expected in filters.items():
        actual = getattr(obj, key, None)
        if key == "email" and isinstance(actual, str) and isinstance(expected, str):
            if actual.lower() != expected.lower():
                return False
        elif actual != expected:
            return False
    return True


def _home_block(**kwargs):
    data = dict(
        foveo_id=45,
        name="Acme Funeral Home",
        email="info@acme.com",
        phone="+15555550100",
        address=FoveoAddress(
            street="1 Main St",
            city="Austin",
            state="TX",
            zip_code="78701",
            country="USA",
        ),
        is_active=True,
    )
    data.update(kwargs)
    return FoveoFuneralHomeBlock(**data)


def _director_block(**kwargs):
    data = dict(
        foveo_user_id=10,
        email="director@acme.com",
        first_name="Pat",
        last_name="Lee",
        password_hash=DJANGO_HASH,
        is_active=True,
    )
    data.update(kwargs)
    return FoveoUserBlock(**data)


def _family_block(**kwargs):
    data = dict(
        foveo_user_id=12,
        email="family@example.com",
        first_name="Sam",
        last_name="River",
        password_hash=DJANGO_HASH,
        is_active=True,
        deceased_first_name="Jordan",
        deceased_last_name="River",
        address=FoveoAddress(
            street="9 Oak Ave",
            city="Austin",
            state="TX",
            zip_code="78702",
            country="USA",
        ),
    )
    data.update(kwargs)
    return FoveoFamilyBlock(**data)


def _payload(**kwargs):
    data = dict(
        event_id=uuid4(),
        event=FoveoEventType.STREAM_CREATED,
        foveo_stream_id=123,
        funeral_home=_home_block(),
        main_director=_director_block(),
    )
    data.update(kwargs)
    return FoveoSyncRequest(**data)


def _service():
    return FoveoSyncService(FakeSession())


def test_django_hash_verifies_and_bcrypt_still_works():
    assert verify_password("foveo-password", DJANGO_HASH)
    assert not verify_password("wrong-password", DJANGO_HASH)
    bcrypt_hash = hash_password("zendora-password")
    assert bcrypt_hash.startswith("$2")
    assert verify_password("zendora-password", bcrypt_hash)


def test_placeholder_email_detection():
    domains = ["foveo.org"]
    assert is_placeholder_email("family_abcde@foveo.org", domains)
    assert is_placeholder_email("tukios_nok@foveo.org", domains)
    assert not is_placeholder_email("staff@foveo.org", domains)
    assert not is_placeholder_email("family_abcde@example.com", domains)


@pytest.mark.asyncio
async def test_require_secret_missing_is_503(monkeypatch):
    monkeypatch.setattr("app.api.integrations_foveo.settings.foveo_sync_secret", None)
    with pytest.raises(HTTPException) as exc:
        await require_foveo_sync_secret(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="x")
        )
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_require_secret_bad_token_is_401(monkeypatch):
    monkeypatch.setattr("app.api.integrations_foveo.settings.foveo_sync_secret", FOVEO_SECRET)
    with pytest.raises(HTTPException) as exc:
        await require_foveo_sync_secret(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="nope")
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_secret_accepts_matching_token(monkeypatch):
    monkeypatch.setattr("app.api.integrations_foveo.settings.foveo_sync_secret", FOVEO_SECRET)
    await require_foveo_sync_secret(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=FOVEO_SECRET)
    )


@pytest.mark.asyncio
async def test_sync_creates_funeral_home_directors_and_family():
    service = _service()
    payload = _payload(
        stream_director=_director_block(
            foveo_user_id=11, email="stream@acme.com", first_name="Alex"
        ),
        family=_family_block(),
    )
    result = await service.sync(payload)

    assert result.funeral_home.status == FoveoEntityStatus.CREATED
    assert result.main_director.status == FoveoEntityStatus.CREATED
    assert result.stream_director.status == FoveoEntityStatus.CREATED
    assert result.family.status == FoveoEntityStatus.CREATED

    home = service.db.funeral_homes[0]
    main = next(u for u in service.db.users if u.foveo_user_id == 10)
    stream = next(u for u in service.db.users if u.foveo_user_id == 11)
    family = next(u for u in service.db.users if u.foveo_user_id == 12)

    assert home.director_id == main.id
    assert stream.funeral_home_id == home.id
    assert stream.id != home.director_id
    assert family.role == UserRole.FAMILY_ADMIN.value
    assert family.director_id == stream.id
    assert family.password_hash == DJANGO_HASH
    assert verify_password("foveo-password", family.password_hash)


@pytest.mark.asyncio
async def test_update_by_foveo_user_id():
    service = _service()
    first = await service.sync(_payload(event_id=uuid4()))
    second = await service.sync(
        _payload(
            event_id=uuid4(),
            event=FoveoEventType.STREAM_UPDATED,
            main_director=_director_block(first_name="Patricia"),
        )
    )
    assert first.main_director.status == FoveoEntityStatus.CREATED
    assert second.main_director.status == FoveoEntityStatus.UPDATED
    assert second.main_director.id == first.main_director.id
    main = next(u for u in service.db.users if u.foveo_user_id == 10)
    assert main.first_name == "Patricia"


@pytest.mark.asyncio
async def test_preexisting_email_is_skipped_and_left_unchanged():
    service = _service()
    existing = User(
        id=uuid4(),
        email="director@acme.com",
        password_hash=hash_password("local-password"),
        first_name="Local",
        last_name="Owner",
        role=UserRole.DIRECTOR.value,
        is_active=True,
        foveo_user_id=None,
    )
    original_hash = existing.password_hash
    service.db.users.append(existing)

    result = await service.sync(_payload())
    assert result.main_director.status == FoveoEntityStatus.SKIPPED_EXISTING_USER
    assert result.main_director.id == existing.id
    assert existing.foveo_user_id is None
    assert existing.password_hash == original_hash
    assert existing.first_name == "Local"
    assert service.db.funeral_homes[0].director_id != existing.id


@pytest.mark.asyncio
async def test_email_collision_on_linked_user_is_conflict():
    service = _service()
    await service.sync(_payload())
    other = User(
        id=uuid4(),
        email="taken@acme.com",
        role=UserRole.VISITOR.value,
        is_active=True,
    )
    service.db.users.append(other)

    result = await service.sync(
        _payload(
            event_id=uuid4(),
            event=FoveoEventType.STREAM_UPDATED,
            main_director=_director_block(email="taken@acme.com"),
        )
    )
    assert result.main_director.status == FoveoEntityStatus.CONFLICT
    main = next(u for u in service.db.users if u.foveo_user_id == 10)
    assert main.email == "director@acme.com"
    assert other.email == "taken@acme.com"
    assert other.foveo_user_id is None


@pytest.mark.asyncio
async def test_unlinked_main_director_is_not_replaced():
    service = _service()
    native = User(
        id=uuid4(),
        email="native@acme.com",
        role=UserRole.DIRECTOR.value,
        is_active=True,
        foveo_user_id=None,
    )
    home = FuneralHome(
        id=uuid4(),
        name="Acme Funeral Home",
        foveo_funeral_home_id=45,
        director_id=native.id,
        is_active=True,
    )
    service.db.users.append(native)
    service.db.funeral_homes.append(home)

    result = await service.sync(_payload(event=FoveoEventType.FUNERAL_HOME_UPDATED))
    assert result.main_director.status == FoveoEntityStatus.CONFLICT
    assert home.director_id == native.id
    created = next(u for u in service.db.users if u.foveo_user_id == 10)
    assert created.id != native.id


@pytest.mark.asyncio
async def test_funeral_home_updated_ignores_stream_people():
    service = _service()
    result = await service.sync(
        _payload(
            event=FoveoEventType.FUNERAL_HOME_UPDATED,
            foveo_stream_id=None,
            stream_director=_director_block(foveo_user_id=11, email="stream@acme.com"),
            family=_family_block(),
        )
    )
    assert result.funeral_home.status == FoveoEntityStatus.CREATED
    assert result.main_director.status == FoveoEntityStatus.CREATED
    assert result.stream_director is None
    assert result.family is None
    assert len(service.db.users) == 1


@pytest.mark.asyncio
async def test_replacing_stream_director_does_not_deactivate_previous():
    service = _service()
    first = await service.sync(
        _payload(
            stream_director=_director_block(
                foveo_user_id=11, email="first-stream@acme.com"
            )
        )
    )
    second = await service.sync(
        _payload(
            event_id=uuid4(),
            event=FoveoEventType.STREAM_UPDATED,
            stream_director=_director_block(
                foveo_user_id=99, email="second-stream@acme.com"
            ),
        )
    )
    previous = next(u for u in service.db.users if u.foveo_user_id == 11)
    current = next(u for u in service.db.users if u.foveo_user_id == 99)
    assert previous.is_active is True
    assert previous.id == first.stream_director.id
    assert current.id == second.stream_director.id
    assert current.id != previous.id


@pytest.mark.asyncio
async def test_placeholder_family_skipped_then_created_with_real_email():
    service = _service()
    skipped = await service.sync(
        _payload(family=_family_block(email="family_abcde@foveo.org"))
    )
    assert skipped.family.status == FoveoEntityStatus.SKIPPED_PLACEHOLDER_EMAIL
    assert skipped.family.id is None
    assert all(u.foveo_user_id != 12 for u in service.db.users)

    created = await service.sync(
        _payload(
            event_id=uuid4(),
            event=FoveoEventType.STREAM_UPDATED,
            family=_family_block(email="real.family@example.com"),
        )
    )
    assert created.family.status == FoveoEntityStatus.CREATED
    family = next(u for u in service.db.users if u.foveo_user_id == 12)
    assert family.email == "real.family@example.com"


@pytest.mark.asyncio
async def test_later_stream_overwrites_family_deceased_name():
    service = _service()
    await service.sync(_payload(family=_family_block(deceased_first_name="Jordan")))
    await service.sync(
        _payload(
            event_id=uuid4(),
            event=FoveoEventType.STREAM_UPDATED,
            family=_family_block(deceased_first_name="Taylor"),
        )
    )
    family = next(u for u in service.db.users if u.foveo_user_id == 12)
    assert family.deceased_first_name == "Taylor"
    assert len([u for u in service.db.users if u.role == UserRole.FAMILY_ADMIN.value]) == 1


@pytest.mark.asyncio
async def test_user_updated_does_not_create():
    service = _service()
    result = await service.sync(
        _payload(
            event=FoveoEventType.USER_UPDATED,
            foveo_stream_id=None,
            funeral_home=None,
            main_director=_director_block(),
        )
    )
    assert result.main_director.status == FoveoEntityStatus.SKIPPED
    assert service.db.users == []


@pytest.mark.asyncio
async def test_user_updated_updates_linked_password():
    service = _service()
    await service.sync(_payload())
    new_hash = django_pbkdf2_sha256.hash("new-foveo-password")
    result = await service.sync(
        _payload(
            event_id=uuid4(),
            event=FoveoEventType.USER_UPDATED,
            foveo_stream_id=None,
            funeral_home=None,
            main_director=_director_block(password_hash=new_hash),
        )
    )
    assert result.main_director.status == FoveoEntityStatus.UPDATED
    main = next(u for u in service.db.users if u.foveo_user_id == 10)
    assert main.password_hash == new_hash
    assert verify_password("new-foveo-password", main.password_hash)


@pytest.mark.asyncio
async def test_unusable_django_password_stored_as_null():
    service = _service()
    await service.sync(_payload(main_director=_director_block(password_hash="!")))
    main = next(u for u in service.db.users if u.foveo_user_id == 10)
    assert main.password_hash is None


@pytest.mark.asyncio
async def test_same_foveo_user_as_main_and_stream_stays_main():
    service = _service()
    director = _director_block()
    result = await service.sync(_payload(main_director=director, stream_director=director))
    assert result.main_director.status == FoveoEntityStatus.CREATED
    assert result.stream_director.status == FoveoEntityStatus.UNCHANGED
    assert result.main_director.id == result.stream_director.id
    assert len(service.db.users) == 1
    home = service.db.funeral_homes[0]
    assert home.director_id == result.main_director.id


@pytest.mark.asyncio
async def test_replayed_event_id_returns_stored_result():
    service = _service()
    payload = _payload(family=_family_block())
    first = await service.sync(payload)
    user_count = len(service.db.users)
    second = await service.sync(payload)
    assert second.model_dump() == first.model_dump()
    assert len(service.db.users) == user_count
    assert len(service.db.events) == 1


@pytest.mark.asyncio
async def test_endpoint_replays_and_commits(monkeypatch):
    monkeypatch.setattr("app.api.integrations_foveo.settings.foveo_sync_secret", FOVEO_SECRET)
    db = FakeSession()
    payload = _payload()
    first = await sync_foveo(payload, db)
    second = await sync_foveo(payload, db)
    assert first.funeral_home.status == FoveoEntityStatus.CREATED
    assert second.funeral_home.id == first.funeral_home.id
    assert len(db.events) == 1


@pytest.mark.asyncio
async def test_password_change_blocked_for_linked_user():
    user = SimpleNamespace(
        id=uuid4(),
        email="director@acme.com",
        password_hash=DJANGO_HASH,
        foveo_user_id=10,
    )
    service = UserService(AsyncMock())
    service.get_by_id = AsyncMock(return_value=user)
    with pytest.raises(PermissionDenied, match=FOVEO_PASSWORD_MANAGED_MESSAGE):
        await service.update_password(user.id, "new-password")
    assert user.password_hash == DJANGO_HASH


@pytest.mark.asyncio
async def test_admin_password_update_blocked_for_linked_user():
    user = SimpleNamespace(
        id=uuid4(),
        email="director@acme.com",
        password_hash=DJANGO_HASH,
        foveo_user_id=10,
        role=UserRole.DIRECTOR.value,
        is_active=True,
        director_id=None,
        funeral_home_id=None,
        vendor_id=None,
        first_name="Pat",
        last_name="Lee",
        deceased_first_name=None,
        deceased_last_name=None,
    )
    db = AsyncMock()
    result = AsyncMock()
    result.scalar_one_or_none = lambda: None
    db.execute = AsyncMock(return_value=result)
    service = UserManagementService(db)
    service.get_by_id = AsyncMock(return_value=user)
    with pytest.raises(PermissionDenied, match=FOVEO_PASSWORD_MANAGED_MESSAGE):
        await service.update(user_id=user.id, password="new-password")


@pytest.mark.asyncio
async def test_reset_password_blocked_for_linked_user():
    user = SimpleNamespace(
        id=uuid4(),
        email="director@acme.com",
        password_hash=DJANGO_HASH,
        is_active=True,
        foveo_user_id=10,
    )
    service = AuthService(AsyncMock())
    service.user_service.get_by_id = AsyncMock(return_value=user)
    token = service.generate_password_reset_token(user)
    with pytest.raises(PermissionDenied, match=FOVEO_PASSWORD_MANAGED_MESSAGE):
        await service.reset_password(token, "new-password")


@pytest.mark.asyncio
async def test_forgot_password_skips_foveo_linked_user(monkeypatch):
    from fastapi import BackgroundTasks

    from app.api import auth as auth_api
    from app.schemas.user import ForgotPasswordRequest

    user = SimpleNamespace(
        id=uuid4(),
        email="director@acme.com",
        is_active=True,
        foveo_user_id=10,
        display_name="Pat Lee",
    )

    async def get_by_email(self, _email):
        return user

    monkeypatch.setattr(auth_api.UserService, "get_by_email", get_by_email)
    tasks = BackgroundTasks()
    result = await auth_api.forgot_password(
        ForgotPasswordRequest(email=user.email),
        background_tasks=tasks,
        db=AsyncMock(),
    )
    assert result.debug_token is None
    assert tasks.tasks == []
