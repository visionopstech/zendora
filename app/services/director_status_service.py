from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundException, PermissionDenied
from app.models.user import User, UserRole
from app.services.director_scope import is_main_director


class DirectorStatusService:
    """Toggle a director's active status."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def set_active(
        self,
        actor: User,
        target_user_id: UUID,
        is_active: bool,
    ) -> User:
        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.funeral_home),
                selectinload(User.directed_funeral_home),
                selectinload(User.director_commission),
            )
            .where(User.id == target_user_id)
        )
        target = result.scalar_one_or_none()
        if not target:
            raise NotFoundException("User not found")
        if target.role != UserRole.DIRECTOR.value:
            raise ConflictError("Target user is not a director")

        target_is_main = is_main_director(target)
        if target_is_main:
            raise ConflictError(
                "Cannot change the main director's status. Set a new main director first."
            )

        if actor.role == UserRole.SUPER_ADMIN.value:
            pass
        elif actor.role == UserRole.DIRECTOR.value and is_main_director(actor):
            if actor.id == target.id:
                raise PermissionDenied("You cannot change your own director status")
            if target.funeral_home_id != actor.funeral_home_id:
                raise PermissionDenied(
                    "You can only change the status of directors in your funeral home"
                )
        else:
            raise PermissionDenied(
                "Only the main director or a super admin can change director status"
            )

        target.is_active = is_active
        await self.db.flush()
        await self.db.refresh(target)
        return target
