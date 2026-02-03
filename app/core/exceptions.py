from fastapi import HTTPException, status


class ZendoraException(Exception):
    """Base exception for all Zendora custom exceptions."""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class NotFoundException(ZendoraException):
    """Raised when a resource is not found."""
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(ZendoraException):
    """Raised when there's a conflict (e.g., duplicate resource)."""
    status_code = status.HTTP_409_CONFLICT


class PermissionDenied(ZendoraException):
    """Raised when user lacks permission for an action."""
    status_code = status.HTTP_403_FORBIDDEN


class UnauthorizedError(ZendoraException):
    """Raised when authentication fails."""
    status_code = status.HTTP_401_UNAUTHORIZED


class ValidationError(ZendoraException):
    """Raised when validation fails."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
