"""Build Jinja2 context dicts for transactional emails."""

from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from app.core.config import settings
from app.models.gift_collection import GiftCollection
from app.models.order import Order, OrderProduct
from app.models.user import User
from app.models.vendor import Vendor


def money(value) -> str:
    if value is None:
        return "0.00"
    return f"{Decimal(str(value)):.2f}"


def format_address(address: Optional[dict]) -> str:
    if not address:
        return ""
    parts = [
        address.get("street"),
        address.get("city"),
        address.get("state"),
        address.get("zip_code"),
        address.get("country"),
    ]
    line = ", ".join(part for part in parts if part)
    extra = address.get("additional_info")
    if extra:
        return f"{line} ({extra})" if line else extra
    return line


def user_name(user: Optional[User]) -> str:
    if not user:
        return ""
    display = getattr(user, "display_name", None)
    if callable(display):
        display = display()
    if display:
        return display
    joined = " ".join(
        part for part in (getattr(user, "first_name", None), getattr(user, "last_name", None)) if part
    ).strip()
    return joined or getattr(user, "email", "") or ""


def deceased_name(user: Optional[User]) -> str:
    if not user:
        return ""
    return " ".join(
        part for part in (user.deceased_first_name, user.deceased_last_name) if part
    ).strip()


def collection_link(collection: Optional[GiftCollection]) -> str:
    if not collection or not collection.public_slug:
        return ""
    return f"{settings.frontend_url}/w/{collection.public_slug}"


def serialize_product(order_product: OrderProduct) -> dict[str, Any]:
    line_total = order_product.product_price * order_product.quantity
    return {
        "name": order_product.product_name,
        "quantity": order_product.quantity,
        "price": money(order_product.product_price),
        "total": money(line_total),
    }


def serialize_user(user: Optional[User]) -> dict[str, str]:
    if not user:
        return {"name": "", "email": "", "deceased_name": "", "address": ""}
    return {
        "name": user_name(user),
        "email": user.email or "",
        "deceased_name": deceased_name(user),
        "address": format_address(user.address),
    }


def serialize_collection(collection: Optional[GiftCollection]) -> dict[str, str]:
    if not collection:
        return {"name": "", "link": "", "description": ""}
    return {
        "name": collection.title or "Gift Collection",
        "link": collection_link(collection),
        "description": collection.description or "",
    }


def serialize_delivery(collection: Optional[GiftCollection]) -> dict[str, Any]:
    address = collection.delivery_address if collection else None
    raw = address or {}
    return {
        "formatted": format_address(address),
        "street": raw.get("street", ""),
        "city": raw.get("city", ""),
        "state": raw.get("state", ""),
        "zip_code": raw.get("zip_code", ""),
        "country": raw.get("country", ""),
        "additional_info": raw.get("additional_info", ""),
    }


def serialize_funeral_home(funeral_home) -> dict[str, str]:
    if not funeral_home:
        return {"name": "", "email": "", "phone": "", "address": ""}
    return {
        "name": funeral_home.name or "",
        "email": funeral_home.email or "",
        "phone": funeral_home.phone or "",
        "address": format_address(funeral_home.address),
    }


def product_list(order_products: list[OrderProduct]) -> list[dict[str, Any]]:
    return [serialize_product(item) for item in order_products]


def product_count(order_products: list[OrderProduct]) -> int:
    return sum(item.quantity for item in order_products)


def products_total(order_products: list[OrderProduct]) -> Decimal:
    return sum(
        (item.product_price * item.quantity for item in order_products),
        Decimal("0"),
    )


def group_order_products_by_vendor(
    order: Order,
) -> dict[UUID, tuple[Vendor, list[OrderProduct]]]:
    grouped: dict[UUID, tuple[Vendor, list[OrderProduct]]] = {}
    for order_product in order.products or []:
        product = getattr(order_product, "product", None)
        associations = getattr(product, "vendor_associations", None) if product else None
        if not associations:
            continue
        for association in associations:
            vendor = association.vendor
            if not vendor:
                continue
            if vendor.id not in grouped:
                grouped[vendor.id] = (vendor, [])
            grouped[vendor.id][1].append(order_product)
    return grouped


def active_vendor_users(vendor: Vendor) -> list[User]:
    return [user for user in (vendor.vendor_users or []) if user.is_active and user.email]


def order_base_context(order: Order) -> dict[str, Any]:
    collection = order.gift_collection
    family = order.family_admin
    buyer = order.visitor
    products = list(order.products or [])
    return {
        "order": {
            "id": str(order.id),
            "total_amount": money(order.total_amount),
            "currency": order.currency or "USD",
            "paid_at": order.paid_at.strftime("%Y-%m-%d %H:%M:%S") if order.paid_at else "",
        },
        "products": product_list(products),
        "buyer": serialize_user(buyer),
        "family": serialize_user(family),
        "collection": serialize_collection(collection),
        "delivery": serialize_delivery(collection),
    }


def vendor_order_context(
    order: Order,
    vendor: Vendor,
    vendor_products: list[OrderProduct],
) -> dict[str, Any]:
    context = order_base_context(order)
    context["products"] = product_list(vendor_products)
    context["product_count"] = product_count(vendor_products)
    context["price"] = money(products_total(vendor_products))
    context["vendor"] = {"name": vendor.name or ""}
    return context


def family_admin_order_context(order: Order) -> dict[str, Any]:
    return order_base_context(order)


def buyer_order_context(order: Order) -> dict[str, Any]:
    context = order_base_context(order)
    context["price_paid"] = money(order.total_amount)
    return context


def super_admin_order_context(order: Order) -> dict[str, Any]:
    context = order_base_context(order)
    vendors = []
    seen: set[UUID] = set()
    for vendor, _products in group_order_products_by_vendor(order).values():
        if vendor.id not in seen:
            seen.add(vendor.id)
            vendors.append({"name": vendor.name or ""})
    context["vendors"] = vendors
    return context


def collection_created_context(collection: GiftCollection) -> dict[str, Any]:
    return {
        "collection": serialize_collection(collection),
        "family_admin": serialize_user(collection.family_admin),
        "director": serialize_user(collection.director),
        "funeral_home": serialize_funeral_home(collection.funeral_home),
    }
