from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from app.core.config import settings


# Create async engine for the API
engine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create sync engine for admin panel (SQLAdmin requires sync)
# Convert asyncpg URL to psycopg2 URL
sync_database_url = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)
sync_engine = create_engine(
    sync_database_url,
    echo=not settings.is_production,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


__all__ = ["Base", "engine", "sync_engine", "AsyncSessionLocal", "get_db"]
