from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ConflictError, NotFoundException, PermissionDenied
from app.dependencies.auth import require_director, require_super_admin_or_director
from app.models.user import User
from app.schemas.user import DirectorStatisticsResponse, DirectorStatusUpdate, UserResponse
from app.services.director_statistics_service import DirectorStatisticsService
from app.services.director_status_service import DirectorStatusService

router = APIRouter()


@router.get("/director/statistics", response_model=DirectorStatisticsResponse)
async def get_director_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_director),
):
    """
    Director dashboard statistics.

    Main directors see funeral-home totals. Other directors see only their
    own families, collections, orders, sales and commissions.
    """
    service = DirectorStatisticsService(db)
    return DirectorStatisticsResponse.model_validate(
        await service.get_statistics(current_user)
    )


@router.patch("/directors/{user_id}/status", response_model=UserResponse)
async def update_director_status(
    user_id: UUID,
    payload: DirectorStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_super_admin_or_director),
):
    """
    Activate or deactivate a director.

    Super admins may change any non-main director. A main director may change
    other directors on their own funeral home.
    """
    service = DirectorStatusService(db)

    try:
        user = await service.set_active(
            actor=current_user,
            target_user_id=user_id,
            is_active=payload.is_active,
        )
        await db.commit()
        return UserResponse.model_validate(user)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except PermissionDenied as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
