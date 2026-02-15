# Import all models to ensure they're registered with Base
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.product import Product, ProductVendor
from app.models.wishlist import Wishlist, WishlistProduct, WishlistStatus
from app.models.order import Order, OrderProduct, OrderStatus
from app.models.manager_settings import ManagerSettings
from app.models.wishlist_settings import WishlistSettings

__all__ = [
    "User",
    "UserRole",
    "Vendor",
    "Product",
    "ProductVendor",
    "Wishlist",
    "WishlistProduct",
    "WishlistStatus",
    "Order",
    "OrderProduct",
    "OrderStatus",
    "ManagerSettings",
    "WishlistSettings",
]
