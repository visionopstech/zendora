from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel
import httpx

from app.core.config import settings
from app.core.exceptions import UnauthorizedError


class UserInfo(BaseModel):
    """User information returned from third-party verification."""
    email: str
    full_name: Optional[str] = None
    user_id: Optional[str] = None  # External user ID


class ThirdPartyAuthProvider(ABC):
    """Abstract base class for third-party authentication providers."""
    
    @abstractmethod
    async def verify_token(self, token: str) -> UserInfo:
        """
        Verify a token with the third-party provider.
        
        Args:
            token: Token to verify
            
        Returns:
            UserInfo: User information from the provider
            
        Raises:
            UnauthorizedError: If token is invalid
        """
        pass


class DefaultThirdPartyAuthProvider(ThirdPartyAuthProvider):
    """Default implementation that calls a configured endpoint."""
    
    def __init__(self):
        self.auth_url = settings.third_party_auth_url
        self.auth_token = settings.third_party_auth_token
    
    async def verify_token(self, token: str) -> UserInfo:
        """
        Verify token by calling the configured third-party endpoint.
        
        Expected response format:
        {
            "valid": true,
            "email": "user@example.com",
            "full_name": "John Doe",  # Optional
            "user_id": "external-id"   # Optional
        }
        """
        if not self.auth_url:
            raise UnauthorizedError("Third-party authentication not configured")
        
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.auth_url,
                    json={"token": token},
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    raise UnauthorizedError("Third-party authentication failed")
                
                data = response.json()
                
                if not data.get("valid"):
                    raise UnauthorizedError("Invalid token")
                
                email = data.get("email")
                if not email:
                    raise UnauthorizedError("Email not provided by third-party")
                
                return UserInfo(
                    email=email,
                    full_name=data.get("full_name"),
                    user_id=data.get("user_id")
                )
                
        except httpx.RequestError as e:
            raise UnauthorizedError(f"Failed to verify token with third-party: {str(e)}")


class ThirdPartyAuthService:
    """Service for handling third-party authentication."""
    
    def __init__(self, provider: Optional[ThirdPartyAuthProvider] = None):
        self.provider = provider or DefaultThirdPartyAuthProvider()
    
    async def verify_and_get_user_info(self, token: str) -> UserInfo:
        """
        Verify token with third-party provider and return user info.
        
        Args:
            token: Token to verify
            
        Returns:
            UserInfo: User information from the provider
        """
        return await self.provider.verify_token(token)
