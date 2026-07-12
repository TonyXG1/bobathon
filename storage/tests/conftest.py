"""Fixtures for the storage suite.

DB-backed tests are marked ``db`` and auto-skip when no reachable Postgres is
configured (DATABASE_URL env var, falling back to the repo-root .env). Each
test runs its async steps through a fresh engine + event loop (``db`` fixture)
so nothing leaks between loops, and starts from truncated tables.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "contracts" / "fixtures" / "requirements.sample.json"


def _database_url() -> str | None:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL=") and line.split("=", 1)[1].strip():
                return line.split("=", 1)[1].strip()
    return None


def _run(url: str, fn):
    """Run ``await fn(session)`` on a fresh loop/engine/session; return result."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async def _runner():
        engine = create_async_engine(url)
        try:
            maker = async_sessionmaker(engine, expire_on_commit=False)
            async with maker() as session:
                return await fn(session)
        finally:
            await engine.dispose()

    return asyncio.run(_runner())


@pytest.fixture(scope="session")
def db_url() -> str:
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("asyncpg")
    pytest.importorskip("pgvector")
    url = _database_url()
    if not url:
        pytest.skip("DATABASE_URL not configured")

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from storage.orm import Base

    async def _prepare():
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()

    try:
        asyncio.run(_prepare())
    except Exception as exc:  # noqa: BLE001 - any connection failure means skip
        pytest.skip(f"Postgres unreachable at {url!r}: {exc}")
    return url


@pytest.fixture
def db(db_url):
    """Callable running ``await fn(session)`` against clean tables."""
    from sqlalchemy import text

    async def _clean(session):
        await session.execute(
            text("TRUNCATE findings, obligation_embeddings, obligations RESTART IDENTITY CASCADE")
        )
        await session.commit()

    _run(db_url, _clean)
    return lambda fn: _run(db_url, fn)


@pytest.fixture(scope="session")
def sample_requirements():
    from contracts.models import Requirement

    raw = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return [Requirement.model_validate(item) for item in raw]


@pytest.fixture(scope="session")
def partners():
    # storage/conftest.py put assessment_service on sys.path for this import.
    from portfolio import load_partners

    return load_partners(REPO_ROOT / "dataset" / "partners.json")
