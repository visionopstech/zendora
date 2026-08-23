# Import all models to ensure they're registered with Base
from app.models.user import User, UserRole
from app.models.funeral_home import FuneralHome
from app.models.vendor import Vendor
from app.models.product import Product, ProductImage, ProductVendor
from app.models.gift_collection import (
    GiftCollection,
    GiftCollectionProduct,
    GiftCollectionStatus,
)
from app.models.default_gift_collection import (
    DefaultCollectionScope,
    DefaultGiftCollection,
    DefaultGiftCollectionProduct,
)
from app.models.order import Order, OrderProduct, OrderStatus
from app.models.finance import (
    DirectorCommission,
    Wallet,
    WalletType,
    WalletTransaction,
    WalletTransactionType,
    OrderCommission,
)
from app.models.director_settings import DirectorSettings
from app.models.gift_collection_settings import GiftCollectionSettings

__all__ = [
    "User",
    "UserRole",
    "FuneralHome",
    "Vendor",
    "Product",
    "ProductImage",
    "ProductVendor",
    "GiftCollection",
    "GiftCollectionProduct",
    "GiftCollectionStatus",
    "DefaultCollectionScope",
    "DefaultGiftCollection",
    "DefaultGiftCollectionProduct",
    "Order",
    "OrderProduct",
    "OrderStatus",
    "DirectorCommission",
    "Wallet",
    "WalletType",
    "WalletTransaction",
    "WalletTransactionType",
    "OrderCommission",
    "DirectorSettings",
    "GiftCollectionSettings",
]
