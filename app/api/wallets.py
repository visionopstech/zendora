from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.dependencies.auth import require_director, require_super_admin
from app.models.user import User
from app.schemas.wallet import WalletResponse
from app.services.financial_service import FinancialService

router = APIRouter()


@router.get("/wallets/me", response_model=WalletResponse)
async def get_my_wallet(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_director),
):
    """Return the authenticated director wallet."""
    service = FinancialService(db)
    wallet = await service.get_or_create_director_wallet(current_user.id)
    await db.commit()
    wallet = await service.get_wallet(wallet.id)
    return WalletResponse.model_validate(wallet)


@router.get("/wallets/platform", response_model=WalletResponse)
async def get_platform_wallet(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Return the Zendora platform wallet."""
    service = FinancialService(db)
    wallet = await service.get_or_create_platform_wallet()
    await db.commit()
    wallet = await service.get_wallet(wallet.id)
    return WalletResponse.model_validate(wallet)


@router.get("/wallets/directors/{director_id}", response_model=WalletResponse)
async def get_director_wallet(
    director_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Return a director wallet for back-office review."""
    service = FinancialService(db)
    wallet = await service.get_or_create_director_wallet(director_id)
    await db.commit()
    wallet = await service.get_wallet(wallet.id)
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    return WalletResponse.model_validate(wallet)
