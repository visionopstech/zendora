"""Default seed content and preview samples for system email templates."""

from app.models.email_template import EmailTemplateSlug


def _html_email(title: str, inner: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
        .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 5px 5px; }}
        .info-box {{ background-color: white; padding: 20px; border-left: 4px solid #4F46E5; margin: 20px 0; }}
        .product-item {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
        .button {{ display: inline-block; padding: 12px 30px; background-color: #4F46E5; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
        .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>{title}</h1></div>
        <div class="content">
{inner}
        </div>
        <div class="footer"><p>&copy; 2026 Zendora. All rights reserved.</p></div>
    </div>
</body>
</html>"""


_PRODUCT_LOOP = """
            {% for product in products %}
            <div class="product-item">
                <strong>{{ product.name }}</strong><br>
                Quantity: {{ product.quantity }} &times; ${{ product.price }} = ${{ product.total }}
            </div>
            {% endfor %}
"""

DEFAULT_EMAIL_TEMPLATES: list[dict] = [
    {
        "slug": EmailTemplateSlug.ORDER_CREATED_VENDOR.value,
        "name": "New Order Received (Vendor)",
        "subject": "New Order Received",
        "description": "Sent to vendor users when an order is paid.",
        "available_variables": [
            {"name": "order.id", "description": "Order ID"},
            {"name": "order.total_amount", "description": "Order total"},
            {"name": "products", "description": "This vendor's purchased gifts (name, quantity, price, total)"},
            {"name": "product_count", "description": "Total quantity of this vendor's gifts"},
            {"name": "price", "description": "Total price for this vendor's gifts"},
            {"name": "family.name", "description": "Family admin name"},
            {"name": "family.email", "description": "Family admin email"},
            {"name": "family.deceased_name", "description": "Deceased person's name"},
            {"name": "family.address", "description": "Family address"},
            {"name": "delivery.formatted", "description": "Delivery address"},
            {"name": "vendor.name", "description": "Vendor name"},
        ],
        "body": _html_email(
            "New Order Received",
            f"""
            <p>A new order includes gifts you supply.</p>
            <div class="info-box">
                <p><strong>Order ID:</strong> {{{{ order.id }}}}</p>
                <p><strong>Vendor:</strong> {{{{ vendor.name }}}}</p>
                <p><strong>Product count:</strong> {{{{ product_count }}}}</p>
                <p><strong>Price:</strong> ${{{{ price }}}}</p>
            </div>
            <div class="info-box">
                <h3>Family</h3>
                <p><strong>Name:</strong> {{{{ family.name }}}}</p>
                <p><strong>Email:</strong> {{{{ family.email }}}}</p>
                <p><strong>Deceased:</strong> {{{{ family.deceased_name }}}}</p>
                <p><strong>Address:</strong> {{{{ family.address }}}}</p>
            </div>
            <div class="info-box">
                <h3>Delivery</h3>
                <p>{{{{ delivery.formatted }}}}</p>
            </div>
            <div class="info-box">
                <h3>Products</h3>
                {_PRODUCT_LOOP}
            </div>
            """,
        ),
    },
    {
        "slug": EmailTemplateSlug.ORDER_CREATED_FAMILY_ADMIN.value,
        "name": "Gift Purchased (Family Admin)",
        "subject": "A gift was purchased from your collection",
        "description": "Sent to the family admin when an order is paid.",
        "available_variables": [
            {"name": "order.id", "description": "Order ID"},
            {"name": "products", "description": "Purchased gifts"},
            {"name": "collection.name", "description": "Collection name"},
            {"name": "collection.link", "description": "Public collection URL"},
            {"name": "buyer.name", "description": "Buyer name"},
            {"name": "buyer.email", "description": "Buyer email"},
        ],
        "body": _html_email(
            "A gift was purchased from your collection",
            f"""
            <p>Someone purchased gifts from your collection.</p>
            <div class="info-box">
                <p><strong>Order ID:</strong> {{{{ order.id }}}}</p>
                <p><strong>Collection:</strong> {{{{ collection.name }}}}</p>
                <p><a href="{{{{ collection.link }}}}">View collection</a></p>
            </div>
            <div class="info-box">
                <h3>Buyer</h3>
                <p><strong>Name:</strong> {{{{ buyer.name }}}}</p>
                <p><strong>Email:</strong> {{{{ buyer.email }}}}</p>
            </div>
            <div class="info-box">
                <h3>Products purchased</h3>
                {_PRODUCT_LOOP}
            </div>
            """,
        ),
    },
    {
        "slug": EmailTemplateSlug.ORDER_CREATED_BUYER.value,
        "name": "Order Confirmation (Buyer)",
        "subject": "Order confirmation",
        "description": "Sent to the buyer when an order is paid.",
        "available_variables": [
            {"name": "order.id", "description": "Order ID"},
            {"name": "price_paid", "description": "Amount paid"},
            {"name": "products", "description": "Purchased gifts"},
            {"name": "family.name", "description": "Family admin name"},
            {"name": "family.deceased_name", "description": "Deceased person's name"},
            {"name": "collection.name", "description": "Collection name"},
            {"name": "collection.link", "description": "Public collection URL"},
        ],
        "body": _html_email(
            "Order confirmation",
            f"""
            <p>Thank you for your purchase.</p>
            <div class="info-box">
                <p><strong>Order ID:</strong> {{{{ order.id }}}}</p>
                <p><strong>Price paid:</strong> ${{{{ price_paid }}}}</p>
                <p><strong>Collection:</strong> {{{{ collection.name }}}}</p>
                <p><a href="{{{{ collection.link }}}}">View collection</a></p>
            </div>
            <div class="info-box">
                <h3>Family</h3>
                <p><strong>Name:</strong> {{{{ family.name }}}}</p>
                <p><strong>In memory of:</strong> {{{{ family.deceased_name }}}}</p>
            </div>
            <div class="info-box">
                <h3>Products purchased</h3>
                {_PRODUCT_LOOP}
            </div>
            """,
        ),
    },
    {
        "slug": EmailTemplateSlug.ORDER_CREATED_SUPER_ADMIN.value,
        "name": "New Order Created (Super Admin)",
        "subject": "New order created",
        "description": "Sent to super admins when an order is paid.",
        "available_variables": [
            {"name": "order.id", "description": "Order ID"},
            {"name": "order.total_amount", "description": "Total price"},
            {"name": "buyer.name", "description": "Buyer name"},
            {"name": "buyer.email", "description": "Buyer email"},
            {"name": "family.name", "description": "Family admin name"},
            {"name": "family.email", "description": "Family admin email"},
            {"name": "vendors", "description": "List of vendor names"},
            {"name": "products", "description": "Purchased gifts"},
        ],
        "body": _html_email(
            "New order created",
            f"""
            <p>A new paid order has been created.</p>
            <div class="info-box">
                <p><strong>Order ID:</strong> {{{{ order.id }}}}</p>
                <p><strong>Total price:</strong> ${{{{ order.total_amount }}}}</p>
                <p><strong>Buyer:</strong> {{{{ buyer.name }}}} ({{{{ buyer.email }}}})</p>
                <p><strong>Family:</strong> {{{{ family.name }}}} ({{{{ family.email }}}})</p>
                <p><strong>Vendors:</strong>
                    {{% for vendor in vendors %}}{{{{ vendor.name }}}}{{% if not loop.last %}}, {{% endif %}}{{% endfor %}}
                </p>
            </div>
            <div class="info-box">
                <h3>Products</h3>
                {_PRODUCT_LOOP}
            </div>
            """,
        ),
    },
    {
        "slug": EmailTemplateSlug.COLLECTION_CREATED_FAMILY_ADMIN.value,
        "name": "Collection Created (Family Admin)",
        "subject": "Your Zendora collection has been created",
        "description": "Sent to the family admin when a collection is created.",
        "available_variables": [
            {"name": "collection.name", "description": "Collection name"},
            {"name": "collection.link", "description": "Public collection URL"},
        ],
        "body": _html_email(
            "Your Zendora collection has been created",
            """
            <p>Your gift collection is ready.</p>
            <div class="info-box">
                <p><strong>Collection:</strong> {{ collection.name }}</p>
            </div>
            <a href="{{ collection.link }}" class="button">View your collection</a>
            """,
        ),
    },
    {
        "slug": EmailTemplateSlug.COLLECTION_CREATED_DIRECTOR.value,
        "name": "New Family Collection (Director)",
        "subject": "New family collection created",
        "description": "Sent to the collection director when a collection is created, if a director is assigned.",
        "available_variables": [
            {"name": "family_admin.name", "description": "Family admin name"},
            {"name": "family_admin.email", "description": "Family admin email"},
            {"name": "collection.name", "description": "Collection name"},
            {"name": "collection.link", "description": "Public collection URL"},
        ],
        "body": _html_email(
            "New family collection created",
            """
            <p>A new family collection has been created.</p>
            <div class="info-box">
                <p><strong>Family admin:</strong> {{ family_admin.name }} ({{ family_admin.email }})</p>
                <p><strong>Collection:</strong> {{ collection.name }}</p>
            </div>
            <a href="{{ collection.link }}" class="button">View collection</a>
            """,
        ),
    },
    {
        "slug": EmailTemplateSlug.COLLECTION_CREATED_SUPER_ADMIN.value,
        "name": "New Collection Created (Super Admin)",
        "subject": "New Collection Created",
        "description": "Sent to super admins when a collection is created.",
        "available_variables": [
            {"name": "family_admin.name", "description": "Family admin name"},
            {"name": "family_admin.email", "description": "Family admin email"},
            {"name": "director.name", "description": "Director name"},
            {"name": "director.email", "description": "Director email"},
            {"name": "funeral_home.name", "description": "Funeral home name"},
            {"name": "funeral_home.email", "description": "Funeral home email"},
            {"name": "funeral_home.phone", "description": "Funeral home phone"},
            {"name": "funeral_home.address", "description": "Funeral home address"},
            {"name": "collection.name", "description": "Collection name"},
            {"name": "collection.link", "description": "Public collection URL"},
        ],
        "body": _html_email(
            "New Collection Created",
            """
            <p>A new gift collection has been created.</p>
            <div class="info-box">
                <h3>Family</h3>
                <p><strong>Name:</strong> {{ family_admin.name }}</p>
                <p><strong>Email:</strong> {{ family_admin.email }}</p>
            </div>
            <div class="info-box">
                <h3>Director</h3>
                <p><strong>Name:</strong> {{ director.name }}</p>
                <p><strong>Email:</strong> {{ director.email }}</p>
            </div>
            <div class="info-box">
                <h3>Funeral home</h3>
                <p><strong>Name:</strong> {{ funeral_home.name }}</p>
                <p><strong>Email:</strong> {{ funeral_home.email }}</p>
                <p><strong>Phone:</strong> {{ funeral_home.phone }}</p>
                <p><strong>Address:</strong> {{ funeral_home.address }}</p>
            </div>
            <div class="info-box">
                <h3>Collection</h3>
                <p><strong>Name:</strong> {{ collection.name }}</p>
                <p><a href="{{ collection.link }}">{{ collection.link }}</a></p>
            </div>
            """,
        ),
    },
]

SAMPLE_EMAIL_CONTEXTS: dict[str, dict] = {
    EmailTemplateSlug.ORDER_CREATED_VENDOR.value: {
        "order": {"id": "00000000-0000-0000-0000-000000000001", "total_amount": "49.00", "currency": "USD"},
        "products": [{"name": "Sympathy flowers", "quantity": 2, "price": "24.50", "total": "49.00"}],
        "product_count": 2,
        "price": "49.00",
        "family": {
            "name": "Jane Family",
            "email": "family@example.com",
            "deceased_name": "John Doe",
            "address": "1 Main St, Springfield, IL 62701, USA",
        },
        "delivery": {"formatted": "1 Main St, Springfield, IL 62701, USA"},
        "vendor": {"name": "Bloom Vendor"},
    },
    EmailTemplateSlug.ORDER_CREATED_FAMILY_ADMIN.value: {
        "order": {"id": "00000000-0000-0000-0000-000000000001"},
        "products": [{"name": "Sympathy flowers", "quantity": 1, "price": "24.50", "total": "24.50"}],
        "collection": {"name": "In Memory of John", "link": "http://localhost:3000/w/abc123"},
        "buyer": {"name": "Alex Buyer", "email": "buyer@example.com"},
    },
    EmailTemplateSlug.ORDER_CREATED_BUYER.value: {
        "order": {"id": "00000000-0000-0000-0000-000000000001"},
        "price_paid": "24.50",
        "products": [{"name": "Sympathy flowers", "quantity": 1, "price": "24.50", "total": "24.50"}],
        "family": {"name": "Jane Family", "deceased_name": "John Doe"},
        "collection": {"name": "In Memory of John", "link": "http://localhost:3000/w/abc123"},
    },
    EmailTemplateSlug.ORDER_CREATED_SUPER_ADMIN.value: {
        "order": {"id": "00000000-0000-0000-0000-000000000001", "total_amount": "24.50"},
        "buyer": {"name": "Alex Buyer", "email": "buyer@example.com"},
        "family": {"name": "Jane Family", "email": "family@example.com"},
        "vendors": [{"name": "Bloom Vendor"}],
        "products": [{"name": "Sympathy flowers", "quantity": 1, "price": "24.50", "total": "24.50"}],
    },
    EmailTemplateSlug.COLLECTION_CREATED_FAMILY_ADMIN.value: {
        "collection": {"name": "In Memory of John", "link": "http://localhost:3000/w/abc123"},
    },
    EmailTemplateSlug.COLLECTION_CREATED_DIRECTOR.value: {
        "family_admin": {"name": "Jane Family", "email": "family@example.com"},
        "collection": {"name": "In Memory of John", "link": "http://localhost:3000/w/abc123"},
    },
    EmailTemplateSlug.COLLECTION_CREATED_SUPER_ADMIN.value: {
        "family_admin": {"name": "Jane Family", "email": "family@example.com"},
        "director": {"name": "Dana Director", "email": "director@example.com"},
        "funeral_home": {
            "name": "Riverside Chapel",
            "email": "chapel@example.com",
            "phone": "555-0100",
            "address": "10 Chapel Rd, Springfield, IL 62701, USA",
        },
        "collection": {"name": "In Memory of John", "link": "http://localhost:3000/w/abc123"},
    },
}
