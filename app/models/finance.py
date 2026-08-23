import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, DateTime, ForeignKey, Numeric, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class WalletType(str, enum.Enum):
    """Wallet owner type."""

    DIRECTOR = "DIRECTOR"
    PLATFORM = "PLATFORM"


class WalletTransactionType(str, enum.Enum):
    """Supported wallet transaction types."""

    CREDIT = "CREDIT"
    DEBIT = "DEBIT"


class DirectorCommission(Base):
    """Stores commission configuration for a director."""

    __tablename__ = "director_commissions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )
    director_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    profit_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=datetime.utcnow,
        nullable=True,
    )

    director: Mapped["User"] = relationship("User", back_populates="director_commission")

    def __repr__(self) -> str:
        return (
            f"<DirectorCommission(director_id={self.director_id}, "
            f"profit_percentage={self.profit_percentage})>"
        )


class Wallet(Base):
    """Internal wallet ledger for directors and the platform."""

    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )
    wallet_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    director_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=datetime.utcnow,
        nullable=True,
    )

    director: Mapped[Optional["User"]] = relationship("User", back_populates="wallet")
    transactions: Mapped[List["WalletTransaction"]] = relationship(
        "WalletTransaction",
        back_populates="wallet",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Wallet(id={self.id}, wallet_type={self.wallet_type}, balance={self.balance})>"


class OrderCommission(Base):
    """Order-level commission snapshot."""

    __tablename__ = "order_commissions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    director_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    base_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    final_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    raw_benefit_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    director_profit_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    director_profit_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    platform_profit_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    credited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    order: Mapped["Order"] = relationship("Order", back_populates="commission")
    director: Mapped["User"] = relationship("User", back_populates="order_commissions")

    def __repr__(self) -> str:
        return (
            f"<OrderCommission(order_id={self.order_id}, director_id={self.director_id}, "
            f"director_profit={self.director_profit_amount})>"
        )


class WalletTransaction(Base):
    """A single wallet ledger entry."""

    __tablename__ = "wallet_transactions"
    __table_args__ = (
        UniqueConstraint("wallet_id", "order_id", "transaction_type", name="uq_wallet_order_transaction"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="transactions")
    order: Mapped["Order"] = relationship("Order", back_populates="wallet_transactions")

    def __repr__(self) -> str:
        return (
            f"<WalletTransaction(wallet_id={self.wallet_id}, order_id={self.order_id}, "
            f"amount={self.amount})>"
        )
