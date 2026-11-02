from hmac import compare_digest
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.schemas.foveo_sync import FoveoSyncRequest, FoveoSyncResponse
from app.services.foveo_sync_service import FoveoSyncService

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


async def require_foveo_sync_secret(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> None:
    """Shared secret in env. Integration is off until FOVEO_SYNC_SECRET is set."""
    if not settings.foveo_sync_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Foveo integration is not configured",
        )
    token = credentials.credentials if credentials else ""
    if not credentials or credentials.scheme.lower() != "bearer" or not compare_digest(
        token, settings.foveo_sync_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
        )


@router.post("/sync", response_model=FoveoSyncResponse)
async def sync_foveo(
    payload: FoveoSyncRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_foveo_sync_secret),
) -> FoveoSyncResponse:
    """
    Inbound Foveo push. Do not log the body — it contains password hashes.
    """
    service = FoveoSyncService(db)
    try:
        result = await service.sync(payload)
        await db.commit()
        return result
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc
