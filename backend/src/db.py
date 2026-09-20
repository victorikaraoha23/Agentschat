"""Database engine, session factory, and the session dependency.

Import as ``from src import db`` and resolve the session factory at use time, so tests can retarget
``src.db.get_sessionmaker``.

Everything here is built **lazily**: ``database_url`` defaults to an empty string (unset) and
SQLAlchemy cannot parse an empty URL, so importing this module must not create an engine.
"""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, building it on first use."""
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory, building it on first use."""
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a session, rolling back on error and always closing it."""
    session = get_sessionmaker()()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

