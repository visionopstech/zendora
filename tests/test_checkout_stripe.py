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
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")

from app.models.order import OrderStatus
from app.services.payment_service import (
    handle_expired_payment,
    handle_payment_failed,
    handle_successful_payment,
    reconcile_order_status,
    resolve_order_from_session,
    session_amount_matches_order,
)
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
    assert call_kwargs["payment_intent_data"] == {"metadata": {"order_id": str(order_id)}}
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
    email_service.notify_order_created = AsyncMock()

    with patch("app.services.payment_service.AsyncSessionLocal") as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.services.payment_service.OrderService", return_value=order_service):
            with patch(
                "app.services.payment_service.FinancialService", return_value=financial_service
            ):
                with patch(
                    "app.services.email_service.EmailService",
                    return_value=email_service,
                ):
                    await handle_successful_payment(session)

    order_service.mark_as_paid.assert_awaited_once_with(order_id)
    financial_service.credit_order_commission.assert_awaited_once_with(order_id)
    email_service.notify_order_created.assert_awaited_once()


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

    with patch("app.services.payment_service.AsyncSessionLocal") as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.services.payment_service.OrderService", return_value=order_service):
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

    with patch("app.services.payment_service.AsyncSessionLocal") as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.services.payment_service.OrderService", return_value=order_service):
            await handle_expired_payment(session)

    order_service.mark_as_failed.assert_awaited_once_with(order_id)
    mock_db.commit.assert_awaited_once()


def _patched_payment_env(order_service, financial_service=None):
    """Context managers patching the payment_service collaborators."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    session_local = patch("app.services.payment_service.AsyncSessionLocal")
    return mock_db, session_local


@pytest.mark.asyncio
async def test_paid_status_survives_commission_credit_failure():
    order_id = uuid4()
    order = SimpleNamespace(
        id=order_id,
        status=OrderStatus.PENDING.value,
        total_amount=Decimal("20.00"),
    )
    session = {
        "id": "cs_test_paid",
        "metadata": {"order_id": str(order_id)},
        "amount_total": 2000,
        "payment_status": "paid",
    }
    mock_db, session_local_patch = _patched_payment_env(None)

    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=order)
    order_service.mark_as_paid = AsyncMock()
    financial_service = AsyncMock()
    financial_service.credit_order_commission = AsyncMock(
        side_effect=RuntimeError("wallet insert failed")
    )

    with session_local_patch as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.services.payment_service.OrderService", return_value=order_service):
            with patch(
                "app.services.payment_service.FinancialService",
                return_value=financial_service,
            ):
                with pytest.raises(RuntimeError):
                    await handle_successful_payment(session)

    order_service.mark_as_paid.assert_awaited_once_with(order_id)
    # PAID was committed before the failing commission credit.
    mock_db.commit.assert_awaited_once()
    mock_db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_successful_payment_does_not_regress_fulfilment_status():
    order_id = uuid4()
    order = SimpleNamespace(
        id=order_id,
        status=OrderStatus.SHIPPING.value,
        total_amount=Decimal("20.00"),
    )
    session = {"id": "cs_x", "metadata": {"order_id": str(order_id)}, "amount_total": 2000}
    mock_db, session_local_patch = _patched_payment_env(None)

    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=order)
    order_service.mark_as_paid = AsyncMock()
    financial_service = AsyncMock()
    financial_service.credit_order_commission = AsyncMock(return_value=False)

    with session_local_patch as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.services.payment_service.OrderService", return_value=order_service):
            with patch(
                "app.services.payment_service.FinancialService",
                return_value=financial_service,
            ):
                await handle_successful_payment(session)

    order_service.mark_as_paid.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_expired_payment_does_not_fail_non_pending_order():
    order_id = uuid4()
    order = SimpleNamespace(id=order_id, status=OrderStatus.CANCELED.value)
    session = {"metadata": {"order_id": str(order_id)}, "id": "cs_test_expired"}
    mock_db, session_local_patch = _patched_payment_env(None)

    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=order)
    order_service.mark_as_failed = AsyncMock()

    with session_local_patch as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.services.payment_service.OrderService", return_value=order_service):
            await handle_expired_payment(session)

    order_service.mark_as_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_expired_payment_reraises_errors_for_stripe_retry():
    order_id = uuid4()
    session = {"metadata": {"order_id": str(order_id)}, "id": "cs_test_expired"}
    mock_db, session_local_patch = _patched_payment_env(None)

    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(side_effect=RuntimeError("db down"))

    with session_local_patch as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.services.payment_service.OrderService", return_value=order_service):
            with pytest.raises(RuntimeError):
                await handle_expired_payment(session)

    mock_db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_payment_failed_marks_pending_order_failed():
    order_id = uuid4()
    order = SimpleNamespace(id=order_id, status=OrderStatus.PENDING.value)
    payment_intent = {"id": "pi_1", "metadata": {"order_id": str(order_id)}}
    mock_db, session_local_patch = _patched_payment_env(None)

    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=order)
    order_service.mark_as_failed = AsyncMock()

    with session_local_patch as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.services.payment_service.OrderService", return_value=order_service):
            await handle_payment_failed(payment_intent)

    order_service.mark_as_failed.assert_awaited_once_with(order_id)
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_payment_failed_ignores_paid_order_and_missing_metadata():
    order_id = uuid4()
    order = SimpleNamespace(id=order_id, status=OrderStatus.PAID.value)
    mock_db, session_local_patch = _patched_payment_env(None)

    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=order)
    order_service.mark_as_failed = AsyncMock()

    with session_local_patch as session_local:
        session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        session_local.return_value.__aexit__ = AsyncMock(return_value=None)
        with patch("app.services.payment_service.OrderService", return_value=order_service):
            await handle_payment_failed({"id": "pi_2", "metadata": {"order_id": str(order_id)}})
            await handle_payment_failed({"id": "pi_3", "metadata": {}})

    order_service.mark_as_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_marks_paid_when_stripe_session_is_paid():
    order = SimpleNamespace(id=uuid4(), status=OrderStatus.PENDING.value, stripe_session_id="cs_test_1")
    paid_session = {"id": "cs_test_1", "payment_status": "paid", "status": "complete"}
    updated = SimpleNamespace(status=OrderStatus.PAID.value)

    mock_db = AsyncMock()
    order_service = AsyncMock()
    order_service.get_by_id = AsyncMock(return_value=updated)

    with patch(
        "app.services.payment_service.StripeService.retrieve_checkout_session",
        new=AsyncMock(return_value=paid_session),
    ):
        with patch(
            "app.services.payment_service.handle_successful_payment", new=AsyncMock()
        ) as paid_handler:
            with patch("app.services.payment_service.AsyncSessionLocal") as session_local:
                session_local.return_value.__aenter__ = AsyncMock(return_value=mock_db)
                session_local.return_value.__aexit__ = AsyncMock(return_value=None)
                with patch(
                    "app.services.payment_service.OrderService", return_value=order_service
                ):
                    changed = await reconcile_order_status(order)

    paid_handler.assert_awaited_once_with(paid_session)
    assert changed is True


@pytest.mark.asyncio
async def test_reconcile_skips_settled_orders_and_swallows_stripe_errors():
    paid = SimpleNamespace(id=uuid4(), status=OrderStatus.PAID.value, stripe_session_id="cs_1")
    temp = SimpleNamespace(id=uuid4(), status=OrderStatus.PENDING.value, stripe_session_id="pending_x")
    pending = SimpleNamespace(id=uuid4(), status=OrderStatus.PENDING.value, stripe_session_id="cs_2")

    assert await reconcile_order_status(paid) is False
    assert await reconcile_order_status(temp) is False
    with patch(
        "app.services.payment_service.StripeService.retrieve_checkout_session",
        new=AsyncMock(side_effect=RuntimeError("stripe down")),
    ):
        assert await reconcile_order_status(pending) is False


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
