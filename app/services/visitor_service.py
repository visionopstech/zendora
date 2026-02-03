from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.models.user import User, UserRole
from app.services.user_service import UserService
from app.core.exceptions import ConflictError


class VisitorService:
    """Service for visitor-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)
    
    async def get_or_create_visitor(
        self,
        email: str,
        full_name: str
    ) -> User:
        """
        Get existing visitor or create a new one.
        
        Args:
            email: Visitor email
            full_name: Visitor full name
            
        Returns:
            User: Visitor user object
        """
        # Check if user already exists
        visitor = await self.user_service.get_by_email(email)
        
        if visitor:
            # If user exists but is not a visitor, that's a conflict
            if visitor.role != UserRole.VISITOR:
                # For MVP, we allow the purchase but don't change the role
                # In production, you might want to handle this differently
                return visitor
            
            # Update name if provided and different
            if full_name and visitor.full_name != full_name:
                visitor.full_name = full_name
                await self.db.flush()
                await self.db.refresh(visitor)
            
            return visitor
        
        # Create new visitor
        visitor = await self.user_service.create_user(
            email=email,
            password=None,  # No password for visitors in MVP
            role=UserRole.VISITOR,
            full_name=full_name
        )
        
        await self.db.flush()
        await self.db.refresh(visitor)
        
        return visitor
