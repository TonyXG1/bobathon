"""Keep the offline API tests hermetic: never touch a real obligation store.

Endpoint tests exercise the HTTP-fallback path exactly as before this change;
the real store functions are tested directly in ``test_storage_wiring.py``
(which captures the unpatched function objects at import time).
"""

import main
import pytest


@pytest.fixture(autouse=True)
def _no_obligation_store(monkeypatch):
    async def _no_store(settings):
        return None

    async def _no_persist(settings, findings):
        return None

    monkeypatch.setattr(main, "fetch_requirements_from_store", _no_store)
    monkeypatch.setattr(main, "persist_findings", _no_persist)
