import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/test_db")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "test")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "test")
os.environ.setdefault("SENDGRID_API_KEY", "test")
os.environ.setdefault("SENDGRID_FROM_EMAIL", "test@example.com")

from sqlalchemy import inspect

from app.models.user import User


def test_user_delete_does_not_null_required_cascade_fks():
    """Deleting a user must not SET NULL on NOT NULL child FKs.

    SQLAlchemy's default is to null parent FKs on related rows before DELETE.
    Those children use ON DELETE CASCADE and required columns (e.g.
    gift_collections.director_id), so the ORM must defer to the database.
    """
    mapper = inspect(User)
    for name in (
        "directed_gift_collections",
        "owned_gift_collections",
        "orders",
        "wallet",
        "order_commissions",
    ):
        assert mapper.relationships[name].passive_deletes is True, name
