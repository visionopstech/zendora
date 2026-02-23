"""SQLAdmin model views for all database models."""
from sqladmin import ModelView
from wtforms import SelectField, TextAreaField, validators
from wtforms.validators import ValidationError
import json

from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.product import Product, ProductVendor
from app.models.wishlist import Wishlist, WishlistProduct, WishlistStatus
from app.models.order import Order, OrderProduct, OrderStatus
from app.admin.formatters import (
    format_uuid, format_datetime, format_json, format_price,
    format_boolean, format_address, format_image_list
)


class UserAdmin(ModelView, model=User):
    """Admin view for User model."""
    
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    
    # List page configuration
    column_list = [
        User.id, User.email, User.full_name, User.role,
        User.is_active, User.manager_id, User.vendor_id, User.created_at
    ]
    column_searchable_list = [User.email, User.full_name]
    column_sortable_list = [User.email, User.role, User.is_active, User.created_at]
    column_default_sort = [(User.created_at, True)]  # Descending
    
    # Filters
    column_filters = [User.role, User.is_active, User.created_at]
    
    # Detail/Edit page configuration
    form_columns = [
        User.email, User.full_name, User.role,
        User.is_active, User.manager, User.vendor
    ]
    
    # Custom formatters
    column_formatters = {
        User.id: lambda m, a: format_uuid(m.id),
        User.is_active: lambda m, a: format_boolean(m.is_active),
        User.created_at: lambda m, a: format_datetime(m.created_at),
        User.manager_id: lambda m, a: format_uuid(m.manager_id) if m.manager_id else "",
        User.vendor_id: lambda m, a: format_uuid(m.vendor_id) if m.vendor_id else "",
    }
    
    # Form overrides for enum field
    form_overrides = {
        "role": SelectField,
    }
    
    form_args = {
        "role": {
            "choices": [(role.value, role.value) for role in UserRole],
            "validators": [validators.DataRequired()],
        },
        "email": {
            "validators": [validators.DataRequired(), validators.Email()],
        },
    }
    
    # Labels
    column_labels = {
        User.id: "ID",
        User.email: "Email",
        User.full_name: "Full Name",
        User.role: "Role",
        User.is_active: "Active",
        User.manager_id: "Manager ID",
        User.manager: "Manager",
        User.vendor_id: "Vendor ID",
        User.vendor: "Vendor",
        User.created_at: "Created At",
        User.updated_at: "Updated At",
    }
    
    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    can_export = True
    
    page_size = 50
    page_size_options = [25, 50, 100, 200]


class VendorAdmin(ModelView, model=Vendor):
    """Admin view for Vendor model."""
    
    name = "Vendor"
    name_plural = "Vendors"
    icon = "fa-solid fa-store"
    
    # List page configuration
    column_list = [
        Vendor.id, Vendor.name, Vendor.is_active, Vendor.created_at
    ]
    column_searchable_list = [Vendor.name, Vendor.description]
    column_sortable_list = [Vendor.name, Vendor.is_active, Vendor.created_at]
    column_default_sort = [(Vendor.name, False)]  # Ascending
    
    # Show relationships in detail view
    column_details_list = [
        Vendor.id, Vendor.name, Vendor.description, Vendor.logo_url,
        Vendor.is_active, Vendor.product_associations,
        Vendor.created_at, Vendor.updated_at
    ]
    
    # Filters
    column_filters = [Vendor.is_active, Vendor.created_at]
    
    # Detail/Edit page configuration
    form_columns = [
        Vendor.name, Vendor.description, Vendor.logo_url, Vendor.is_active
    ]
    
    # Custom formatters
    column_formatters = {
        Vendor.id: lambda m, a: format_uuid(m.id),
        Vendor.is_active: lambda m, a: format_boolean(m.is_active),
        Vendor.created_at: lambda m, a: format_datetime(m.created_at),
        Vendor.product_associations: lambda m, a: f"{len(m.product_associations)} product(s)" if m.product_associations else "No products",
    }
    
    form_overrides = {
        "description": TextAreaField,
    }
    
    form_args = {
        "name": {
            "validators": [validators.DataRequired(), validators.Length(max=255)],
        },
        "logo_url": {
            "label": "Logo URL",
            "description": "URL to vendor logo image",
        },
    }
    
    # Labels
    column_labels = {
        Vendor.id: "ID",
        Vendor.name: "Name",
        Vendor.description: "Description",
        Vendor.logo_url: "Logo URL",
        Vendor.is_active: "Active",
        Vendor.created_at: "Created At",
        Vendor.updated_at: "Updated At",
    }
    
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True
    
    page_size = 50
    page_size_options = [25, 50, 100, 200]


class ProductAdmin(ModelView, model=Product):
    """Admin view for Product model."""
    
    name = "Product"
    name_plural = "Products"
    icon = "fa-solid fa-box"
    
    # List page configuration
    column_list = [
        Product.id, Product.name, Product.price, Product.is_active, Product.created_at
    ]
    column_searchable_list = [Product.name, Product.description]
    column_sortable_list = [Product.name, Product.price, Product.is_active, Product.created_at]
    column_default_sort = [(Product.created_at, True)]  # Descending
    
    # Show relationships in detail view
    column_details_list = [
        Product.id, Product.name, Product.description, Product.price,
        Product.images, Product.is_active, Product.vendor_associations,
        Product.created_at, Product.updated_at
    ]
    
    # Filters
    column_filters = [Product.is_active, Product.price, Product.created_at]
    
    # Detail/Edit page configuration
    form_columns = [
        Product.name, Product.description, Product.price,
        Product.images, Product.is_active
    ]
    
    # Custom formatters
    column_formatters = {
        Product.id: lambda m, a: format_uuid(m.id),
        Product.price: lambda m, a: format_price(m.price),
        Product.is_active: lambda m, a: format_boolean(m.is_active),
        Product.created_at: lambda m, a: format_datetime(m.created_at),
        Product.vendor_associations: lambda m, a: f"{len(m.vendor_associations)} vendor(s)" if m.vendor_associations else "No vendors",
    }
    
    form_overrides = {
        "description": TextAreaField,
        "images": TextAreaField,
    }
    
    form_args = {
        "name": {
            "validators": [validators.DataRequired(), validators.Length(max=255)],
        },
        "price": {
            "validators": [validators.DataRequired()],
            "description": "Product price in USD",
        },
        "images": {
            "label": "Images (JSON array)",
            "description": 'JSON array of image URLs, e.g., ["url1", "url2"]',
        },
    }
    
    # Labels
    column_labels = {
        Product.id: "ID",
        Product.name: "Name",
        Product.description: "Description",
        Product.price: "Price",
        Product.images: "Images",
        Product.is_active: "Active",
        Product.created_at: "Created At",
        Product.updated_at: "Updated At",
    }
    
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True
    
    page_size = 50
    page_size_options = [25, 50, 100, 200]
    
    async def on_model_change(self, data, model, is_created, request):
        """Validate and process images JSON before saving."""
        if "images" in data and data["images"]:
            try:
                # If it's a string, try to parse as JSON
                if isinstance(data["images"], str):
                    images = json.loads(data["images"])
                    data["images"] = images
                # Validate it's a list
                if not isinstance(data.get("images"), list):
                    raise ValidationError("Images must be a JSON array")
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for images")


class WishlistAdmin(ModelView, model=Wishlist):
    """Admin view for Wishlist model."""
    
    name = "Wishlist"
    name_plural = "Wishlists"
    icon = "fa-solid fa-heart"
    
    # List page configuration
    column_list = [
        Wishlist.id, Wishlist.title, Wishlist.status,
        Wishlist.admin, Wishlist.manager, Wishlist.public_slug, Wishlist.created_at
    ]
    column_searchable_list = [Wishlist.title, Wishlist.public_slug, Wishlist.description]
    column_sortable_list = [Wishlist.title, Wishlist.status, Wishlist.created_at, Wishlist.published_at]
    column_default_sort = [(Wishlist.created_at, True)]  # Descending
    
    # Show relationships in detail view
    column_details_list = [
        Wishlist.id, Wishlist.admin, Wishlist.manager, Wishlist.public_slug,
        Wishlist.status, Wishlist.title, Wishlist.description,
        Wishlist.logo_url, Wishlist.header_image_url,
        Wishlist.primary_color, Wishlist.secondary_color,
        Wishlist.delivery_address, Wishlist.products,
        Wishlist.created_at, Wishlist.updated_at, Wishlist.published_at
    ]
    
    # Filters
    column_filters = [Wishlist.status, Wishlist.created_at, Wishlist.published_at]
    
    # Detail/Edit page configuration
    form_columns = [
        Wishlist.admin, Wishlist.manager, Wishlist.public_slug,
        Wishlist.status, Wishlist.title, Wishlist.description,
        Wishlist.logo_url, Wishlist.header_image_url,
        Wishlist.primary_color, Wishlist.secondary_color,
        Wishlist.delivery_address, Wishlist.published_at
    ]
    
    # Custom formatters
    column_formatters = {
        Wishlist.id: lambda m, a: format_uuid(m.id),
        Wishlist.admin: lambda m, a: f"{m.admin.full_name} ({m.admin.email})" if m.admin else "No admin",
        Wishlist.manager: lambda m, a: f"{m.manager.full_name} ({m.manager.email})" if m.manager else "No manager",
        Wishlist.created_at: lambda m, a: format_datetime(m.created_at),
        Wishlist.published_at: lambda m, a: format_datetime(m.published_at) if m.published_at else "",
        Wishlist.delivery_address: lambda m, a: format_address(m.delivery_address),
        Wishlist.products: lambda m, a: f"{len(m.products)} product(s)" if m.products else "No products",
    }
    
    form_overrides = {
        "status": SelectField,
        "description": TextAreaField,
        "delivery_address": TextAreaField,
    }
    
    form_args = {
        "status": {
            "choices": [(status.value, status.value) for status in WishlistStatus],
            "validators": [validators.DataRequired()],
        },
        "public_slug": {
            "validators": [validators.DataRequired(), validators.Length(max=255)],
            "description": "Unique public URL slug for this wishlist",
        },
        "title": {
            "validators": [validators.Length(max=255)],
        },
        "primary_color": {
            "label": "Primary Color (Hex)",
            "description": "Hex color code, e.g., #FF5733",
        },
        "secondary_color": {
            "label": "Secondary Color (Hex)",
            "description": "Hex color code, e.g., #33FF57",
        },
        "delivery_address": {
            "label": "Delivery Address (JSON)",
            "description": 'JSON object with address fields, e.g., {"street": "123 Main St", "city": "NYC", ...}',
        },
    }
    
    # Labels
    column_labels = {
        Wishlist.id: "ID",
        Wishlist.admin_id: "Admin ID",
        Wishlist.manager_id: "Manager ID",
        Wishlist.admin: "Admin User",
        Wishlist.manager: "Manager User",
        Wishlist.public_slug: "Public Slug",
        Wishlist.status: "Status",
        Wishlist.title: "Title",
        Wishlist.description: "Description",
        Wishlist.logo_url: "Logo URL",
        Wishlist.header_image_url: "Header Image URL",
        Wishlist.primary_color: "Primary Color",
        Wishlist.secondary_color: "Secondary Color",
        Wishlist.delivery_address: "Delivery Address",
        Wishlist.created_at: "Created At",
        Wishlist.updated_at: "Updated At",
        Wishlist.published_at: "Published At",
    }
    
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True
    
    page_size = 50
    page_size_options = [25, 50, 100, 200]
    
    async def on_model_change(self, data, model, is_created, request):
        """Validate and process delivery_address JSON before saving."""
        if "delivery_address" in data and data["delivery_address"]:
            try:
                # If it's a string, try to parse as JSON
                if isinstance(data["delivery_address"], str):
                    address = json.loads(data["delivery_address"])
                    data["delivery_address"] = address
                # Validate it's a dict
                if not isinstance(data.get("delivery_address"), dict):
                    raise ValidationError("Delivery address must be a JSON object")
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for delivery address")


class OrderAdmin(ModelView, model=Order):
    """Admin view for Order model."""
    
    name = "Order"
    name_plural = "Orders"
    icon = "fa-solid fa-shopping-cart"
    
    # List page configuration
    column_list = [
        Order.id, Order.visitor, Order.wishlist,
        Order.status, Order.total_amount, Order.currency,
        Order.created_at, Order.paid_at
    ]
    column_searchable_list = [Order.stripe_session_id]
    column_sortable_list = [Order.status, Order.total_amount, Order.created_at, Order.paid_at]
    column_default_sort = [(Order.created_at, True)]  # Descending
    
    # Show relationships in detail view
    column_details_list = [
        Order.id, Order.visitor, Order.wishlist, Order.admin,
        Order.stripe_session_id, Order.status, Order.total_amount,
        Order.currency, Order.products,
        Order.created_at, Order.paid_at, Order.updated_at
    ]
    
    # Filters
    column_filters = [Order.status, Order.currency, Order.created_at, Order.paid_at]
    
    # Detail/Edit page configuration
    form_columns = [
        Order.visitor, Order.wishlist, Order.admin,
        Order.stripe_session_id, Order.status, Order.total_amount,
        Order.currency, Order.paid_at
    ]
    
    # Custom formatters
    column_formatters = {
        Order.id: lambda m, a: format_uuid(m.id),
        Order.visitor: lambda m, a: f"{m.visitor.full_name} ({m.visitor.email})" if m.visitor else "No visitor",
        Order.wishlist: lambda m, a: m.wishlist.title if m.wishlist else "No wishlist",
        Order.total_amount: lambda m, a: format_price(m.total_amount),
        Order.created_at: lambda m, a: format_datetime(m.created_at),
        Order.paid_at: lambda m, a: format_datetime(m.paid_at) if m.paid_at else "",
        Order.products: lambda m, a: f"{len(m.products)} item(s)" if m.products else "No items",
    }
    
    form_overrides = {
        "status": SelectField,
    }
    
    form_args = {
        "status": {
            "choices": [(status.value, status.value) for status in OrderStatus],
            "validators": [validators.DataRequired()],
        },
        "stripe_session_id": {
            "label": "Stripe Session ID",
            "validators": [validators.DataRequired()],
            "description": "Stripe checkout session ID",
        },
        "total_amount": {
            "validators": [validators.DataRequired()],
            "description": "Total order amount",
        },
        "currency": {
            "validators": [validators.Length(max=3)],
            "description": "Currency code (e.g., USD)",
        },
    }
    
    # Labels
    column_labels = {
        Order.id: "ID",
        Order.visitor_id: "Visitor ID",
        Order.wishlist_id: "Wishlist ID",
        Order.admin_id: "Admin ID",
        Order.visitor: "Visitor User",
        Order.wishlist: "Wishlist",
        Order.admin: "Admin User",
        Order.stripe_session_id: "Stripe Session ID",
        Order.status: "Status",
        Order.total_amount: "Total Amount",
        Order.currency: "Currency",
        Order.created_at: "Created At",
        Order.paid_at: "Paid At",
        Order.updated_at: "Updated At",
    }
    
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True
    
    page_size = 50
    page_size_options = [25, 50, 100, 200]


class ProductVendorAdmin(ModelView, model=ProductVendor):
    """Admin view for Product-Vendor associations."""
    
    name = "Product-Vendor"
    name_plural = "Product-Vendor Associations"
    icon = "fa-solid fa-link"
    category = "Associations"
    
    # List page configuration
    column_list = [
        ProductVendor.product, ProductVendor.vendor, ProductVendor.created_at
    ]
    
    # Custom formatters
    column_formatters = {
        ProductVendor.product: lambda m, a: m.product.name if m.product else "Unknown",
        ProductVendor.vendor: lambda m, a: m.vendor.name if m.vendor else "Unknown",
    }
    
    # Detail/Edit page configuration
    form_columns = [
        ProductVendor.product, ProductVendor.vendor
    ]
    
    # Custom formatters
    column_formatters = {
        ProductVendor.product_id: lambda m, a: format_uuid(m.product_id),
        ProductVendor.vendor_id: lambda m, a: format_uuid(m.vendor_id),
        ProductVendor.created_at: lambda m, a: format_datetime(m.created_at),
    }
    
    # Labels
    column_labels = {
        ProductVendor.product_id: "Product ID",
        ProductVendor.vendor_id: "Vendor ID",
        ProductVendor.product: "Product",
        ProductVendor.vendor: "Vendor",
        ProductVendor.created_at: "Created At",
    }
    
    can_create = False
    can_edit = False  # Can't edit composite primary key
    can_delete = False
    can_view_details = True
    can_export = True
    
    page_size = 50
    page_size_options = [25, 50, 100, 200]


class WishlistProductAdmin(ModelView, model=WishlistProduct):
    """Admin view for Wishlist-Product associations."""
    
    name = "Wishlist-Product"
    name_plural = "Wishlist-Product Associations"
    icon = "fa-solid fa-link"
    category = "Associations"
    
    # List page configuration
    column_list = [
        WishlistProduct.wishlist, WishlistProduct.product,
        WishlistProduct.quantity, WishlistProduct.created_at
    ]
    
    # Custom formatters
    column_formatters = {
        WishlistProduct.wishlist: lambda m, a: m.wishlist.title if m.wishlist else "Unknown",
        WishlistProduct.product: lambda m, a: m.product.name if m.product else "Unknown",
    }
    
    # Detail/Edit page configuration
    form_columns = [
        WishlistProduct.wishlist, WishlistProduct.product, WishlistProduct.quantity
    ]
    
    # Custom formatters
    column_formatters = {
        WishlistProduct.wishlist_id: lambda m, a: format_uuid(m.wishlist_id),
        WishlistProduct.product_id: lambda m, a: format_uuid(m.product_id),
        WishlistProduct.created_at: lambda m, a: format_datetime(m.created_at),
    }
    
    form_args = {
        "quantity": {
            "validators": [validators.DataRequired()],
            "description": "Quantity of this product in the wishlist",
        }
    }
    
    # Labels
    column_labels = {
        WishlistProduct.wishlist_id: "Wishlist ID",
        WishlistProduct.product_id: "Product ID",
        WishlistProduct.wishlist: "Wishlist",
        WishlistProduct.product: "Product",
        WishlistProduct.quantity: "Quantity",
        WishlistProduct.created_at: "Created At",
    }
    
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True
    
    page_size = 50
    page_size_options = [25, 50, 100, 200]


class OrderProductAdmin(ModelView, model=OrderProduct):
    """Admin view for Order-Product associations."""
    
    name = "Order-Product"
    name_plural = "Order-Product Items"
    icon = "fa-solid fa-shopping-bag"
    category = "Associations"
    
    # List page configuration
    column_list = [
        OrderProduct.order, OrderProduct.product,
        OrderProduct.product_name, OrderProduct.product_price,
        OrderProduct.quantity, OrderProduct.created_at
    ]
    
    # Custom formatters
    column_formatters = {
        OrderProduct.order: lambda m, a: f"Order {str(m.order_id)[:8]}..." if m.order else "Unknown",
        OrderProduct.product: lambda m, a: m.product.name if m.product else m.product_name,
        OrderProduct.product_price: lambda m, a: format_price(m, a, attr_name="product_price"),
    }
    
    # Detail/Edit page configuration
    form_columns = [
        OrderProduct.order, OrderProduct.product,
        OrderProduct.product_name, OrderProduct.product_price,
        OrderProduct.quantity
    ]
    
    # Custom formatters
    column_formatters = {
        OrderProduct.order_id: lambda m, a: format_uuid(m.order_id),
        OrderProduct.product_id: lambda m, a: format_uuid(m.product_id),
        OrderProduct.product_price: lambda m, a: format_price(m.product_price),
        OrderProduct.created_at: lambda m, a: format_datetime(m.created_at),
    }
    
    form_args = {
        "product_name": {
            "validators": [validators.DataRequired()],
            "description": "Product name snapshot",
        },
        "product_price": {
            "validators": [validators.DataRequired()],
            "description": "Product price snapshot",
        },
        "quantity": {
            "validators": [validators.DataRequired()],
            "description": "Quantity ordered",
        }
    }
    
    # Labels
    column_labels = {
        OrderProduct.order_id: "Order ID",
        OrderProduct.product_id: "Product ID",
        OrderProduct.order: "Order",
        OrderProduct.product: "Product",
        OrderProduct.product_name: "Product Name (Snapshot)",
        OrderProduct.product_price: "Product Price (Snapshot)",
        OrderProduct.quantity: "Quantity",
        OrderProduct.created_at: "Created At",
    }
    
    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True
    
    page_size = 50
    page_size_options = [25, 50, 100, 200]
