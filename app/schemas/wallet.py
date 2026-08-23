from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WalletTransactionResponse(BaseModel):
    """Wallet ledger entry response."""

    id: UUID
    order_id: UUID
    transaction_type: str
    amount: Decimal
    description: Optional[str] = None
    details: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WalletResponse(BaseModel):
    """Wallet response with transaction history."""

    id: UUID
    wallet_type: str
    director_id: Optional[UUID] = None
    currency: str
    balance: Decimal
    created_at: datetime
    updated_at: Optional[datetime] = None
    transactions: List[WalletTransactionResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True
