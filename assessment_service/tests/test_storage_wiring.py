"""Offline tests for the obligation-store wiring (graceful degradation).

The real functions are captured at import time, so the autouse hermetic patch
in ``conftest.py`` (which swaps the module attributes) does not affect them.
"""

import asyncio

import pytest
from config import Settings
from engine import RULES
from main import (
    RULE_ID_BY_REGULATION,
    fetch_requirements_from_store,
    persist_findings,
)


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_store_fetch_returns_none_without_database_url():
    result = asyncio.run(fetch_requirements_from_store(_settings(database_url=None)))
    assert result is None


def test_store_fetch_returns_none_when_db_unreachable():
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("asyncpg")
    url = "postgresql+asyncpg://nobody:nothing@localhost:59999/nowhere"
    result = asyncio.run(fetch_requirements_from_store(_settings(database_url=url)))
    assert result is None


def test_persist_findings_is_a_noop_without_database_url():
    # Must not raise — audit is best-effort and never fails the response.
    asyncio.run(persist_findings(_settings(database_url=None), []))


def test_rule_id_map_covers_every_rule_uniquely():
    # save_findings resolves rule_id via the regulation label — 1:1 required.
    assert len(RULE_ID_BY_REGULATION) == len(RULES)
    assert set(RULE_ID_BY_REGULATION.values()) == {rule.rule_id for rule in RULES}
