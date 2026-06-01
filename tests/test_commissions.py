import os
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test")
os.environ.setdefault("SENDGRID_API_KEY", "test")
os.environ.setdefault("SENDGRID_FROM_EMAIL", "test@example.com")

from app.models.finance import Wallet, WalletType
from app.models.order import Order, OrderProduct
from app.models.wishlist import Wishlist
from app.schemas.product import ProductCreate
from app.services.financial_service import FinancialService
from app.services.order_service import OrderService
import app.services.order_service as order_service_module


class FakeSession:
    def __init__(self, wishlist=None):
        self.wishlist = wishlist
        self.added = []

    async def get(self, model, object_id):
        if model is Wishlist and self.wishlist and self.wishlist.id == object_id:
            return self.wishlist
        return None

    def add(self, obj):
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.added.append(obj)

    async def flush(self):
        return None

    async def refresh(self, obj, attribute_names=None):
        return None


def test_product_schema_rejects_price_below_base_price():
    with pytest.raises(PydanticValidationError):
        ProductCreate(
            name="Stroller",
            base_price=Decimal("12.00"),
            price=Decimal("10.00"),
            images=[],
            vendor_ids=[],
        )


@pytest.mark.asyncio
async def test_financial_service_calculates_manager_and_platform_profit_from_retail_price():
    service = FinancialService(FakeSession())
    product = SimpleNamespace(
        id=uuid4(),
        base_price=Decimal("10.00"),
        price=Decimal("20.00"),
    )

    commission = await service.calculate_order_commission(
        products=[product],
        quantities={product.id: 1},
        manager_profit_percentage=Decimal("20.00"),
    )

    assert commission["base_amount"] == Decimal("10.00")
    assert commission["final_amount"] == Decimal("20.00")
    assert commission["raw_benefit_amount"] == Decimal("10.00")
    assert commission["manager_profit_amount"] == Decimal("4.00")
    assert commission["platform_profit_amount"] == Decimal("6.00")


@pytest.mark.asyncio
async def test_financial_service_clamps_platform_profit_to_zero_when_commission_exceeds_margin():
    service = FinancialService(FakeSession())
    product = SimpleNamespace(
        id=uuid4(),
        base_price=Decimal("18.00"),
        price=Decimal("20.00"),
    )

    commission = await service.calculate_order_commission(
        products=[product],
        quantities={product.id: 1},
        manager_profit_percentage=Decimal("20.00"),
    )

    assert commission["manager_profit_amount"] == Decimal("4.00")
    assert commission["platform_profit_amount"] == Decimal("0.00")


@pytest.mark.asyncio
async def test_order_service_create_order_creates_commission_snapshot_for_wishlist_manager(monkeypatch):
    wishlist = SimpleNamespace(id=uuid4(), manager_id=uuid4())
    db = FakeSession(wishlist=wishlist)
    financial_service = SimpleNamespace(
        get_manager_profit_percentage=AsyncMock(return_value=Decimal("20.00")),
        calculate_order_commission=AsyncMock(
            return_value={
                "base_amount": Decimal("10.00"),
                "final_amount": Decimal("20.00"),
                "raw_benefit_amount": Decimal("10.00"),
                "manager_profit_percentage": Decimal("20.00"),
                "manager_profit_amount": Decimal("4.00"),
                "platform_profit_amount": Decimal("6.00"),
            }
        ),
        create_order_commission_snapshot=AsyncMock(),
    )

    monkeypatch.setattr(order_service_module, "FinancialService", lambda _: financial_service)

    service = OrderService(db)
    product = SimpleNamespace(
        id=uuid4(),
        name="Car seat",
        price=Decimal("20.00"),
    )

    order = await service.create_order(
        visitor_id=uuid4(),
        wishlist_id=wishlist.id,
        admin_id=uuid4(),
        stripe_session_id="temp_123",
        products=[product],
        quantities={product.id: 1},
    )

    assert order.total_amount == Decimal("20.00")
    assert any(isinstance(item, Order) for item in db.added)
    assert any(isinstance(item, OrderProduct) for item in db.added)
    financial_service.create_order_commission_snapshot.assert_awaited_once_with(
        order_id=order.id,
        manager_id=wishlist.manager_id,
        products=[product],
        quantities={product.id: 1},
    )


@pytest.mark.asyncio
async def test_financial_service_credit_order_commission_is_idempotent(monkeypatch):
    db = FakeSession()
    service = FinancialService(db)
    commission = SimpleNamespace(
        manager_id=uuid4(),
        manager_profit_amount=Decimal("4.00"),
        platform_profit_amount=Decimal("6.00"),
        credited_at=None,
    )
    manager_wallet = Wallet(
        id=uuid4(),
        wallet_type=WalletType.MANAGER.value,
        manager_id=commission.manager_id,
        balance=Decimal("0.00"),
        currency="USD",
    )
    platform_wallet = Wallet(
        id=uuid4(),
        wallet_type=WalletType.PLATFORM.value,
        balance=Decimal("0.00"),
        currency="USD",
    )

    monkeypatch.setattr(service, "get_order_commission", AsyncMock(return_value=commission))
    monkeypatch.setattr(service, "get_or_create_manager_wallet", AsyncMock(return_value=manager_wallet))
    monkeypatch.setattr(service, "get_or_create_platform_wallet", AsyncMock(return_value=platform_wallet))

    first_credit = await service.credit_order_commission(uuid4())
    added_transactions_after_first_credit = len(db.added)
    second_credit = await service.credit_order_commission(uuid4())

    assert first_credit is True
    assert second_credit is False
    assert manager_wallet.balance == Decimal("4.00")
    assert platform_wallet.balance == Decimal("6.00")
    assert commission.credited_at is not None
    assert len(db.added) == added_transactions_after_first_credit
