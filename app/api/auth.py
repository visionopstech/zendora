from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.user import (
    UserLogin,
    TokenResponse,
    UserResponse,
    MagicLinkRequest,
    MagicLinkVerify,
    ThirdPartyLoginRequest,
)
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.third_party_auth import ThirdPartyAuthService
from app.models.user import UserRole
from app.core.exceptions import UnauthorizedError, ConflictError

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password.
    
    Returns JWT access token.
    """
    auth_service = AuthService(db)
    
    try:
        user, token = await auth_service.login_with_password(
            credentials.email,
            credentials.password
        )
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user)
        )
    except UnauthorizedError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/magic-link/request")
async def request_magic_link(
    request: MagicLinkRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Request a magic link to be sent to the email.
    
    In production, this would send an email with the magic link.
    For MVP, we return the token directly.
    """
    auth_service = AuthService(db)
    user_service = UserService(db)
    
    # Check if user exists
    user = await user_service.get_by_email(request.email)
    if not user:
        # For security, don't reveal if email exists
        return {
            "message": "If the email exists, a magic link has been sent",
            "status": "success"
        }
    
    # Generate magic link token
    token = auth_service.generate_magic_link_token(request.email)
    
    # TODO: Send email with magic link via SendGrid
    # For now, return the token directly for testing
    # background_tasks.add_task(send_magic_link_email, request.email, token)
    
    return {
        "message": "Magic link sent successfully",
        "status": "success",
        # Remove this in production!
        "debug_token": token
    }


@router.get("/magic-link/verify", response_model=TokenResponse)
async def verify_magic_link(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify magic link token and return JWT access token.
    """
    auth_service = AuthService(db)
    
    try:
        user, access_token = await auth_service.verify_magic_link_token(token)
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user)
        )
    except UnauthorizedError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/redirect-login", response_model=TokenResponse)
async def redirect_login(
    request: ThirdPartyLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login using third-party redirect token.
    
    This endpoint:
    1. Verifies the token with the third-party provider
    2. Auto-creates user if not exists
    3. Returns JWT access token
    """
    auth_service = AuthService(db)
    user_service = UserService(db)
    third_party_service = ThirdPartyAuthService()
    
    try:
        # Verify token with third-party provider
        user_info = await third_party_service.verify_and_get_user_info(request.token)
        
        # Check if user exists
        user = await user_service.get_by_email(user_info.email)
        
        # Auto-create user if not exists
        if not user:
            user = await user_service.create_user(
                email=user_info.email,
                password=None,  # No password for third-party users
                role=UserRole.VISITOR,  # Default to visitor
                full_name=user_info.full_name
            )
            await db.commit()
        
        # Create JWT token
        token = auth_service.create_token_for_user(user)
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user)
        )
        
    except UnauthorizedError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
