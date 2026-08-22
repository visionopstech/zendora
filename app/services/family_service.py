from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.gift_collection import GiftCollection, GiftCollectionStatus
from app.models.user import User, UserRole


class FamilyService:
    """Read model for family admins enriched with funeral home and collection data."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, family_admin_id: UUID) -> Optional[User]:
        """Get a family admin with funeral home and director loaded."""
        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.funeral_home),
                selectinload(User.director),
            )
            .where(
                User.id == family_admin_id,
                User.role == UserRole.FAMILY_ADMIN.value,
            )
        )
        return result.scalar_one_or_none()

    async def list_families(
        self,
        funeral_home_id: Optional[UUID] = None,
        director_id: Optional[UUID] = None,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[List[User], int]:
        """List family admins with filters, returning the page and total count."""
        filters = [User.role == UserRole.FAMILY_ADMIN.value]

        if funeral_home_id is not None:
            filters.append(User.funeral_home_id == funeral_home_id)
        if director_id is not None:
            filters.append(User.director_id == director_id)
        if is_active is not None:
            filters.append(User.is_active == is_active)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                )
            )

        count_query = select(func.count()).select_from(User).where(*filters)
        total = (await self.db.execute(count_query)).scalar() or 0

        query = (
            select(User)
            .options(
                selectinload(User.funeral_home),
                selectinload(User.director),
            )
            .where(*filters)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def get_collection_stats(
        self,
        family_admin_ids: List[UUID],
    ) -> dict[UUID, dict]:
        """
        Collect per-family collection counts and the published collection, if any.

        Returns a mapping of family admin id -> {count, published_id, published_slug}.
        """
        stats: dict[UUID, dict] = {
            family_admin_id: {
                "count": 0,
                "published_id": None,
                "published_slug": None,
            }
            for family_admin_id in family_admin_ids
        }

        if not family_admin_ids:
            return stats

        counts = await self.db.execute(
            select(GiftCollection.family_admin_id, func.count())
            .where(GiftCollection.family_admin_id.in_(family_admin_ids))
            .group_by(GiftCollection.family_admin_id)
        )
        for family_admin_id, count in counts.all():
            stats[family_admin_id]["count"] = count

        published = await self.db.execute(
            select(
                GiftCollection.family_admin_id,
                GiftCollection.id,
                GiftCollection.public_slug,
            ).where(
                GiftCollection.family_admin_id.in_(family_admin_ids),
                GiftCollection.status == GiftCollectionStatus.PUBLISHED.value,
            )
        )
        for family_admin_id, collection_id, public_slug in published.all():
            stats[family_admin_id]["published_id"] = collection_id
            stats[family_admin_id]["published_slug"] = public_slug

        return stats
