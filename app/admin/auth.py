"""Admin authentication provider for SQLAdmin."""
from typing import Optional
from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import select
import logging

from app.core.config import settings
from app.core.database import sync_engine
from app.core.security import verify_password
from app.models.user import User, UserRole
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AdminAuthBackend(AuthenticationBackend):
    """
    Authentication backend for SQLAdmin panel.
    Supports two authentication methods:
    1. Environment variables (ADMIN_USERNAME and ADMIN_PASSWORD)
    2. Database SUPER_ADMIN users
    """

    async def login(self, request: Request) -> bool:
        """
        Handle admin login with username and password.
        
        Args:
            request: Starlette request object
            
        Returns:
            bool: True if login successful, False otherwise
        """
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        
        logger.info(f"Login attempt - Username: {username}")
        
        # First, try environment variable credentials
        if username == settings.admin_username and password == settings.admin_password:
            request.session.update({
                "authenticated": True,
                "user_email": username,
                "auth_type": "env"
            })
            logger.info("Login successful (environment credentials)")
            return True
        
        # Second, try database SUPER_ADMIN users
        try:
            with Session(sync_engine) as db:
                # Find user by email
                stmt = select(User).where(
                    User.email == username,
                    User.role == UserRole.SUPER_ADMIN.value,
                    User.is_active == True
                )
                user = db.execute(stmt).scalar_one_or_none()
                
                if user and user.password_hash:
                    # Verify password
                    if verify_password(password, user.password_hash):
                        request.session.update({
                            "authenticated": True,
                            "user_email": user.email,
                            "user_id": str(user.id),
                            "auth_type": "database"
                        })
                        logger.info(f"Login successful (database user: {user.email})")
                        return True
                    else:
                        logger.warning(f"Invalid password for user: {username}")
                else:
                    logger.warning(f"User not found or not SUPER_ADMIN: {username}")
        except Exception as e:
            logger.error(f"Database authentication error: {e}")
        
        logger.warning("Login failed")
        return False

    async def logout(self, request: Request) -> bool:
        """
        Handle admin logout.
        Clears session data.
        
        Args:
            request: Starlette request object
            
        Returns:
            bool: True if logout successful
        """
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """
        Authenticate each admin request.
        Validates user session.
        
        Args:
            request: Starlette request object
            
        Returns:
            bool: True if authenticated, False otherwise (will redirect to login)
        """
        authenticated = request.session.get("authenticated")
        
        if not authenticated:
            return False
        
        return True
