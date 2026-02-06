"""Admin panel configuration and setup."""
from sqladmin import Admin

from app.admin.auth import AdminAuthBackend
from app.admin.views import (
    UserAdmin,
    VendorAdmin,
    ProductAdmin,
    WishlistAdmin,
    OrderAdmin,
    ProductVendorAdmin,
    WishlistProductAdmin,
    OrderProductAdmin,
)
from app.core.config import settings


def setup_admin(app, engine):
    """
    Setup and configure SQLAdmin for the FastAPI application.
    
    Note: SessionMiddleware must be added to the app before calling this function.
    
    Args:
        app: FastAPI application instance
        engine: SQLAlchemy sync engine (for admin compatibility)
        
    Returns:
        Admin: Configured SQLAdmin instance
    """
    # Create authentication backend
    authentication_backend = AdminAuthBackend(secret_key=settings.jwt_secret)
    
    # Create admin instance with sync engine
    admin = Admin(
        app=app,
        engine=engine,
        title="Zendora Admin",
        base_url="/admin",
        authentication_backend=authentication_backend,
    )
    
    # Register all model views
    admin.add_view(UserAdmin)
    admin.add_view(VendorAdmin)
    admin.add_view(ProductAdmin)
    admin.add_view(WishlistAdmin)
    admin.add_view(OrderAdmin)
    
    # Register junction table views (in "Associations" category)
    admin.add_view(ProductVendorAdmin)
    admin.add_view(WishlistProductAdmin)
    admin.add_view(OrderProductAdmin)
    
    return admin


__all__ = ["setup_admin"]
