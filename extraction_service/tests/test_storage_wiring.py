"""Offline tests for the obligation-store wiring and the triage endpoint guard."""

import asyncio

import main
from config import Settings
from fastapi.testclient import TestClient
from main import _store_and_read as real_store_and_read


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_store_and_read_returns_none_without_database_url():
    result = asyncio.run(real_store_and_read(_settings(database_url=None), [], None))
    assert result is None


def test_similar_endpoint_503_without_database(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: _settings(database_url=None))
    client = TestClient(main.app)
    resp = client.get("/requirements/32011L0065/similar")
    assert resp.status_code == 503
