# Import all models to ensure they're registered with Base
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.product import Product, ProductVendor
from app.models.wishlist import Wishlist, WishlistProduct, WishlistStatus
from app.models.wishlist_template import WishlistTemplate, WishlistTemplateProduct
from app.models.order import Order, OrderProduct, OrderStatus
from app.models.finance import (
    ManagerCommission,
    Wallet,
    WalletType,
    WalletTransaction,
    WalletTransactionType,
    OrderCommission,
)
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
    "WishlistTemplate",
    "WishlistTemplateProduct",
    "Order",
    "OrderProduct",
    "OrderStatus",
    "ManagerCommission",
    "Wallet",
    "WalletType",
    "WalletTransaction",
    "WalletTransactionType",
    "OrderCommission",
    "ManagerSettings",
    "WishlistSettings",
]
