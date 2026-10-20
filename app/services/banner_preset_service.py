from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, PermissionDenied
from app.models.banner_preset import BannerPreset, BannerPresetScope
from app.models.user import User, UserRole


class BannerPresetService:
    """Service for default banner catalog operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, banner_id: UUID) -> Optional[BannerPreset]:
        result = await self.db.execute(
            select(BannerPreset).where(BannerPreset.id == banner_id)
        )
        return result.scalar_one_or_none()

    def can_read(self, actor: User, banner: BannerPreset) -> bool:
        """Whether the caller may see this banner."""
        if actor.role == UserRole.SUPER_ADMIN.value:
            return True
        if actor.role not in {UserRole.DIRECTOR.value, UserRole.FAMILY_ADMIN.value}:
            return False
        if banner.owner_scope == BannerPresetScope.ZENDORA.value:
            return True
        return (
            banner.owner_scope == BannerPresetScope.FUNERAL_HOME.value
            and actor.funeral_home_id is not None
            and banner.funeral_home_id == actor.funeral_home_id
        )

    def can_edit(self, actor: User, banner: BannerPreset) -> bool:
        """Whether the caller may update or deactivate this banner."""
        if actor.role == UserRole.SUPER_ADMIN.value:
            return True
        if actor.role != UserRole.DIRECTOR.value:
            return False
        return (
            banner.owner_scope == BannerPresetScope.FUNERAL_HOME.value
            and actor.funeral_home_id is not None
            and banner.funeral_home_id == actor.funeral_home_id
        )

    def _visibility_filters(self, actor: User):
        if actor.role == UserRole.SUPER_ADMIN.value:
            return []

        clauses = [BannerPreset.owner_scope == BannerPresetScope.ZENDORA.value]
        if actor.funeral_home_id:
            clauses.append(
                (BannerPreset.owner_scope == BannerPresetScope.FUNERAL_HOME.value)
                & (BannerPreset.funeral_home_id == actor.funeral_home_id)
            )
        return [or_(*clauses)]

    async def list_for_user(
        self,
        actor: User,
        active_only: bool = True,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> tuple[List[BannerPreset], int]:
        """List banners the caller may use, ordered by sort_order then name."""
        filters = self._visibility_filters(actor)
        if active_only:
            filters.append(BannerPreset.is_active == True)

        count_query = select(func.count()).select_from(BannerPreset)
        if filters:
            count_query = count_query.where(*filters)
        total = (await self.db.execute(count_query)).scalar() or 0

        query = select(BannerPreset)
        if filters:
            query = query.where(*filters)
        query = query.order_by(BannerPreset.sort_order, BannerPreset.name)
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    def resolve_create_scope(self, actor: User) -> tuple[BannerPresetScope, Optional[UUID]]:
        """Force scope from the caller. Super admin → Zendora, director → their home."""
        if actor.role == UserRole.SUPER_ADMIN.value:
            return BannerPresetScope.ZENDORA, None
        if actor.role == UserRole.DIRECTOR.value:
            if not actor.funeral_home_id:
                raise PermissionDenied(
                    "Directors must belong to a funeral home to create default banners"
                )
            return BannerPresetScope.FUNERAL_HOME, actor.funeral_home_id
        raise PermissionDenied("You do not have permission to create default banners")

    async def create(
        self,
        created_by: UUID,
        name: str,
        image_url: str,
        owner_scope: BannerPresetScope,
        funeral_home_id: Optional[UUID] = None,
        sort_order: int = 0,
        is_active: bool = True,
    ) -> BannerPreset:
        scope_value = (
            owner_scope.value if isinstance(owner_scope, BannerPresetScope) else owner_scope
        )
        if scope_value == BannerPresetScope.ZENDORA.value:
            funeral_home_id = None
        elif not funeral_home_id:
            raise PermissionDenied("Funeral-home banners require a funeral home")

        banner = BannerPreset(
            created_by=created_by,
            name=name,
            image_url=image_url,
            owner_scope=scope_value,
            funeral_home_id=funeral_home_id,
            sort_order=sort_order,
            is_active=is_active,
        )
        self.db.add(banner)
        await self.db.flush()
        await self.db.refresh(banner)
        return banner

    async def update(
        self,
        banner_id: UUID,
        name: Optional[str] = None,
        image_url: Optional[str] = None,
        sort_order: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> BannerPreset:
        banner = await self.get_by_id(banner_id)
        if not banner:
            raise NotFoundException("Banner preset not found")

        if name is not None:
            banner.name = name
        if image_url is not None:
            banner.image_url = image_url
        if sort_order is not None:
            banner.sort_order = sort_order
        if is_active is not None:
            banner.is_active = is_active

        await self.db.flush()
        await self.db.refresh(banner)
        return banner

    async def deactivate(self, banner_id: UUID) -> BannerPreset:
        banner = await self.get_by_id(banner_id)
        if not banner:
            raise NotFoundException("Banner preset not found")

        banner.is_active = False
        await self.db.flush()
        await self.db.refresh(banner)
        return banner
