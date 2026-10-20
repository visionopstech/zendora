import os
from datetime import timedelta
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
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

from app.api import auth as auth_api
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    PASSWORD_RESET_TOKEN_USE,
    create_access_token,
    create_password_reset_token,
    decode_access_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)
from app.dependencies.auth import get_current_user
from app.schemas.user import ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from fastapi.security import HTTPAuthorizationCredentials


def make_user(**kwargs):
    password_hash = kwargs.get("password_hash", hash_password("old-password"))
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        email=kwargs.get("email", "family@example.com"),
        password_hash=password_hash,
        is_active=kwargs.get("is_active", True),
        display_name=kwargs.get("display_name", "Fam Admin"),
        first_name=kwargs.get("first_name", "Fam"),
        last_name=kwargs.get("last_name", "Admin"),
        role=kwargs.get("role", "FAMILY_ADMIN"),
    )


def test_password_reset_token_is_not_an_access_token():
    user = make_user()
    token = create_password_reset_token(user.id, user.email, user.password_hash)
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["token_use"] == PASSWORD_RESET_TOKEN_USE
    assert decode_password_reset_token(token)["sub"] == str(user.id)


def test_access_token_is_rejected_as_password_reset_token():
    token = create_access_token({"sub": str(uuid4()), "email": "a@b.com", "role": "VISITOR"})
    assert decode_password_reset_token(token) is None


def test_expired_password_reset_token_is_rejected():
    user = make_user()
    token = create_password_reset_token(
        user.id,
        user.email,
        user.password_hash,
        expires_delta=timedelta(seconds=-1),
    )
    assert decode_password_reset_token(token) is None


@pytest.mark.asyncio
async def test_reset_password_updates_hash_and_invalidates_token():
    user = make_user()
    service = AuthService(AsyncMock())
    service.user_service.get_by_id = AsyncMock(return_value=user)

    async def update_password(_user_id, new_password):
        user.password_hash = hash_password(new_password)
        return user

    service.user_service.update_password = AsyncMock(side_effect=update_password)

    token = service.generate_password_reset_token(user)
    updated = await service.reset_password(token, "new-password")

    assert verify_password("new-password", updated.password_hash)
    with pytest.raises(UnauthorizedError):
        await service.reset_password(token, "another-password")


@pytest.mark.asyncio
async def test_reset_password_rejects_unknown_or_inactive_user():
    service = AuthService(AsyncMock())
    missing = make_user()
    token = create_password_reset_token(missing.id, missing.email, missing.password_hash)

    service.user_service.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(UnauthorizedError):
        await service.reset_password(token, "new-password")

    inactive = make_user(is_active=False)
    token = create_password_reset_token(inactive.id, inactive.email, inactive.password_hash)
    service.user_service.get_by_id = AsyncMock(return_value=inactive)
    with pytest.raises(UnauthorizedError):
        await service.reset_password(token, "new-password")


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_does_not_leak_or_email(monkeypatch):
    async def missing_email(self, _email):
        return None

    monkeypatch.setattr(auth_api.UserService, "get_by_email", missing_email)

    tasks = BackgroundTasks()
    result = await auth_api.forgot_password(
        ForgotPasswordRequest(email="missing@example.com"),
        background_tasks=tasks,
        db=AsyncMock(),
    )

    assert result.message == auth_api.FORGOT_PASSWORD_MESSAGE
    assert result.debug_token is None
    assert tasks.tasks == []


@pytest.mark.asyncio
async def test_forgot_password_queues_email_for_active_user(monkeypatch):
    user = make_user()

    async def get_by_email(self, email):
        assert email == user.email
        return user

    monkeypatch.setattr(auth_api.UserService, "get_by_email", get_by_email)
    monkeypatch.setattr(auth_api.settings, "environment", "development")

    tasks = BackgroundTasks()
    result = await auth_api.forgot_password(
        ForgotPasswordRequest(email=user.email),
        background_tasks=tasks,
        db=AsyncMock(),
    )

    assert result.message == auth_api.FORGOT_PASSWORD_MESSAGE
    assert result.debug_token
    assert decode_password_reset_token(result.debug_token)["sub"] == str(user.id)
    assert len(tasks.tasks) == 1
    task = tasks.tasks[0]
    assert task.args[0] == user.email
    assert task.args[1] == user.display_name
    assert f"/reset-password?token={result.debug_token}" in task.args[2]


@pytest.mark.asyncio
async def test_forgot_password_skips_inactive_user(monkeypatch):
    user = make_user(is_active=False)

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


@pytest.mark.asyncio
async def test_forgot_password_hides_debug_token_in_production(monkeypatch):
    user = make_user()

    async def get_by_email(self, _email):
        return user

    monkeypatch.setattr(auth_api.UserService, "get_by_email", get_by_email)
    monkeypatch.setattr(auth_api.settings, "environment", "production")

    tasks = BackgroundTasks()
    result = await auth_api.forgot_password(
        ForgotPasswordRequest(email=user.email),
        background_tasks=tasks,
        db=AsyncMock(),
    )

    assert result.debug_token is None
    assert len(tasks.tasks) == 1


@pytest.mark.asyncio
async def test_reset_password_endpoint_commits_on_success(monkeypatch):
    db = AsyncMock()
    user = make_user()

    async def reset(self, token, password):
        assert token == "reset-token"
        assert password == "new-password"
        return user

    monkeypatch.setattr(auth_api.AuthService, "reset_password", reset)

    result = await auth_api.reset_password(
        ResetPasswordRequest(token="reset-token", password="new-password"),
        db=db,
    )

    assert result.message == "Password has been reset successfully"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_password_endpoint_rejects_bad_token(monkeypatch):
    async def reset(self, _token, _password):
        raise UnauthorizedError("Invalid or expired password reset token")

    monkeypatch.setattr(auth_api.AuthService, "reset_password", reset)

    with pytest.raises(HTTPException) as exc:
        await auth_api.reset_password(
            ResetPasswordRequest(token="bad-token", password="new-password"),
            db=AsyncMock(),
        )

    assert exc.value.status_code == 401
    assert "Invalid or expired" in exc.value.detail


@pytest.mark.asyncio
async def test_get_current_user_rejects_password_reset_token():
    user = make_user()
    token = create_password_reset_token(user.id, user.email, user.password_hash)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(UnauthorizedError):
        await get_current_user(credentials=credentials, db=AsyncMock())


@pytest.mark.asyncio
async def test_password_reset_email_contains_link(monkeypatch):
    service = EmailService()
    captured = {}

    async def fake_send(to_email, subject, html_content, plain_content=None):
        captured["to_email"] = to_email
        captured["subject"] = subject
        captured["html_content"] = html_content
        return True

    monkeypatch.setattr(service, "send_email", fake_send)

    sent = await service.send_password_reset_email(
        "family@example.com",
        "Fam Admin",
        "http://localhost:3000/reset-password?token=abc",
    )

    assert sent is True
    assert captured["to_email"] == "family@example.com"
    assert "Reset your Zendora password" in captured["subject"]
    assert "http://localhost:3000/reset-password?token=abc" in captured["html_content"]
    assert "Fam Admin" in captured["html_content"]
    assert "expires in 1 hour" in captured["html_content"]
