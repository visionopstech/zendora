from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional, List
from decimal import Decimal

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
            .options(selectinload(User.manager_commission))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.manager_commission))
            .where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        role: Optional[UserRole] = None,
        include_inactive: bool = False
    ) -> List[User]:
        """Get all users, optionally filtered by role."""
        query = select(User).options(selectinload(User.manager_commission))
        
        if role:
            query = query.where(User.role == role.value)
        
        if not include_inactive:
            query = query.where(User.is_active == True)
        
        query = query.order_by(User.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_manager_admins(self, manager_id: UUID) -> List[User]:
        """Get all admins belonging to a specific manager."""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.manager_commission))
            .where(
                User.manager_id == manager_id,
                User.role == UserRole.ADMIN.value
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
        manager_id: Optional[UUID] = None,
        vendor_id: Optional[UUID] = None,
        profit_percentage: Optional[Decimal] = None
    ) -> User:
        """Create a new user."""
        # Check if email already exists
        existing_user = await self.get_by_email(email)
        if existing_user:
            raise ConflictError("User with this email already exists")
        
        # Validate role-specific requirements
        if role == UserRole.ADMIN and not manager_id:
            raise PermissionDenied("ADMIN users must have a manager_id")
        
        if role == UserRole.VENDOR and not vendor_id:
            raise PermissionDenied("VENDOR users must have a vendor_id")

        if profit_percentage is not None and role != UserRole.MANAGER:
            raise PermissionDenied("profit_percentage can only be set for MANAGER users")
        
        # Verify manager exists if manager_id provided
        if manager_id:
            manager = await self.get_by_id(manager_id)
            if not manager:
                raise NotFoundException("Manager not found")
            if manager.role != UserRole.MANAGER.value:
                raise PermissionDenied("Specified manager_id must belong to a MANAGER user")
        
        # Verify vendor exists if vendor_id provided
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
            manager_id=manager_id,
            vendor_id=vendor_id,
            is_active=True
        )
        
        self.db.add(user)
        await self.db.flush()

        if role == UserRole.MANAGER and profit_percentage is not None:
            financial_service = FinancialService(self.db)
            await financial_service.upsert_manager_commission(user.id, profit_percentage)

        user = await self.get_by_id(user.id)
        
        return user
    
    async def update(
        self,
        user_id: UUID,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        manager_id: Optional[UUID] = None,
        vendor_id: Optional[UUID] = None,
        password: Optional[str] = None,
        profit_percentage: Optional[Decimal] = None,
        profit_percentage_provided: bool = False,
    ) -> User:
        """Update user details."""
        user = await self.get_by_id(user_id)
        
        if not user:
            raise NotFoundException("User not found")
        
        # Check email uniqueness if changing email
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
            
            # Validate role-specific requirements
            if role == UserRole.ADMIN and not (user.manager_id or manager_id):
                raise PermissionDenied("ADMIN users must have a manager_id")
            if role == UserRole.VENDOR and not (user.vendor_id or vendor_id):
                raise PermissionDenied("VENDOR users must have a vendor_id")
        
        if is_active is not None:
            user.is_active = is_active
        
        if manager_id is not None:
            # Verify manager exists
            manager = await self.get_by_id(manager_id)
            if not manager:
                raise NotFoundException("Manager not found")
            if manager.role != UserRole.MANAGER.value:
                raise PermissionDenied("Specified manager_id must belong to a MANAGER user")
            user.manager_id = manager_id
        
        if vendor_id is not None:
            # Verify vendor exists
            result = await self.db.execute(select(Vendor).where(Vendor.id == vendor_id))
            vendor = result.scalar_one_or_none()
            if not vendor:
                raise NotFoundException("Vendor not found")
            user.vendor_id = vendor_id
        
        if password:
            user.password_hash = hash_password(password)

        if profit_percentage_provided and resulting_role != UserRole.MANAGER.value:
            raise PermissionDenied("profit_percentage can only be set for MANAGER users")

        financial_service = FinancialService(self.db)
        if resulting_role == UserRole.MANAGER.value:
            if profit_percentage_provided:
                await financial_service.upsert_manager_commission(user.id, profit_percentage)
        else:
            commission = await financial_service.get_manager_commission(user.id)
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
