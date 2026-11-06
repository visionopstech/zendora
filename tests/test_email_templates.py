import os
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
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

from app.api import email_templates as email_templates_api
from app.api.orders import send_order_status_email
from app.core.exceptions import NotFoundException, PermissionDenied, ValidationError
from app.models.email_template import EmailTemplateSlug
from app.models.order import OrderStatus
from app.models.user import UserRole
from app.schemas.order import OrderStatusEmailRequest
from app.schemas.email_template import EmailTemplatePreviewRequest, EmailTemplateUpdate
from app.services.email_service import EmailService, order_ready_for_status_email
from app.services.email_template_defaults import DEFAULT_EMAIL_TEMPLATES, SAMPLE_EMAIL_CONTEXTS
from app.services.email_template_service import EmailTemplateService


def make_user(**kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        email=kwargs.get("email", "user@example.com"),
        first_name=kwargs.get("first_name", "Test"),
        last_name=kwargs.get("last_name", "User"),
        is_active=kwargs.get("is_active", True),
        role=kwargs.get("role", UserRole.SUPER_ADMIN.value),
        vendor_id=kwargs.get("vendor_id"),
        funeral_home_id=kwargs.get("funeral_home_id"),
        funeral_home=kwargs.get("funeral_home"),
        directed_funeral_home=kwargs.get("directed_funeral_home"),
        deceased_first_name=kwargs.get("deceased_first_name"),
        deceased_last_name=kwargs.get("deceased_last_name"),
        address=kwargs.get("address"),
    )


def make_template(**kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        slug=kwargs.get("slug", EmailTemplateSlug.ORDER_CREATED_BUYER.value),
        name=kwargs.get("name", "Order confirmation"),
        subject=kwargs.get("subject", "Order confirmation"),
        body=kwargs.get("body", "<p>Order {{ order.id }}</p>"),
        description=kwargs.get("description", "Buyer confirmation"),
        available_variables=kwargs.get("available_variables", [{"name": "order.id", "description": "ID"}]),
        is_active=kwargs.get("is_active", True),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        updated_at=kwargs.get("updated_at"),
    )


def test_email_template_update_schema_does_not_accept_slug():
    payload = EmailTemplateUpdate(subject="Hello", body="<p>Hi</p>", name="Updated")
    assert payload.model_dump(exclude_unset=True) == {
        "subject": "Hello",
        "body": "<p>Hi</p>",
        "name": "Updated",
    }


def test_default_templates_render_with_sample_context():
    service = EmailTemplateService(AsyncMock())
    slugs = {row["slug"] for row in DEFAULT_EMAIL_TEMPLATES}
    assert slugs == {item.value for item in EmailTemplateSlug}

    for row in DEFAULT_EMAIL_TEMPLATES:
        context = SAMPLE_EMAIL_CONTEXTS[row["slug"]]
        subject, body = service.render(row["subject"], row["body"], context)
        assert subject
        assert "<html" in body.lower()
        assert "{{" not in subject
        assert "{{" not in body


def test_render_product_loop_and_missing_variables():
    service = EmailTemplateService(AsyncMock())
    subject, body = service.render(
        "Order {{ order.id }}",
        "{% for product in products %}<li>{{ product.name }} x {{ product.quantity }}</li>{% endfor %}{{ missing.nested.value }}",
        {
            "order": {"id": "abc"},
            "products": [{"name": "Flowers", "quantity": 2}],
        },
    )
    assert subject == "Order abc"
    assert "<li>Flowers x 2</li>" in body


@pytest.mark.asyncio
async def test_send_templated_email_skips_inactive():
    template = make_template(is_active=False, slug="order_created_buyer")
    db = AsyncMock()
    service = EmailService(db)
    service.send_email = AsyncMock(return_value=True)

    template_service = EmailTemplateService(db)
    template_service.get_by_slug = AsyncMock(return_value=template)

    from unittest.mock import patch

    with patch("app.services.email_service.EmailTemplateService", return_value=template_service):
        sent = await service.send_templated_email(
            "order_created_buyer",
            "buyer@example.com",
            {"order": {"id": "1"}},
        )

    assert sent is False
    service.send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_templated_email_renders_and_sends():
    template = make_template(
        subject="Hello {{ buyer.name }}",
        body="<p>{{ order.id }}</p>",
    )
    db = AsyncMock()
    service = EmailService(db)
    service.send_email = AsyncMock(return_value=True)

    template_service = EmailTemplateService(db)
    template_service.get_by_slug = AsyncMock(return_value=template)

    from unittest.mock import patch

    with patch("app.services.email_service.EmailTemplateService", return_value=template_service):
        sent = await service.send_templated_email(
            EmailTemplateSlug.ORDER_CREATED_BUYER.value,
            "buyer@example.com",
            {"buyer": {"name": "Alex"}, "order": {"id": "99"}},
        )

    assert sent is True
    service.send_email.assert_awaited_once()
    args = service.send_email.await_args
    assert args.args[0] == "buyer@example.com" or args.kwargs.get("to_email") == "buyer@example.com"
    assert "Hello Alex" in (args.kwargs.get("subject") or args.args[1])


@pytest.mark.asyncio
async def test_notify_order_created_routes_by_slug_and_skips_vendor_without_users():
    vendor_with_users = SimpleNamespace(
        id=uuid4(),
        name="Bloom",
        vendor_users=[
            make_user(email="vendor@example.com", is_active=True),
            make_user(email="inactive-vendor@example.com", is_active=False),
        ],
    )
    vendor_without_users = SimpleNamespace(
        id=uuid4(),
        name="Silent Vendor",
        vendor_users=[],
    )
    product_a = SimpleNamespace(
        vendor_associations=[SimpleNamespace(vendor=vendor_with_users)]
    )
    product_b = SimpleNamespace(
        vendor_associations=[SimpleNamespace(vendor=vendor_without_users)]
    )
    order = SimpleNamespace(
        id=uuid4(),
        total_amount=Decimal("30.00"),
        currency="USD",
        paid_at=datetime.utcnow(),
        visitor=make_user(email="buyer@example.com", first_name="Alex", last_name="Buyer"),
        family_admin=make_user(
            email="family@example.com",
            first_name="Jane",
            last_name="Family",
            deceased_first_name="John",
            deceased_last_name="Doe",
        ),
        gift_collection=SimpleNamespace(
            title="Memories",
            public_slug="abc123",
            description="",
            delivery_address={"street": "1 Main", "city": "Town", "state": "IL", "zip_code": "62701", "country": "USA"},
            director=None,
            funeral_home=None,
        ),
        products=[
            SimpleNamespace(
                product_name="Flowers",
                product_price=Decimal("10.00"),
                quantity=2,
                product=product_a,
            ),
            SimpleNamespace(
                product_name="Candle",
                product_price=Decimal("10.00"),
                quantity=1,
                product=product_b,
            ),
        ],
    )

    service = EmailService(AsyncMock())
    service.send_templated_email = AsyncMock(return_value=True)
    service._super_admin_emails = AsyncMock(return_value=["admin@example.com", "ops@example.com"])

    await service.notify_order_created(order)

    calls = service.send_templated_email.await_args_list
    slugs_and_recipients = [(call.args[0], call.args[1]) for call in calls]

    assert (EmailTemplateSlug.ORDER_CREATED_VENDOR.value, "vendor@example.com") in slugs_and_recipients
    assert (EmailTemplateSlug.ORDER_CREATED_VENDOR.value, "inactive-vendor@example.com") not in slugs_and_recipients
    assert not any(recipient.endswith("silent") for _, recipient in slugs_and_recipients)
    assert (EmailTemplateSlug.ORDER_CREATED_FAMILY_ADMIN.value, "family@example.com") in slugs_and_recipients
    assert (EmailTemplateSlug.ORDER_CREATED_BUYER.value, "buyer@example.com") in slugs_and_recipients
    assert (EmailTemplateSlug.ORDER_CREATED_SUPER_ADMIN.value, "admin@example.com") in slugs_and_recipients
    assert (EmailTemplateSlug.ORDER_CREATED_SUPER_ADMIN.value, "ops@example.com") in slugs_and_recipients

    vendor_call = next(
        call for call in calls if call.args[0] == EmailTemplateSlug.ORDER_CREATED_VENDOR.value
    )
    assert vendor_call.args[2]["product_count"] == 2
    assert vendor_call.args[2]["price"] == "20.00"
    assert vendor_call.args[2]["vendor"]["name"] == "Bloom"


def test_order_ready_for_status_email_requires_payment():
    paid = SimpleNamespace(status=OrderStatus.PAID.value, paid_at=datetime.utcnow())
    refunded = SimpleNamespace(status=OrderStatus.REFUNDED.value, paid_at=None)
    failed_after_payment = SimpleNamespace(
        status=OrderStatus.FAILED.value, paid_at=datetime.utcnow()
    )
    pending = SimpleNamespace(status=OrderStatus.PENDING.value, paid_at=None)
    failed = SimpleNamespace(status=OrderStatus.FAILED.value, paid_at=None)

    assert order_ready_for_status_email(paid) is True
    assert order_ready_for_status_email(refunded) is True
    assert order_ready_for_status_email(failed_after_payment) is True
    assert order_ready_for_status_email(pending) is False
    assert order_ready_for_status_email(failed) is False


def _status_order():
    director = make_user(email="director@example.com", first_name="Dana", last_name="Director")
    vendor = SimpleNamespace(
        id=uuid4(),
        name="Bloom",
        vendor_users=[make_user(email="vendor@example.com", is_active=True)],
    )
    return SimpleNamespace(
        id=uuid4(),
        status=OrderStatus.REFUNDED.value,
        total_amount=Decimal("20.00"),
        currency="USD",
        paid_at=datetime.utcnow(),
        visitor=make_user(email="buyer@example.com", first_name="Alex", last_name="Buyer"),
        family_admin=make_user(email="family@example.com", first_name="Jane", last_name="Family"),
        gift_collection=SimpleNamespace(
            title="Memories",
            public_slug="abc123",
            description="",
            director=director,
            director_id=director.id,
            delivery_address=None,
            funeral_home=None,
        ),
        funeral_home_id=uuid4(),
        products=[
            SimpleNamespace(
                product_name="Flowers",
                product_price=Decimal("10.00"),
                quantity=2,
                product=SimpleNamespace(
                    vendor_associations=[SimpleNamespace(vendor=vendor)]
                ),
            )
        ],
    )


@pytest.mark.asyncio
async def test_notify_order_status_changed_routes_current_status_and_note():
    order = _status_order()
    sender = make_user(
        email="ops@example.com",
        first_name="Sam",
        last_name="Admin",
        role=UserRole.SUPER_ADMIN.value,
    )
    service = EmailService(AsyncMock())
    service.send_templated_email = AsyncMock(return_value=True)
    service._super_admin_emails = AsyncMock(return_value=["admin@example.com"])

    deliveries = await service.notify_order_status_changed(
        order, sender, note="  Refunded today  "
    )

    routed = {(item.audience, item.email) for item in deliveries}
    assert ("vendor", "vendor@example.com") in routed
    assert ("family_admin", "family@example.com") in routed
    assert ("buyer", "buyer@example.com") in routed
    assert ("director", "director@example.com") in routed
    assert ("super_admin", "admin@example.com") in routed
    assert all(item.sent for item in deliveries)

    slugs = [call.args[0] for call in service.send_templated_email.await_args_list]
    assert EmailTemplateSlug.ORDER_STATUS_CHANGED_VENDOR.value in slugs
    assert EmailTemplateSlug.ORDER_STATUS_CHANGED_BUYER.value in slugs
    assert EmailTemplateSlug.ORDER_STATUS_CHANGED_DIRECTOR.value in slugs

    vendor_call = next(
        call
        for call in service.send_templated_email.await_args_list
        if call.args[0] == EmailTemplateSlug.ORDER_STATUS_CHANGED_VENDOR.value
    )
    assert vendor_call.args[2]["order"]["status"] == OrderStatus.REFUNDED.value
    assert vendor_call.args[2]["note"] == "Refunded today"
    assert vendor_call.args[2]["sender"]["name"] == "Sam Admin"
    assert vendor_call.args[2]["product_count"] == 2


@pytest.mark.asyncio
async def test_send_order_status_email_rejects_unpaid_order():
    order = _status_order()
    order.status = OrderStatus.PENDING.value
    order.paid_at = None
    order_service = MagicMock()
    order_service.get_by_id = AsyncMock(return_value=order)

    from unittest.mock import patch

    with patch("app.api.orders.OrderService", return_value=order_service):
        with pytest.raises(ValidationError):
            await send_order_status_email(
                order_id=order.id,
                payload=OrderStatusEmailRequest(),
                db=AsyncMock(),
                current_user=make_user(role=UserRole.SUPER_ADMIN.value),
            )


@pytest.mark.asyncio
async def test_send_order_status_email_rejects_director_outside_scope():
    order = _status_order()
    order.gift_collection.director_id = uuid4()
    order_service = MagicMock()
    order_service.get_by_id = AsyncMock(return_value=order)
    director = make_user(
        role=UserRole.DIRECTOR.value,
        funeral_home_id=uuid4(),
    )

    from unittest.mock import patch

    with patch("app.api.orders.OrderService", return_value=order_service):
        with pytest.raises(PermissionDenied):
            await send_order_status_email(
                order_id=order.id,
                payload=OrderStatusEmailRequest(note="Update"),
                db=AsyncMock(),
                current_user=director,
            )


@pytest.mark.asyncio
async def test_send_order_status_email_vendor_sends_for_own_order():
    order = _status_order()
    vendor_id = uuid4()
    order_service = MagicMock()
    order_service.get_by_id = AsyncMock(return_value=order)
    order_service.get_order_vendor_products = AsyncMock(return_value=([object()], Decimal("20")))
    email_service = MagicMock()
    email_service.notify_order_status_changed = AsyncMock(
        return_value=[
            SimpleNamespace(audience="buyer", email="buyer@example.com", sent=True),
            SimpleNamespace(audience="vendor", email="vendor@example.com", sent=False),
        ]
    )
    vendor = make_user(role=UserRole.VENDOR.value, vendor_id=vendor_id)

    from unittest.mock import patch

    with patch("app.api.orders.OrderService", return_value=order_service), patch(
        "app.api.orders.EmailService", return_value=email_service
    ):
        result = await send_order_status_email(
            order_id=order.id,
            payload=OrderStatusEmailRequest(note="Shipped"),
            db=AsyncMock(),
            current_user=vendor,
        )

    email_service.notify_order_status_changed.assert_awaited_once()
    assert email_service.notify_order_status_changed.await_args.args[1] is vendor
    assert email_service.notify_order_status_changed.await_args.kwargs["note"] == "Shipped"
    assert result.sent_count == 1
    assert result.status == OrderStatus.REFUNDED
    assert result.recipients[1].sent is False


@pytest.mark.asyncio
async def test_notify_collection_created_skips_director_when_missing():
    collection = SimpleNamespace(
        title="Memories",
        public_slug="abc123",
        description="A collection",
        family_admin=make_user(email="family@example.com", first_name="Jane", last_name="Family"),
        director=None,
        funeral_home=SimpleNamespace(
            name="Chapel",
            email="chapel@example.com",
            phone="555",
            address=None,
        ),
    )

    service = EmailService(AsyncMock())
    service.send_templated_email = AsyncMock(return_value=True)
    service._super_admin_emails = AsyncMock(return_value=["admin@example.com"])

    await service.notify_collection_created(collection)

    slugs = [call.args[0] for call in service.send_templated_email.await_args_list]
    assert EmailTemplateSlug.COLLECTION_CREATED_FAMILY_ADMIN.value in slugs
    assert EmailTemplateSlug.COLLECTION_CREATED_SUPER_ADMIN.value in slugs
    assert EmailTemplateSlug.COLLECTION_CREATED_DIRECTOR.value not in slugs


@pytest.mark.asyncio
async def test_notify_collection_created_sends_to_director_when_present():
    collection = SimpleNamespace(
        title="Memories",
        public_slug="abc123",
        description="",
        family_admin=make_user(email="family@example.com"),
        director=make_user(email="director@example.com", first_name="Dana", last_name="Director"),
        funeral_home=None,
    )

    service = EmailService(AsyncMock())
    service.send_templated_email = AsyncMock(return_value=True)
    service._super_admin_emails = AsyncMock(return_value=[])

    await service.notify_collection_created(collection)

    slugs_and_recipients = [
        (call.args[0], call.args[1]) for call in service.send_templated_email.await_args_list
    ]
    assert (
        EmailTemplateSlug.COLLECTION_CREATED_DIRECTOR.value,
        "director@example.com",
    ) in slugs_and_recipients


@pytest.mark.asyncio
async def test_list_email_templates_returns_all():
    templates = [make_template(slug="order_created_buyer"), make_template(slug="order_created_vendor")]
    service = MagicMock()
    service.list = AsyncMock(return_value=templates)

    from unittest.mock import patch

    with patch("app.api.email_templates.EmailTemplateService", return_value=service):
        result = await email_templates_api.list_email_templates(
            db=AsyncMock(),
            current_user=make_user(email="admin@example.com"),
        )

    assert len(result) == 2
    assert result[0].slug == "order_created_buyer"


@pytest.mark.asyncio
async def test_update_email_template_not_found():
    service = MagicMock()
    service.update = AsyncMock(side_effect=NotFoundException("Email template not found"))

    from unittest.mock import patch

    with patch("app.api.email_templates.EmailTemplateService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await email_templates_api.update_email_template(
                slug="missing",
                payload=EmailTemplateUpdate(subject="Nope"),
                db=AsyncMock(),
                current_user=make_user(),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_preview_email_template_uses_sample_context():
    template = make_template(
        slug=EmailTemplateSlug.COLLECTION_CREATED_FAMILY_ADMIN.value,
        subject="Created: {{ collection.name }}",
        body="<p>{{ collection.link }}</p>",
    )
    service = MagicMock()
    service.get_by_slug = AsyncMock(return_value=template)
    service.render = EmailTemplateService(AsyncMock()).render

    from unittest.mock import patch

    with patch("app.api.email_templates.EmailTemplateService", return_value=service):
        result = await email_templates_api.preview_email_template(
            slug=EmailTemplateSlug.COLLECTION_CREATED_FAMILY_ADMIN.value,
            payload=EmailTemplatePreviewRequest(context=None),
            db=AsyncMock(),
            current_user=make_user(),
        )

    assert "In Memory of John" in result.subject
    assert "http://localhost:3000/w/abc123" in result.body
