import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")

from app.core.security import hash_password, verify_password
from app.models.user import UserRole
from app.services.user_management_service import UserManagementService


def make_user(role: UserRole, **kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        email=kwargs.get("email", "family@example.com"),
        first_name="Fam",
        last_name="Admin",
        role=role.value,
        is_active=True,
        director_id=None,
        funeral_home_id=None,
        vendor_id=None,
        deceased_first_name=None,
        deceased_last_name=None,
        password_hash=hash_password("old-password"),
    )


def make_service(user):
    db = AsyncMock()
    result = AsyncMock()
    result.scalar_one_or_none = lambda: None
    db.execute = AsyncMock(return_value=result)
    service = UserManagementService(db)
    service.get_by_id = AsyncMock(return_value=user)
    return service


@pytest.mark.asyncio
async def test_password_update_hashes_new_password():
    family_admin = make_user(UserRole.FAMILY_ADMIN)
    service = make_service(family_admin)

    await service.update(
        user_id=family_admin.id,
        password="new-password",
    )

    assert verify_password("new-password", family_admin.password_hash)
