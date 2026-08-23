"""SQLAdmin model views for all database models."""
from sqladmin import ModelView
from wtforms import SelectField, TextAreaField, validators
from wtforms.validators import ValidationError
import json

from app.models.user import User, UserRole
from app.models.funeral_home import FuneralHome
from app.models.vendor import Vendor
from app.models.product import Product, ProductImage, ProductVendor
from app.models.gift_collection import GiftCollection, GiftCollectionProduct, GiftCollectionStatus
from app.models.default_gift_collection import (
    DefaultCollectionScope,
    DefaultGiftCollection,
    DefaultGiftCollectionProduct,
)
from app.models.order import Order, OrderProduct, OrderStatus
from app.admin.formatters import (
    format_uuid, format_datetime, format_price,
    format_boolean, format_address,
)


class UserAdmin(ModelView, model=User):
    """Admin view for User model."""

    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"

    column_list = [
        User.id, User.email, User.full_name, User.role,
        User.is_active, User.director_id, User.funeral_home_id, User.vendor_id, User.created_at
    ]
    column_searchable_list = [User.email, User.full_name]
    column_sortable_list = [User.email, User.role, User.is_active, User.created_at]
    column_default_sort = [(User.created_at, True)]

    column_filters = [User.role, User.is_active, User.created_at]

    form_columns = [
        User.email, User.full_name, User.role,
        User.is_active, User.director, User.funeral_home, User.vendor
    ]

    column_formatters = {
        User.id: lambda m, a: format_uuid(m.id),
        User.is_active: lambda m, a: format_boolean(m.is_active),
        User.created_at: lambda m, a: format_datetime(m.created_at),
        User.director_id: lambda m, a: format_uuid(m.director_id) if m.director_id else "",
        User.funeral_home_id: lambda m, a: format_uuid(m.funeral_home_id) if m.funeral_home_id else "",
        User.vendor_id: lambda m, a: format_uuid(m.vendor_id) if m.vendor_id else "",
    }

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

    column_labels = {
        User.id: "ID",
        User.email: "Email",
        User.full_name: "Full Name",
        User.role: "Role",
        User.is_active: "Active",
        User.director_id: "Director ID",
        User.director: "Director",
        User.funeral_home_id: "Funeral Home ID",
        User.funeral_home: "Funeral Home",
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


class FuneralHomeAdmin(ModelView, model=FuneralHome):
    """Admin view for FuneralHome model."""

    name = "Funeral Home"
    name_plural = "Funeral Homes"
    icon = "fa-solid fa-building"

    column_list = [
        FuneralHome.id, FuneralHome.name, FuneralHome.email,
        FuneralHome.director_id, FuneralHome.is_active, FuneralHome.created_at
    ]
    column_searchable_list = [FuneralHome.name, FuneralHome.email, FuneralHome.description]
    column_sortable_list = [FuneralHome.name, FuneralHome.is_active, FuneralHome.created_at]
    column_default_sort = [(FuneralHome.name, False)]

    column_filters = [FuneralHome.is_active, FuneralHome.created_at]

    form_columns = [
        FuneralHome.name, FuneralHome.description, FuneralHome.email,
        FuneralHome.phone, FuneralHome.address, FuneralHome.logo_url,
        FuneralHome.director, FuneralHome.is_active
    ]

    column_formatters = {
        FuneralHome.id: lambda m, a: format_uuid(m.id),
        FuneralHome.is_active: lambda m, a: format_boolean(m.is_active),
        FuneralHome.created_at: lambda m, a: format_datetime(m.created_at),
        FuneralHome.director_id: lambda m, a: format_uuid(m.director_id) if m.director_id else "",
        FuneralHome.address: lambda m, a: format_address(m.address),
    }

    form_overrides = {
        "description": TextAreaField,
        "address": TextAreaField,
    }

    form_args = {
        "name": {
            "validators": [validators.DataRequired(), validators.Length(max=255)],
        },
        "address": {
            "label": "Address (JSON)",
            "description": 'JSON object, e.g., {"street": "123 Main St", "city": "NYC", ...}',
        },
    }

    column_labels = {
        FuneralHome.id: "ID",
        FuneralHome.name: "Name",
        FuneralHome.description: "Description",
        FuneralHome.email: "Email",
        FuneralHome.phone: "Phone",
        FuneralHome.address: "Address",
        FuneralHome.logo_url: "Logo URL",
        FuneralHome.director_id: "Director ID",
        FuneralHome.director: "Director",
        FuneralHome.is_active: "Active",
        FuneralHome.created_at: "Created At",
        FuneralHome.updated_at: "Updated At",
    }

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = True
    can_export = True

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    async def on_model_change(self, data, model, is_created, request):
        """Validate address JSON before saving."""
        if "address" in data and data["address"]:
            try:
                if isinstance(data["address"], str):
                    data["address"] = json.loads(data["address"])
                if not isinstance(data.get("address"), dict):
                    raise ValidationError("Address must be a JSON object")
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for address")


class VendorAdmin(ModelView, model=Vendor):
    """Admin view for Vendor model."""

    name = "Vendor"
    name_plural = "Vendors"
    icon = "fa-solid fa-store"

    column_list = [
        Vendor.id, Vendor.name, Vendor.is_active, Vendor.created_at
    ]
    column_searchable_list = [Vendor.name, Vendor.description]
    column_sortable_list = [Vendor.name, Vendor.is_active, Vendor.created_at]
    column_default_sort = [(Vendor.name, False)]

    column_details_list = [
        Vendor.id, Vendor.name, Vendor.description, Vendor.logo_url,
        Vendor.is_active, Vendor.product_associations,
        Vendor.created_at, Vendor.updated_at
    ]

    column_filters = [Vendor.is_active, Vendor.created_at]

    form_columns = [
        Vendor.name, Vendor.description, Vendor.logo_url, Vendor.is_active
    ]

    column_formatters = {
        Vendor.id: lambda m, a: format_uuid(m.id),
        Vendor.is_active: lambda m, a: format_boolean(m.is_active),
        Vendor.created_at: lambda m, a: format_datetime(m.created_at),
        Vendor.product_associations: lambda m, a: f"{len(m.product_associations)} gift(s)" if m.product_associations else "No gifts",
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
    """Admin view for Product (gift) model."""

    name = "Gift"
    name_plural = "Gifts"
    icon = "fa-solid fa-gift"

    column_list = [
        Product.id, Product.name, Product.base_price, Product.price,
        Product.is_active, Product.created_at
    ]
    column_searchable_list = [Product.name, Product.description]
    column_sortable_list = [Product.name, Product.price, Product.is_active, Product.created_at]
    column_default_sort = [(Product.created_at, True)]

    column_details_list = [
        Product.id, Product.name, Product.description, Product.base_price, Product.price,
        Product.images, Product.is_active, Product.vendor_associations,
        Product.created_at, Product.updated_at
    ]

    column_filters = [Product.is_active, Product.price, Product.created_at]

    form_columns = [
        Product.name, Product.description, Product.base_price, Product.price, Product.is_active
    ]

    column_formatters = {
        Product.id: lambda m, a: format_uuid(m.id),
        Product.base_price: lambda m, a: format_price(m.base_price),
        Product.price: lambda m, a: format_price(m.price),
        Product.is_active: lambda m, a: format_boolean(m.is_active),
        Product.created_at: lambda m, a: format_datetime(m.created_at),
        Product.images: lambda m, a: f"{len(m.images)} image(s)" if m.images else "No images",
        Product.vendor_associations: lambda m, a: f"{len(m.vendor_associations)} vendor(s)" if m.vendor_associations else "No vendors",
    }

    form_overrides = {
        "description": TextAreaField,
    }

    form_args = {
        "name": {
            "validators": [validators.DataRequired(), validators.Length(max=255)],
        },
        "price": {
            "validators": [validators.DataRequired()],
            "description": "Retail price in USD",
        },
    }

    column_labels = {
        Product.id: "ID",
        Product.name: "Name",
        Product.description: "Description",
        Product.base_price: "Base Price",
        Product.price: "Retail Price",
        Product.images: "Gallery",
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


class ProductImageAdmin(ModelView, model=ProductImage):
    """Admin view for gift gallery images."""

    name = "Gift Image"
    name_plural = "Gift Images"
    icon = "fa-solid fa-image"
    category = "Associations"

    column_list = [
        ProductImage.id, ProductImage.product_id, ProductImage.url,
        ProductImage.is_primary, ProductImage.sort_order, ProductImage.created_at
    ]
    column_sortable_list = [ProductImage.sort_order, ProductImage.created_at, ProductImage.is_primary]
    column_default_sort = [(ProductImage.created_at, True)]

    column_formatters = {
        ProductImage.id: lambda m, a: format_uuid(m.id),
        ProductImage.product_id: lambda m, a: format_uuid(m.product_id),
        ProductImage.is_primary: lambda m, a: format_boolean(m.is_primary),
        ProductImage.created_at: lambda m, a: format_datetime(m.created_at),
    }

    column_labels = {
        ProductImage.id: "ID",
        ProductImage.product_id: "Gift ID",
        ProductImage.url: "URL",
        ProductImage.alt_text: "Alt Text",
        ProductImage.is_primary: "Primary",
        ProductImage.sort_order: "Sort Order",
        ProductImage.created_at: "Created At",
    }

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True

    page_size = 50
    page_size_options = [25, 50, 100, 200]


class GiftCollectionAdmin(ModelView, model=GiftCollection):
    """Admin view for GiftCollection model."""

    name = "Gift Collection"
    name_plural = "Gift Collections"
    icon = "fa-solid fa-heart"

    column_list = [
        GiftCollection.id, GiftCollection.title, GiftCollection.status,
        GiftCollection.family_admin, GiftCollection.director,
        GiftCollection.public_slug, GiftCollection.created_at
    ]
    column_searchable_list = [GiftCollection.title, GiftCollection.public_slug, GiftCollection.description]
    column_sortable_list = [GiftCollection.title, GiftCollection.status, GiftCollection.created_at, GiftCollection.published_at]
    column_default_sort = [(GiftCollection.created_at, True)]

    column_details_list = [
        GiftCollection.id, GiftCollection.family_admin, GiftCollection.director,
        GiftCollection.funeral_home, GiftCollection.public_slug,
        GiftCollection.status, GiftCollection.title, GiftCollection.description,
        GiftCollection.logo_url, GiftCollection.header_image_url,
        GiftCollection.primary_color, GiftCollection.secondary_color,
        GiftCollection.delivery_address, GiftCollection.products,
        GiftCollection.created_at, GiftCollection.updated_at, GiftCollection.published_at
    ]

    column_filters = [GiftCollection.status, GiftCollection.created_at, GiftCollection.published_at]

    form_columns = [
        GiftCollection.family_admin, GiftCollection.director, GiftCollection.funeral_home,
        GiftCollection.public_slug, GiftCollection.status, GiftCollection.title,
        GiftCollection.description, GiftCollection.logo_url, GiftCollection.header_image_url,
        GiftCollection.primary_color, GiftCollection.secondary_color,
        GiftCollection.delivery_address, GiftCollection.published_at
    ]

    column_formatters = {
        GiftCollection.id: lambda m, a: format_uuid(m.id),
        GiftCollection.family_admin: lambda m, a: f"{m.family_admin.full_name} ({m.family_admin.email})" if m.family_admin else "No family admin",
        GiftCollection.director: lambda m, a: f"{m.director.full_name} ({m.director.email})" if m.director else "No director",
        GiftCollection.created_at: lambda m, a: format_datetime(m.created_at),
        GiftCollection.published_at: lambda m, a: format_datetime(m.published_at) if m.published_at else "",
        GiftCollection.delivery_address: lambda m, a: format_address(m.delivery_address),
        GiftCollection.products: lambda m, a: f"{len(m.products)} gift(s)" if m.products else "No gifts",
    }

    form_overrides = {
        "status": SelectField,
        "description": TextAreaField,
        "delivery_address": TextAreaField,
    }

    form_args = {
        "status": {
            "choices": [(status.value, status.value) for status in GiftCollectionStatus],
            "validators": [validators.DataRequired()],
        },
        "public_slug": {
            "validators": [validators.DataRequired(), validators.Length(max=255)],
            "description": "Unique public URL slug for this gift collection",
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

    column_labels = {
        GiftCollection.id: "ID",
        GiftCollection.family_admin_id: "Family Admin ID",
        GiftCollection.director_id: "Director ID",
        GiftCollection.family_admin: "Family Admin",
        GiftCollection.director: "Director",
        GiftCollection.funeral_home: "Funeral Home",
        GiftCollection.public_slug: "Public Slug",
        GiftCollection.status: "Status",
        GiftCollection.title: "Title",
        GiftCollection.description: "Description",
        GiftCollection.logo_url: "Logo URL",
        GiftCollection.header_image_url: "Header Image URL",
        GiftCollection.primary_color: "Primary Color",
        GiftCollection.secondary_color: "Secondary Color",
        GiftCollection.delivery_address: "Delivery Address",
        GiftCollection.created_at: "Created At",
        GiftCollection.updated_at: "Updated At",
        GiftCollection.published_at: "Published At",
    }

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    async def on_model_change(self, data, model, is_created, request):
        """Validate delivery_address JSON before saving."""
        if "delivery_address" in data and data["delivery_address"]:
            try:
                if isinstance(data["delivery_address"], str):
                    data["delivery_address"] = json.loads(data["delivery_address"])
                if not isinstance(data.get("delivery_address"), dict):
                    raise ValidationError("Delivery address must be a JSON object")
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for delivery address")


class DefaultGiftCollectionAdmin(ModelView, model=DefaultGiftCollection):
    """Admin view for default gift collections."""

    name = "Default Gift Collection"
    name_plural = "Default Gift Collections"
    icon = "fa-solid fa-copy"

    column_list = [
        DefaultGiftCollection.id, DefaultGiftCollection.name,
        DefaultGiftCollection.owner_scope, DefaultGiftCollection.funeral_home_id,
        DefaultGiftCollection.is_active, DefaultGiftCollection.created_at
    ]
    column_searchable_list = [DefaultGiftCollection.name, DefaultGiftCollection.description]
    column_sortable_list = [DefaultGiftCollection.name, DefaultGiftCollection.owner_scope, DefaultGiftCollection.created_at]
    column_default_sort = [(DefaultGiftCollection.created_at, True)]

    column_filters = [DefaultGiftCollection.owner_scope, DefaultGiftCollection.is_active]

    form_columns = [
        DefaultGiftCollection.name, DefaultGiftCollection.description,
        DefaultGiftCollection.owner_scope, DefaultGiftCollection.funeral_home,
        DefaultGiftCollection.collection_title, DefaultGiftCollection.collection_description,
        DefaultGiftCollection.logo_url, DefaultGiftCollection.header_image_url,
        DefaultGiftCollection.primary_color, DefaultGiftCollection.secondary_color,
        DefaultGiftCollection.delivery_address, DefaultGiftCollection.is_active
    ]

    column_formatters = {
        DefaultGiftCollection.id: lambda m, a: format_uuid(m.id),
        DefaultGiftCollection.is_active: lambda m, a: format_boolean(m.is_active),
        DefaultGiftCollection.created_at: lambda m, a: format_datetime(m.created_at),
        DefaultGiftCollection.funeral_home_id: lambda m, a: format_uuid(m.funeral_home_id) if m.funeral_home_id else "",
    }

    form_overrides = {
        "owner_scope": SelectField,
        "description": TextAreaField,
        "collection_description": TextAreaField,
        "delivery_address": TextAreaField,
    }

    form_args = {
        "owner_scope": {
            "choices": [(scope.value, scope.value) for scope in DefaultCollectionScope],
            "validators": [validators.DataRequired()],
        },
        "name": {
            "validators": [validators.DataRequired(), validators.Length(max=255)],
        },
    }

    column_labels = {
        DefaultGiftCollection.id: "ID",
        DefaultGiftCollection.name: "Name",
        DefaultGiftCollection.description: "Description",
        DefaultGiftCollection.owner_scope: "Owner Scope",
        DefaultGiftCollection.funeral_home_id: "Funeral Home ID",
        DefaultGiftCollection.funeral_home: "Funeral Home",
        DefaultGiftCollection.collection_title: "Collection Title",
        DefaultGiftCollection.collection_description: "Collection Description",
        DefaultGiftCollection.is_active: "Active",
        DefaultGiftCollection.created_at: "Created At",
    }

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True

    page_size = 50
    page_size_options = [25, 50, 100, 200]


class OrderAdmin(ModelView, model=Order):
    """Admin view for Order model."""

    name = "Order"
    name_plural = "Orders"
    icon = "fa-solid fa-shopping-cart"

    column_list = [
        Order.id, Order.visitor, Order.gift_collection,
        Order.status, Order.total_amount, Order.currency,
        Order.created_at, Order.paid_at
    ]
    column_searchable_list = [Order.stripe_session_id]
    column_sortable_list = [Order.status, Order.total_amount, Order.created_at, Order.paid_at]
    column_default_sort = [(Order.created_at, True)]

    column_details_list = [
        Order.id, Order.visitor, Order.gift_collection, Order.family_admin,
        Order.funeral_home, Order.stripe_session_id, Order.status, Order.total_amount,
        Order.currency, Order.products,
        Order.created_at, Order.paid_at, Order.updated_at
    ]

    column_filters = [Order.status, Order.currency, Order.created_at, Order.paid_at]

    form_columns = [
        Order.visitor, Order.gift_collection, Order.family_admin,
        Order.funeral_home, Order.stripe_session_id, Order.status, Order.total_amount,
        Order.currency, Order.paid_at
    ]

    column_formatters = {
        Order.id: lambda m, a: format_uuid(m.id),
        Order.visitor: lambda m, a: f"{m.visitor.full_name} ({m.visitor.email})" if m.visitor else "No visitor",
        Order.gift_collection: lambda m, a: m.gift_collection.title if m.gift_collection else "No collection",
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

    column_labels = {
        Order.id: "ID",
        Order.visitor_id: "Visitor ID",
        Order.gift_collection_id: "Gift Collection ID",
        Order.family_admin_id: "Family Admin ID",
        Order.visitor: "Visitor User",
        Order.gift_collection: "Gift Collection",
        Order.family_admin: "Family Admin",
        Order.funeral_home: "Funeral Home",
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

    name = "Gift-Vendor"
    name_plural = "Gift-Vendor Associations"
    icon = "fa-solid fa-link"
    category = "Associations"

    column_list = [
        ProductVendor.product, ProductVendor.vendor, ProductVendor.created_at
    ]

    column_formatters = {
        ProductVendor.product: lambda m, a: m.product.name if m.product else "Unknown",
        ProductVendor.vendor: lambda m, a: m.vendor.name if m.vendor else "Unknown",
        ProductVendor.product_id: lambda m, a: format_uuid(m.product_id),
        ProductVendor.vendor_id: lambda m, a: format_uuid(m.vendor_id),
        ProductVendor.created_at: lambda m, a: format_datetime(m.created_at),
    }

    form_columns = [
        ProductVendor.product, ProductVendor.vendor
    ]

    column_labels = {
        ProductVendor.product_id: "Gift ID",
        ProductVendor.vendor_id: "Vendor ID",
        ProductVendor.product: "Gift",
        ProductVendor.vendor: "Vendor",
        ProductVendor.created_at: "Created At",
    }

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True

    page_size = 50
    page_size_options = [25, 50, 100, 200]


class GiftCollectionProductAdmin(ModelView, model=GiftCollectionProduct):
    """Admin view for Gift Collection-Product associations."""

    name = "Collection-Gift"
    name_plural = "Collection-Gift Associations"
    icon = "fa-solid fa-link"
    category = "Associations"

    column_list = [
        GiftCollectionProduct.gift_collection, GiftCollectionProduct.product,
        GiftCollectionProduct.quantity, GiftCollectionProduct.created_at
    ]

    column_formatters = {
        GiftCollectionProduct.gift_collection: lambda m, a: m.gift_collection.title if m.gift_collection else "Unknown",
        GiftCollectionProduct.product: lambda m, a: m.product.name if m.product else "Unknown",
        GiftCollectionProduct.gift_collection_id: lambda m, a: format_uuid(m.gift_collection_id),
        GiftCollectionProduct.product_id: lambda m, a: format_uuid(m.product_id),
        GiftCollectionProduct.created_at: lambda m, a: format_datetime(m.created_at),
    }

    form_columns = [
        GiftCollectionProduct.gift_collection, GiftCollectionProduct.product, GiftCollectionProduct.quantity
    ]

    form_args = {
        "quantity": {
            "validators": [validators.DataRequired()],
            "description": "Quantity of this gift in the collection",
        }
    }

    column_labels = {
        GiftCollectionProduct.gift_collection_id: "Collection ID",
        GiftCollectionProduct.product_id: "Gift ID",
        GiftCollectionProduct.gift_collection: "Gift Collection",
        GiftCollectionProduct.product: "Gift",
        GiftCollectionProduct.quantity: "Quantity",
        GiftCollectionProduct.created_at: "Created At",
    }

    can_create = False
    can_edit = False
    can_delete = False
    can_view_details = True
    can_export = True

    page_size = 50
    page_size_options = [25, 50, 100, 200]


class DefaultGiftCollectionProductAdmin(ModelView, model=DefaultGiftCollectionProduct):
    """Admin view for default collection-product associations."""

    name = "Default Collection-Gift"
    name_plural = "Default Collection-Gift Associations"
    icon = "fa-solid fa-link"
    category = "Associations"

    column_list = [
        DefaultGiftCollectionProduct.default_collection,
        DefaultGiftCollectionProduct.product,
        DefaultGiftCollectionProduct.quantity,
        DefaultGiftCollectionProduct.created_at,
    ]

    column_formatters = {
        DefaultGiftCollectionProduct.default_collection: lambda m, a: m.default_collection.name if m.default_collection else "Unknown",
        DefaultGiftCollectionProduct.product: lambda m, a: m.product.name if m.product else "Unknown",
        DefaultGiftCollectionProduct.created_at: lambda m, a: format_datetime(m.created_at),
    }

    column_labels = {
        DefaultGiftCollectionProduct.default_collection: "Default Collection",
        DefaultGiftCollectionProduct.product: "Gift",
        DefaultGiftCollectionProduct.quantity: "Quantity",
        DefaultGiftCollectionProduct.created_at: "Created At",
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

    name = "Order-Gift"
    name_plural = "Order-Gift Items"
    icon = "fa-solid fa-shopping-bag"
    category = "Associations"

    column_list = [
        OrderProduct.order, OrderProduct.product,
        OrderProduct.product_name, OrderProduct.product_price,
        OrderProduct.quantity, OrderProduct.created_at
    ]

    column_formatters = {
        OrderProduct.order: lambda m, a: f"Order {str(m.order_id)[:8]}..." if m.order else "Unknown",
        OrderProduct.product: lambda m, a: m.product.name if m.product else m.product_name,
        OrderProduct.order_id: lambda m, a: format_uuid(m.order_id),
        OrderProduct.product_id: lambda m, a: format_uuid(m.product_id),
        OrderProduct.product_price: lambda m, a: format_price(m.product_price),
        OrderProduct.created_at: lambda m, a: format_datetime(m.created_at),
    }

    form_columns = [
        OrderProduct.order, OrderProduct.product,
        OrderProduct.product_name, OrderProduct.product_price,
        OrderProduct.quantity
    ]

    form_args = {
        "product_name": {
            "validators": [validators.DataRequired()],
            "description": "Gift name snapshot",
        },
        "product_price": {
            "validators": [validators.DataRequired()],
            "description": "Gift price snapshot",
        },
        "quantity": {
            "validators": [validators.DataRequired()],
            "description": "Quantity ordered",
        }
    }

    column_labels = {
        OrderProduct.order_id: "Order ID",
        OrderProduct.product_id: "Gift ID",
        OrderProduct.order: "Order",
        OrderProduct.product: "Gift",
        OrderProduct.product_name: "Gift Name (Snapshot)",
        OrderProduct.product_price: "Gift Price (Snapshot)",
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
