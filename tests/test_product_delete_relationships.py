import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")

from sqlalchemy import inspect

from app.models.product import Product


def test_product_delete_does_not_null_junction_primary_keys():
    """Deleting a gift must not SET NULL on association composite PKs.

    SQLAlchemy's default is to blank parent FKs on related rows before DELETE.
    Junction tables include product_id in the primary key (e.g.
    default_gift_collection_products), so the ORM must delete those rows
    and/or defer to ON DELETE CASCADE instead.
    """
    mapper = inspect(Product)
    for name in (
        "vendor_associations",
        "gift_collection_associations",
        "default_collection_associations",
        "order_items",
    ):
        rel = mapper.relationships[name]
        assert rel.passive_deletes is True, name
        assert "delete" in rel.cascade, name
        assert "delete-orphan" in rel.cascade, name
