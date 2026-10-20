from datetime import datetime, timedelta
from hashlib import sha256
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

PASSWORD_RESET_TOKEN_USE = "password_reset"
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 1


# Password hashing context
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
    bcrypt__ident="2b"
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        bool: True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    
    Note:
        Bcrypt has a 72-byte password limit. Passwords are truncated if needed.
    """
    # Truncate password to 72 bytes to comply with bcrypt limit
    if len(password.encode('utf-8')) > 72:
        password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token
        expires_delta: Optional custom expiration time
        
    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: JWT token to decode
        
    Returns:
        Optional[dict]: Decoded token data or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None


def password_reset_fingerprint(password_hash: Optional[str]) -> str:
    """Short hash of the current password so a reset token dies after it is used."""
    return sha256((password_hash or "").encode("utf-8")).hexdigest()[:16]


def create_password_reset_token(
    user_id: UUID,
    email: str,
    password_hash: Optional[str],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a short-lived JWT used only for password reset."""
    return create_access_token(
        {
            "sub": str(user_id),
            "email": email,
            "token_use": PASSWORD_RESET_TOKEN_USE,
            "pwd": password_reset_fingerprint(password_hash),
        },
        expires_delta=expires_delta
        or timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS),
    )


def decode_password_reset_token(token: str) -> Optional[dict]:
    """Decode a password-reset JWT. Returns None if invalid, expired, or wrong type."""
    payload = decode_access_token(token)
    if not payload or payload.get("token_use") != PASSWORD_RESET_TOKEN_USE:
        return None
    return payload
