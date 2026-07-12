"""Async engine / session factory for the obligation store.

Everything is lazy: no connection (and no engine) is created at import time.
Services pass their own ``DATABASE_URL`` (from pydantic-settings); engines are
cached per URL so repeated calls share the pool.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engines: dict[str, AsyncEngine] = {}
_sessionmakers: dict[str, async_sessionmaker[AsyncSession]] = {}


def get_engine(database_url: str) -> AsyncEngine:
    """Cached async engine for ``database_url`` (created on first use)."""
    engine = _engines.get(database_url)
    if engine is None:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        _engines[database_url] = engine
    return engine


def get_sessionmaker(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Cached session factory bound to the engine for ``database_url``."""
    maker = _sessionmakers.get(database_url)
    if maker is None:
        maker = async_sessionmaker(get_engine(database_url), expire_on_commit=False)
        _sessionmakers[database_url] = maker
    return maker


async def dispose_engine(database_url: str) -> None:
    """Dispose and forget the engine for ``database_url`` (tests / shutdown)."""
    engine = _engines.pop(database_url, None)
    _sessionmakers.pop(database_url, None)
    if engine is not None:
        await engine.dispose()
