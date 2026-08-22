import os
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "pk_test_mock")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_mock")
os.environ.setdefault("SENDGRID_API_KEY", "test")
os.environ.setdefault("SENDGRID_FROM_EMAIL", "test@example.com")

from app.api.webhooks import (
    handle_expired_payment,
    handle_successful_payment,
    resolve_order_from_session,
    session_amount_matches_order,
)
from app.models.order import OrderStatus
from app.services.stripe_service import (
    CheckoutSessionResult,
    StripeService,
    normalize_product_images,
    price_to_cents,
)


def test_price_to_cents():
    assert price_to_cents(Decimal("19.99")) == 1999
    assert price_to_cents(Decimal("10.00")) == 1000


def test_normalize_product_images_list():
    images = [
        "https://cdn.example.com/a.jpg",
        "not-a-url",
        "http://cdn.example.com/b.jpg",
    ]
    assert normalize_product_images(images) == [
        "https://cdn.example.com/a.jpg",
        "http://cdn.example.com/b.jpg",
    ]


def test_normalize_product_images_dict():
    images = {
        "main": "https://cdn.example.com/main.jpg",
        "alt": "ftp://invalid.example/x.jpg",
    }
    assert normalize_product_images(images) == ["https://cdn.example.com/main.jpg"]


def test_normalize_product_images_gallery_objects():
    images = [
        SimpleNamespace(url="https://cdn.example.com/a.jpg"),
        {"url": "https://cdn.example.com/b.jpg"},
        SimpleNamespace(url="not-a-url"),
    ]
    assert normalize_product_images(images) == [
        "https://cdn.example.com/a.jpg",
        "https://cdn.example.com/b.jpg",
    ]


def test_session_amount_matches_order():
    order = SimpleNamespace(id=uuid4(), total_amount=Decimal("45.50"))
    assert session_amount_matches_order(order, {"amount_total": 4550}) is True
    assert session_amount_matches_order(order, {"amount_total": 4500}) is False


@pytest.mark.asyncio
async def test_resolve_order_from_session_metadata():
    order_id = uuid4()
    order = SimpleNamespace(id=order_id)
    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=order)

    session = {"metadata": {"order_id": str(order_id)}, "id": "cs_test_123"}

    resolved = await resolve_order_from_session(order_service, session)
    assert resolved is order
    order_service.get_by_id.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_order_from_session_id_fallback():
    order = SimpleNamespace(id=uuid4())
    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=None)
    order_service.get_by_stripe_session_id = AsyncMock(return_value=order)

    session = {"metadata": {}, "id": "cs_test_fallback"}

    resolved = await resolve_order_from_session(order_service, session)
    assert resolved is order
    order_service.get_by_stripe_session_id.assert_awaited_once_with("cs_test_fallback")


@pytest.mark.asyncio
async def test_create_checkout_session_returns_id_and_url():
    order_id = uuid4()
    product = SimpleNamespace(
        id=uuid4(),
        name="Gift",
        description="A nice gift",
        price=Decimal("25.00"),
        images=["https://cdn.example.com/gift.jpg"],
    )
    mock_session = SimpleNamespace(
        url="https://checkout.stripe.com/c/pay/cs_test_abc",
        id="cs_test_abc",
    )

    service = StripeService()
    with patch(
        "app.services.stripe_service.stripe.checkout.Session.create",
        return_value=mock_session,
    ) as create_mock:
        result = await service.create_checkout_session(
            order_id=order_id,
            products=[product],
            quantities={product.id: 1},
            visitor_email="buyer@example.com",
        )

    assert result == CheckoutSessionResult(
        url="https://checkout.stripe.com/c/pay/cs_test_abc",
        session_id="cs_test_abc",
    )
    create_mock.assert_called_once()
    call_kwargs = create_mock.call_args.kwargs
    assert call_kwargs["metadata"] == {"order_id": str(order_id)}
    assert call_kwargs["line_items"][0]["price_data"]["unit_amount"] == 2500


@pytest.mark.asyncio
async def test_handle_successful_payment_marks_paid_and_credits_commission():
    order_id = uuid4()
    order = SimpleNamespace(
        id=order_id,
        status=OrderStatus.PENDING.value,
        total_amount=Decimal("20.00"),
        wishlist=SimpleNamespace(manager=SimpleNamespace()),
    )
    session = {
        "id": "cs_test_paid",
        "metadata": {"order_id": str(order_id)},
        "amount_total": 2000,
        "payment_status": "paid",
    }

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.rollback = AsyncMock()

    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=order)
    order_service.mark_as_paid = AsyncMock()

    financial_service = AsyncMock()
    financial_service.credit_order_commission = AsyncMock(return_value=True)

    email_service = AsyncMock()
    email_service.send_purchase_confirmation_emails = AsyncMock()

    with patch("app.api.webhooks.AsyncSessionLocal") as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.api.webhooks.OrderService", return_value=order_service):
            with patch(
                "app.api.webhooks.FinancialService", return_value=financial_service
            ):
                with patch(
                    "app.services.email_service.EmailService",
                    return_value=email_service,
                ):
                    await handle_successful_payment(session)

    order_service.mark_as_paid.assert_awaited_once_with(order_id)
    financial_service.credit_order_commission.assert_awaited_once_with(order_id)
    email_service.send_purchase_confirmation_emails.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_successful_payment_skips_amount_mismatch():
    order_id = uuid4()
    order = SimpleNamespace(
        id=order_id,
        status=OrderStatus.PENDING.value,
        total_amount=Decimal("20.00"),
    )
    session = {
        "id": "cs_test_bad_amount",
        "metadata": {"order_id": str(order_id)},
        "amount_total": 9999,
    }

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=order)
    order_service.mark_as_paid = AsyncMock()

    with patch("app.api.webhooks.AsyncSessionLocal") as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.api.webhooks.OrderService", return_value=order_service):
            await handle_successful_payment(session)

    order_service.mark_as_paid.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_expired_payment_marks_failed():
    order_id = uuid4()
    order = SimpleNamespace(id=order_id, status=OrderStatus.PENDING.value)
    session = {"metadata": {"order_id": str(order_id)}, "id": "cs_test_expired"}

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=order)
    order_service.mark_as_failed = AsyncMock()

    with patch("app.api.webhooks.AsyncSessionLocal") as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.api.webhooks.OrderService", return_value=order_service):
            await handle_expired_payment(session)

    order_service.mark_as_failed.assert_awaited_once_with(order_id)
    mock_db.commit.assert_awaited_once()


def test_verify_webhook_signature_delegates_to_stripe():
    service = StripeService()
    payload = b'{"id": "evt_test"}'
    signature = "t=1,v1=abc"

    with patch(
        "app.services.stripe_service.stripe.Webhook.construct_event",
        return_value={"type": "checkout.session.completed"},
    ) as construct_mock:
        event = service.verify_webhook_signature(payload, signature)

    assert event["type"] == "checkout.session.completed"
    construct_mock.assert_called_once()
