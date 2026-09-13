from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.models.user import User, UserRole
from app.services.user_service import UserService


class VisitorService:
    """Service for visitor-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)
    
    async def get_or_create_visitor(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        """
        Get existing visitor or create a new one.
        
        Args:
            email: Visitor email
            first_name: Visitor first name
            last_name: Visitor last name
            
        Returns:
            User: Visitor user object
        """
        visitor = await self.user_service.get_by_email(email)
        
        if visitor:
            if visitor.role != UserRole.VISITOR:
                return visitor
            
            updated = False
            if first_name and visitor.first_name != first_name:
                visitor.first_name = first_name
                updated = True
            if last_name and visitor.last_name != last_name:
                visitor.last_name = last_name
                updated = True
            if updated:
                await self.db.flush()
                await self.db.refresh(visitor)
            
            return visitor
        
        visitor = await self.user_service.create_user(
            email=email,
            password=None,
            role=UserRole.VISITOR,
            first_name=first_name,
            last_name=last_name,
        )
        
        await self.db.flush()
        await self.db.refresh(visitor)
        
        return visitor
