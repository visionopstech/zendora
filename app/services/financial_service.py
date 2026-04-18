from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException, ValidationError
from app.models.finance import (
    ManagerCommission,
    OrderCommission,
    Wallet,
    WalletTransaction,
    WalletTransactionType,
    WalletType,
)
from app.models.order import Order
from app.models.product import Product


MONEY_QUANTUM = Decimal("0.01")
PERCENT_QUANTUM = Decimal("0.01")


class FinancialService:
    """Commission and wallet ledger operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _quantize_money(self, amount: Decimal) -> Decimal:
        return Decimal(amount).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    def _quantize_percent(self, amount: Decimal) -> Decimal:
        return Decimal(amount).quantize(PERCENT_QUANTUM, rounding=ROUND_HALF_UP)

    async def get_manager_commission(self, manager_id: UUID) -> Optional[ManagerCommission]:
        result = await self.db.execute(
            select(ManagerCommission).where(ManagerCommission.manager_id == manager_id)
        )
        return result.scalar_one_or_none()

    async def upsert_manager_commission(
        self,
        manager_id: UUID,
        profit_percentage: Optional[Decimal],
    ) -> Optional[ManagerCommission]:
        if profit_percentage is None:
            commission = await self.get_manager_commission(manager_id)
            if commission:
                await self.db.delete(commission)
                await self.db.flush()
            return None

        normalized_percentage = self._quantize_percent(profit_percentage)
        if normalized_percentage < 0 or normalized_percentage > 100:
            raise ValidationError("profit_percentage must be between 0 and 100")

        commission = await self.get_manager_commission(manager_id)
        if commission:
            commission.profit_percentage = normalized_percentage
        else:
            commission = ManagerCommission(
                manager_id=manager_id,
                profit_percentage=normalized_percentage,
            )
            self.db.add(commission)

        await self.db.flush()
        await self.db.refresh(commission)
        return commission

    async def get_manager_profit_percentage(self, manager_id: UUID) -> Decimal:
        commission = await self.get_manager_commission(manager_id)
        if not commission:
            return Decimal("0.00")
        return self._quantize_percent(commission.profit_percentage)

    async def calculate_order_commission(
        self,
        products: List[Product],
        quantities: dict[UUID, int],
        manager_profit_percentage: Decimal,
    ) -> dict[str, Decimal]:
        base_amount = self._quantize_money(
            sum(product.base_price * quantities.get(product.id, 1) for product in products)
        )
        final_amount = self._quantize_money(
            sum(product.price * quantities.get(product.id, 1) for product in products)
        )
        raw_benefit_amount = self._quantize_money(final_amount - base_amount)
        normalized_percentage = self._quantize_percent(manager_profit_percentage)
        manager_profit_amount = self._quantize_money(
            final_amount * (normalized_percentage / Decimal("100"))
        )
        platform_profit_amount = self._quantize_money(
            max(raw_benefit_amount - manager_profit_amount, Decimal("0.00"))
        )

        return {
            "base_amount": base_amount,
            "final_amount": final_amount,
            "raw_benefit_amount": raw_benefit_amount,
            "manager_profit_percentage": normalized_percentage,
            "manager_profit_amount": manager_profit_amount,
            "platform_profit_amount": platform_profit_amount,
        }

    async def create_order_commission_snapshot(
        self,
        order_id: UUID,
        manager_id: UUID,
        products: List[Product],
        quantities: dict[UUID, int],
    ) -> OrderCommission:
        profit_percentage = await self.get_manager_profit_percentage(manager_id)
        commission_data = await self.calculate_order_commission(
            products=products,
            quantities=quantities,
            manager_profit_percentage=profit_percentage,
        )
        commission = OrderCommission(
            order_id=order_id,
            manager_id=manager_id,
            **commission_data,
        )
        self.db.add(commission)
        await self.db.flush()
        await self.db.refresh(commission)
        return commission

    async def get_order_commission(self, order_id: UUID) -> Optional[OrderCommission]:
        result = await self.db.execute(
            select(OrderCommission)
            .options(selectinload(OrderCommission.order))
            .where(OrderCommission.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def get_platform_wallet(self) -> Optional[Wallet]:
        result = await self.db.execute(
            select(Wallet).where(Wallet.wallet_type == WalletType.PLATFORM.value)
        )
        return result.scalar_one_or_none()

    async def get_manager_wallet(self, manager_id: UUID) -> Optional[Wallet]:
        result = await self.db.execute(
            select(Wallet).where(
                Wallet.wallet_type == WalletType.MANAGER.value,
                Wallet.manager_id == manager_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_platform_wallet(self) -> Wallet:
        wallet = await self.get_platform_wallet()
        if wallet:
            return wallet

        wallet = Wallet(
            wallet_type=WalletType.PLATFORM.value,
            currency="USD",
            balance=Decimal("0.00"),
        )
        self.db.add(wallet)
        await self.db.flush()
        await self.db.refresh(wallet)
        return wallet

    async def get_or_create_manager_wallet(self, manager_id: UUID) -> Wallet:
        wallet = await self.get_manager_wallet(manager_id)
        if wallet:
            return wallet

        wallet = Wallet(
            wallet_type=WalletType.MANAGER.value,
            manager_id=manager_id,
            currency="USD",
            balance=Decimal("0.00"),
        )
        self.db.add(wallet)
        await self.db.flush()
        await self.db.refresh(wallet)
        return wallet

    async def create_wallet_transaction(
        self,
        wallet: Wallet,
        order_id: UUID,
        amount: Decimal,
        description: str,
        details: Optional[dict] = None,
    ) -> Optional[WalletTransaction]:
        normalized_amount = self._quantize_money(amount)
        if normalized_amount == Decimal("0.00"):
            return None

        wallet.balance = self._quantize_money(wallet.balance + normalized_amount)
        transaction = WalletTransaction(
            wallet_id=wallet.id,
            order_id=order_id,
            transaction_type=WalletTransactionType.CREDIT.value,
            amount=normalized_amount,
            description=description,
            details=details,
        )
        self.db.add(transaction)
        await self.db.flush()
        return transaction

    async def credit_order_commission(self, order_id: UUID) -> bool:
        commission = await self.get_order_commission(order_id)
        if not commission:
            raise NotFoundException("Order commission not found")

        if commission.credited_at:
            return False

        manager_wallet = await self.get_or_create_manager_wallet(commission.manager_id)
        platform_wallet = await self.get_or_create_platform_wallet()

        await self.create_wallet_transaction(
            wallet=manager_wallet,
            order_id=order_id,
            amount=commission.manager_profit_amount,
            description="Manager commission credit",
            details={"beneficiary": "manager"},
        )
        await self.create_wallet_transaction(
            wallet=platform_wallet,
            order_id=order_id,
            amount=commission.platform_profit_amount,
            description="Platform profit credit",
            details={"beneficiary": "platform"},
        )

        commission.credited_at = datetime.utcnow()
        await self.db.flush()
        return True

    async def get_wallet(self, wallet_id: UUID) -> Optional[Wallet]:
        result = await self.db.execute(
            select(Wallet)
            .options(selectinload(Wallet.transactions))
            .where(Wallet.id == wallet_id)
        )
        return result.scalar_one_or_none()

    async def list_wallet_transactions(self, wallet_id: UUID) -> List[WalletTransaction]:
        result = await self.db.execute(
            select(WalletTransaction)
            .where(WalletTransaction.wallet_id == wallet_id)
            .order_by(WalletTransaction.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_order(self, order_id: UUID) -> Optional[Order]:
        result = await self.db.execute(select(Order).where(Order.id == order_id))
        return result.scalar_one_or_none()
