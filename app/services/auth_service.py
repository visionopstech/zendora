from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import secrets
from typing import Optional

from app.models.user import User, UserRole
from app.core.security import create_access_token
from app.core.exceptions import UnauthorizedError, ConflictError
from app.services.user_service import UserService


# In-memory store for magic link tokens (in production, use Redis)
_magic_link_tokens: dict[str, dict] = {}


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)
    
    def create_token_for_user(self, user: User) -> str:
        """Create JWT access token for a user."""
        # Handle role - it might be a string or enum depending on context
        role_value = user.role if isinstance(user.role, str) else user.role.value
        
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": role_value,
        }
        return create_access_token(token_data)
    
    async def login_with_password(self, email: str, password: str) -> tuple[User, str]:
        """
        Authenticate user with email and password.
        Returns user and access token.
        """
        user = await self.user_service.authenticate(email, password)
        
        if not user:
            raise UnauthorizedError("Invalid email or password")
        
        token = self.create_token_for_user(user)
        return user, token
    
    def generate_magic_link_token(self, email: str) -> str:
        """Generate a magic link token."""
        token = secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + timedelta(minutes=15)
        
        _magic_link_tokens[token] = {
            "email": email,
            "expiry": expiry
        }
        
        return token
    
    async def verify_magic_link_token(self, token: str) -> tuple[User, str]:
        """
        Verify magic link token and return user with access token.
        """
        token_data = _magic_link_tokens.get(token)
        
        if not token_data:
            raise UnauthorizedError("Invalid or expired magic link token")
        
        if datetime.utcnow() > token_data["expiry"]:
            del _magic_link_tokens[token]
            raise UnauthorizedError("Magic link token has expired")
        
        email = token_data["email"]
        user = await self.user_service.get_by_email(email)
        
        if not user:
            raise UnauthorizedError("User not found")
        
        if not user.is_active:
            raise UnauthorizedError("User account is inactive")
        
        # Remove used token
        del _magic_link_tokens[token]
        
        access_token = self.create_token_for_user(user)
        return user, access_token
    
    async def register_user(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None
    ) -> tuple[User, str]:
        """
        Register a new user with email and password.
        Returns user and access token.
        """
        # Check if user already exists
        existing_user = await self.user_service.get_by_email(email)
        if existing_user:
            raise ConflictError("User with this email already exists")
        
        # Create new user with VISITOR role by default
        user = await self.user_service.create_user(
            email=email,
            password=password,
            role=UserRole.VISITOR,
            full_name=full_name
        )
        
        # Create access token
        token = self.create_token_for_user(user)
        
        return user, token
    
    async def cleanup_expired_tokens(self):
        """Remove expired magic link tokens."""
        now = datetime.utcnow()
        expired = [
            token for token, data in _magic_link_tokens.items()
            if data["expiry"] < now
        ]
        for token in expired:
            del _magic_link_tokens[token]
