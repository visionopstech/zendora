"""Admin panel configuration and setup."""
from sqladmin import Admin

from app.admin.auth import AdminAuthBackend
from app.admin.views import (
    UserAdmin,
    FuneralHomeAdmin,
    VendorAdmin,
    ProductAdmin,
    ProductImageAdmin,
    GiftCollectionAdmin,
    DefaultGiftCollectionAdmin,
    OrderAdmin,
    ProductVendorAdmin,
    GiftCollectionProductAdmin,
    DefaultGiftCollectionProductAdmin,
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
    authentication_backend = AdminAuthBackend(secret_key=settings.jwt_secret)
    
    admin = Admin(
        app=app,
        engine=engine,
        title="Zendora Admin",
        base_url="/admin",
        authentication_backend=authentication_backend,
    )
    
    admin.add_view(UserAdmin)
    admin.add_view(FuneralHomeAdmin)
    admin.add_view(VendorAdmin)
    admin.add_view(ProductAdmin)
    admin.add_view(GiftCollectionAdmin)
    admin.add_view(DefaultGiftCollectionAdmin)
    admin.add_view(OrderAdmin)
    
    admin.add_view(ProductImageAdmin)
    admin.add_view(ProductVendorAdmin)
    admin.add_view(GiftCollectionProductAdmin)
    admin.add_view(DefaultGiftCollectionProductAdmin)
    admin.add_view(OrderProductAdmin)
    
    return admin


__all__ = ["setup_admin"]
