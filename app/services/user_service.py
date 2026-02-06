from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional
import secrets
from datetime import datetime, timedelta

from app.models.user import User, UserRole
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import NotFoundException, UnauthorizedError
from app.core.config import settings


class UserService:
    """Service for user-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def create_user(
        self,
        email: str,
        password: Optional[str],
        role: UserRole,
        full_name: Optional[str] = None,
        manager_id: Optional[UUID] = None
    ) -> User:
        """Create a new user."""
        password_hash = hash_password(password) if password else None
        
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role.value if isinstance(role, UserRole) else role,
            manager_id=manager_id,
            is_active=True
        )
        
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        
        return user
    
    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        user = await self.get_by_email(email)
        
        if not user or not user.password_hash:
            return None
        
        if not verify_password(password, user.password_hash):
            return None
        
        if not user.is_active:
            return None
        
        return user
    
    async def update_password(self, user_id: UUID, new_password: str) -> User:
        """Update user password."""
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")
        
        user.password_hash = hash_password(new_password)
        await self.db.flush()
        await self.db.refresh(user)
        
        return user
    
    def generate_password(self, length: int = 12) -> str:
        """Generate a random password."""
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    async def create_admin_with_manager(
        self,
        email: str,
        full_name: str,
        manager_id: UUID
    ) -> tuple[User, str]:
        """
        Create an admin user with a generated password.
        Returns the user and the plain text password.
        """
        password = self.generate_password()
        
        user = await self.create_user(
            email=email,
            password=password,
            role=UserRole.ADMIN.value,
            full_name=full_name,
            manager_id=manager_id
        )
        
        return user, password
    
    async def get_manager_admins(self, manager_id: UUID) -> list[User]:
        """Get all admins belonging to a manager."""
        result = await self.db.execute(
            select(User).where(
                User.manager_id == manager_id,
                User.role == UserRole.ADMIN.value
            )
        )
        return list(result.scalars().all())
