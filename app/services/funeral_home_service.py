from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundException, PermissionDenied
from app.models.funeral_home import FuneralHome
from app.models.gift_collection import GiftCollection
from app.models.user import User, UserRole


class FuneralHomeService:
    """Service for funeral home operations, including director assignment."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _home_options(self):
        return [
            selectinload(FuneralHome.director),
            selectinload(FuneralHome.members),
        ]

    async def get_by_id(self, funeral_home_id: UUID) -> Optional[FuneralHome]:
        """Get a funeral home by ID with its director and members loaded."""
        result = await self.db.execute(
            select(FuneralHome)
            .options(*self._home_options())
            .where(FuneralHome.id == funeral_home_id)
        )
        return result.scalar_one_or_none()

    async def get_by_director(self, director_id: UUID) -> Optional[FuneralHome]:
        """Get the funeral home a director is the main director of."""
        result = await self.db.execute(
            select(FuneralHome)
            .options(*self._home_options())
            .where(FuneralHome.director_id == director_id)
        )
        return result.scalar_one_or_none()

    async def list_directors(self, funeral_home_id: UUID) -> List[User]:
        """List every director assigned to a funeral home."""
        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.funeral_home),
                selectinload(User.directed_funeral_home),
            )
            .where(
                User.funeral_home_id == funeral_home_id,
                User.role == UserRole.DIRECTOR.value,
            )
            .order_by(User.created_at.asc())
        )
        return list(result.scalars().all())

    async def count_families(self, funeral_home_id: UUID) -> int:
        """Count family admins attached to a funeral home."""
        result = await self.db.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.funeral_home_id == funeral_home_id,
                User.role == UserRole.FAMILY_ADMIN.value,
            )
        )
        return result.scalar() or 0

    async def list_funeral_homes(
        self,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        has_director: Optional[bool] = None,
        ids: Optional[List[UUID]] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[List[FuneralHome], int]:
        """List funeral homes with filters, returning the page and total count."""
        filters = []

        if ids is not None:
            if not ids:
                return [], 0
            filters.append(FuneralHome.id.in_(ids))
        if is_active is not None:
            filters.append(FuneralHome.is_active == is_active)
        if has_director is True:
            filters.append(FuneralHome.director_id.isnot(None))
        elif has_director is False:
            filters.append(FuneralHome.director_id.is_(None))
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    FuneralHome.name.ilike(pattern),
                    FuneralHome.email.ilike(pattern),
                    FuneralHome.description.ilike(pattern),
                )
            )

        count_query = select(func.count()).select_from(FuneralHome)
        if filters:
            count_query = count_query.where(*filters)
        total = (await self.db.execute(count_query)).scalar() or 0

        query = select(FuneralHome).options(*self._home_options())
        if filters:
            query = query.where(*filters)
        query = query.order_by(FuneralHome.name).offset(offset).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def create(
        self,
        name: str,
        description: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[dict] = None,
        logo_url: Optional[str] = None,
        director_id: Optional[UUID] = None,
    ) -> FuneralHome:
        """Create a funeral home, optionally assigning a director immediately."""
        funeral_home = FuneralHome(
            name=name,
            description=description,
            email=email,
            phone=phone,
            address=address,
            logo_url=logo_url,
            is_active=True,
        )

        self.db.add(funeral_home)
        await self.db.flush()

        if director_id:
            await self.add_director(funeral_home.id, director_id, is_main=True)

        await self.db.refresh(funeral_home)
        return await self.get_by_id(funeral_home.id)

    async def update(
        self,
        funeral_home_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[dict] = None,
        logo_url: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> FuneralHome:
        """Update funeral home details."""
        funeral_home = await self.get_by_id(funeral_home_id)
        if not funeral_home:
            raise NotFoundException("Funeral home not found")

        if name is not None:
            funeral_home.name = name
        if description is not None:
            funeral_home.description = description
        if email is not None:
            funeral_home.email = email
        if phone is not None:
            funeral_home.phone = phone
        if address is not None:
            funeral_home.address = address
        if logo_url is not None:
            funeral_home.logo_url = logo_url
        if is_active is not None:
            funeral_home.is_active = is_active

        await self.db.flush()
        await self.db.refresh(funeral_home)
        return funeral_home

    async def deactivate(self, funeral_home_id: UUID) -> FuneralHome:
        """Soft delete a funeral home."""
        funeral_home = await self.get_by_id(funeral_home_id)
        if not funeral_home:
            raise NotFoundException("Funeral home not found")

        funeral_home.is_active = False
        await self.db.flush()
        await self.db.refresh(funeral_home)
        return funeral_home

    async def _load_director_user(self, user_id: UUID) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        director = result.scalar_one_or_none()
        if not director:
            raise NotFoundException("User not found")
        if director.role != UserRole.DIRECTOR.value:
            raise PermissionDenied("Only DIRECTOR users can be assigned to a funeral home")
        return director

    async def add_director(
        self,
        funeral_home_id: UUID,
        user_id: UUID,
        is_main: bool = False,
    ) -> FuneralHome:
        """
        Add a director to a funeral home.

        The first director (or an explicit is_main) becomes the main director.
        Additional directors share funeral_home_id but are not the main director.
        """
        funeral_home = await self.get_by_id(funeral_home_id)
        if not funeral_home:
            raise NotFoundException("Funeral home not found")

        director = await self._load_director_user(user_id)

        if director.funeral_home_id and director.funeral_home_id != funeral_home_id:
            raise ConflictError(
                "This director is already assigned to another funeral home"
            )

        existing_main = await self.get_by_director(user_id)
        if existing_main and existing_main.id != funeral_home_id:
            raise ConflictError(
                f"This director is already assigned to funeral home '{existing_main.name}'"
            )

        make_main = is_main or funeral_home.director_id is None
        if make_main and funeral_home.director_id and funeral_home.director_id != user_id:
            funeral_home.director_id = user_id
        elif make_main:
            funeral_home.director_id = user_id

        director.funeral_home_id = funeral_home_id
        await self._cascade_funeral_home(user_id, funeral_home_id)

        await self.db.flush()
        return await self.get_by_id(funeral_home_id)

    async def set_main_director(self, funeral_home_id: UUID, user_id: UUID) -> FuneralHome:
        """Designate an existing home director as the main director."""
        funeral_home = await self.get_by_id(funeral_home_id)
        if not funeral_home:
            raise NotFoundException("Funeral home not found")

        director = await self._load_director_user(user_id)
        if director.funeral_home_id != funeral_home_id:
            raise ConflictError("Director must already belong to this funeral home")

        funeral_home.director_id = user_id
        await self.db.flush()
        return await self.get_by_id(funeral_home_id)

    async def remove_director(self, funeral_home_id: UUID, user_id: UUID) -> FuneralHome:
        """Remove a non-main director from a funeral home."""
        funeral_home = await self.get_by_id(funeral_home_id)
        if not funeral_home:
            raise NotFoundException("Funeral home not found")

        director = await self._load_director_user(user_id)
        if director.funeral_home_id != funeral_home_id:
            raise NotFoundException("This director is not assigned to this funeral home")

        if funeral_home.director_id == user_id:
            raise ConflictError(
                "Cannot remove the main director. Set a new main director first."
            )

        director.funeral_home_id = None
        await self._cascade_funeral_home(user_id, None)

        await self.db.flush()
        return await self.get_by_id(funeral_home_id)

    async def assign_director(self, funeral_home_id: UUID, user_id: UUID) -> FuneralHome:
        """Backward-compatible alias: add a director and make them main if none exists."""
        return await self.add_director(funeral_home_id, user_id, is_main=False)

    async def unassign_director(self, funeral_home_id: UUID) -> FuneralHome:
        """Remove the main director only when they are the sole director."""
        funeral_home = await self.get_by_id(funeral_home_id)
        if not funeral_home:
            raise NotFoundException("Funeral home not found")

        if not funeral_home.director_id:
            raise NotFoundException("This funeral home has no director assigned")

        directors = await self.list_directors(funeral_home_id)
        if len(directors) > 1:
            raise ConflictError(
                "Cannot remove the main director while other directors remain. "
                "Set a new main director first."
            )

        director_id = funeral_home.director_id
        funeral_home.director_id = None

        result = await self.db.execute(select(User).where(User.id == director_id))
        director = result.scalar_one_or_none()
        if director:
            director.funeral_home_id = None

        await self._cascade_funeral_home(director_id, None)

        await self.db.flush()
        return await self.get_by_id(funeral_home_id)

    async def _cascade_funeral_home(
        self,
        director_id: UUID,
        funeral_home_id: Optional[UUID],
    ) -> None:
        """Propagate a funeral home change to a director's families and collections."""
        await self.db.execute(
            update(User)
            .where(
                User.director_id == director_id,
                User.role == UserRole.FAMILY_ADMIN.value,
            )
            .values(funeral_home_id=funeral_home_id)
        )
        await self.db.execute(
            update(GiftCollection)
            .where(GiftCollection.director_id == director_id)
            .values(funeral_home_id=funeral_home_id)
        )
