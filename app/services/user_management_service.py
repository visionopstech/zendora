from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, List
from decimal import Decimal

from app.models.funeral_home import FuneralHome
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.core.security import hash_password
from app.core.exceptions import NotFoundException, ConflictError, PermissionDenied
from app.services.financial_service import FinancialService


class UserManagementService:
    """Service for user management operations (CRUD)."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.director_commission))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.director_commission))
            .where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        role: Optional[UserRole] = None,
        include_inactive: bool = False,
        funeral_home_id: Optional[UUID] = None,
        unassigned: Optional[bool] = None,
        search: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> tuple[List[User], int]:
        """
        List users with filters, returning the page and the total count.

        `unassigned=True` returns users without a funeral home, which is how a
        super admin finds directors awaiting assignment.
        """
        filters = []
        
        if role:
            filters.append(User.role == (role.value if isinstance(role, UserRole) else role))
        
        if not include_inactive:
            filters.append(User.is_active == True)
        
        if funeral_home_id is not None:
            filters.append(User.funeral_home_id == funeral_home_id)
        
        if unassigned is True:
            filters.append(User.funeral_home_id.is_(None))
        elif unassigned is False:
            filters.append(User.funeral_home_id.isnot(None))
        
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    User.email.ilike(pattern),
                    User.full_name.ilike(pattern),
                )
            )
        
        count_query = select(func.count()).select_from(User)
        if filters:
            count_query = count_query.where(*filters)
        total = (await self.db.execute(count_query)).scalar() or 0
        
        query = select(User).options(selectinload(User.director_commission))
        if filters:
            query = query.where(*filters)
        query = query.order_by(User.created_at.desc())
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all()), total
    
    async def get_director_family_admins(self, director_id: UUID) -> List[User]:
        """Get all family admins belonging to a specific director."""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.director_commission))
            .where(
                User.director_id == director_id,
                User.role == UserRole.FAMILY_ADMIN.value
            ).order_by(User.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_vendor_users(self, vendor_id: UUID) -> List[User]:
        """Get all vendor users belonging to a specific vendor."""
        result = await self.db.execute(
            select(User).where(
                User.vendor_id == vendor_id,
                User.role == UserRole.VENDOR.value
            ).order_by(User.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def create(
        self,
        email: str,
        password: str,
        role: UserRole,
        full_name: Optional[str] = None,
        director_id: Optional[UUID] = None,
        funeral_home_id: Optional[UUID] = None,
        vendor_id: Optional[UUID] = None,
        profit_percentage: Optional[Decimal] = None
    ) -> User:
        """Create a new user."""
        existing_user = await self.get_by_email(email)
        if existing_user:
            raise ConflictError("User with this email already exists")
        
        if role == UserRole.FAMILY_ADMIN and not director_id:
            raise PermissionDenied("FAMILY_ADMIN users must have a director_id")
        
        if role == UserRole.VENDOR and not vendor_id:
            raise PermissionDenied("VENDOR users must have a vendor_id")

        if profit_percentage is not None and role != UserRole.DIRECTOR:
            raise PermissionDenied("profit_percentage can only be set for DIRECTOR users")
        
        director = None
        if director_id:
            director = await self.get_by_id(director_id)
            if not director:
                raise NotFoundException("Director not found")
            if director.role != UserRole.DIRECTOR.value:
                raise PermissionDenied("Specified director_id must belong to a DIRECTOR user")
        
        if funeral_home_id:
            await self._verify_funeral_home(funeral_home_id)
        elif director and role == UserRole.FAMILY_ADMIN:
            # Families inherit their director's funeral home by default.
            funeral_home_id = director.funeral_home_id
        
        if vendor_id:
            result = await self.db.execute(select(Vendor).where(Vendor.id == vendor_id))
            vendor = result.scalar_one_or_none()
            if not vendor:
                raise NotFoundException("Vendor not found")
        
        password_hash = hash_password(password)
        
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role.value if isinstance(role, UserRole) else role,
            director_id=director_id,
            funeral_home_id=funeral_home_id,
            vendor_id=vendor_id,
            is_active=True
        )
        
        self.db.add(user)
        await self.db.flush()

        if role == UserRole.DIRECTOR and profit_percentage is not None:
            financial_service = FinancialService(self.db)
            await financial_service.upsert_director_commission(user.id, profit_percentage)

        user = await self.get_by_id(user.id)
        
        return user
    
    async def update(
        self,
        user_id: UUID,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        director_id: Optional[UUID] = None,
        funeral_home_id: Optional[UUID] = None,
        vendor_id: Optional[UUID] = None,
        password: Optional[str] = None,
        profit_percentage: Optional[Decimal] = None,
        profit_percentage_provided: bool = False,
    ) -> User:
        """Update user details."""
        user = await self.get_by_id(user_id)
        
        if not user:
            raise NotFoundException("User not found")
        
        if email and email != user.email:
            existing_user = await self.get_by_email(email)
            if existing_user:
                raise ConflictError("User with this email already exists")
            user.email = email
        
        if full_name is not None:
            user.full_name = full_name
        
        resulting_role = user.role
        if role is not None:
            role_value = role.value if isinstance(role, UserRole) else role
            user.role = role_value
            resulting_role = role_value
            
            if role == UserRole.FAMILY_ADMIN and not (user.director_id or director_id):
                raise PermissionDenied("FAMILY_ADMIN users must have a director_id")
            if role == UserRole.VENDOR and not (user.vendor_id or vendor_id):
                raise PermissionDenied("VENDOR users must have a vendor_id")
        
        if is_active is not None:
            user.is_active = is_active
        
        if director_id is not None:
            director = await self.get_by_id(director_id)
            if not director:
                raise NotFoundException("Director not found")
            if director.role != UserRole.DIRECTOR.value:
                raise PermissionDenied("Specified director_id must belong to a DIRECTOR user")
            user.director_id = director_id
            if funeral_home_id is None and user.role == UserRole.FAMILY_ADMIN.value:
                user.funeral_home_id = director.funeral_home_id
        
        if funeral_home_id is not None:
            await self._verify_funeral_home(funeral_home_id)
            user.funeral_home_id = funeral_home_id
        
        if vendor_id is not None:
            result = await self.db.execute(select(Vendor).where(Vendor.id == vendor_id))
            vendor = result.scalar_one_or_none()
            if not vendor:
                raise NotFoundException("Vendor not found")
            user.vendor_id = vendor_id
        
        if password:
            user.password_hash = hash_password(password)

        if profit_percentage_provided and resulting_role != UserRole.DIRECTOR.value:
            raise PermissionDenied("profit_percentage can only be set for DIRECTOR users")

        financial_service = FinancialService(self.db)
        if resulting_role == UserRole.DIRECTOR.value:
            if profit_percentage_provided:
                await financial_service.upsert_director_commission(user.id, profit_percentage)
        else:
            commission = await financial_service.get_director_commission(user.id)
            if commission:
                await self.db.delete(commission)
        
        await self.db.flush()
        user = await self.get_by_id(user.id)
        
        return user
    
    async def delete(self, user_id: UUID) -> None:
        """Delete a user."""
        user = await self.get_by_id(user_id)
        
        if not user:
            raise NotFoundException("User not found")
        
        await self.db.delete(user)
        await self.db.flush()
    
    async def _verify_funeral_home(self, funeral_home_id: UUID) -> FuneralHome:
        result = await self.db.execute(
            select(FuneralHome).where(FuneralHome.id == funeral_home_id)
        )
        funeral_home = result.scalar_one_or_none()
        if not funeral_home:
            raise NotFoundException("Funeral home not found")
        return funeral_home
