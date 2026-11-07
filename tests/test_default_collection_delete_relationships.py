import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")

from sqlalchemy import inspect

from app.models.default_gift_collection import DefaultGiftCollection


def test_default_collection_delete_does_not_null_junction_primary_keys():
    """Deleting a default must not SET NULL on its gift-association primary key.

    SQLAlchemy's default is to blank parent FKs on related rows before DELETE.
    default_gift_collection_products includes default_collection_id in the
    primary key, so the ORM must defer to ON DELETE CASCADE. Copied gift
    collections use ON DELETE SET NULL and must not be deleted with the default.
    """
    mapper = inspect(DefaultGiftCollection)

    products = mapper.relationships["products"]
    assert products.passive_deletes is True
    assert "delete" in products.cascade
    assert "delete-orphan" in products.cascade

    derived = mapper.relationships["derived_collections"]
    assert derived.passive_deletes is True
    assert "delete" not in derived.cascade
