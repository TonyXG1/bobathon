"""Keep the offline API tests hermetic: never touch a real obligation store.

Endpoint tests exercise the stateless live path exactly as before this change;
the real store helper is tested directly in ``test_storage_wiring.py`` (which
captures the unpatched function object at import time).
"""

import main
import pytest


@pytest.fixture(autouse=True)
def _no_obligation_store(monkeypatch):
    async def _no_store(settings, fetched, families):
        return None

    monkeypatch.setattr(main, "_store_and_read", _no_store)
