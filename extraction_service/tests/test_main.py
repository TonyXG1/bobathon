"""Tests for live extraction (extractor.py) and the API (main.py).

A fake CELLAR client stands in for the network, so these run offline and fast.
"""

import main
import pytest
from extractor import WATCHLIST, fetch_requirements
from fastapi.testclient import TestClient

from contracts.models import Requirement


class FakeCellar:
    """Stand-in for CellarClient returning canned metadata."""

    def __init__(self, missing: set[str] | None = None, boom: set[str] | None = None):
        self.missing = missing or set()
        self.boom = boom or set()
        self.closed = False

    def get_metadata(self, celex: str):
        if celex in self.boom:
            raise RuntimeError("simulated source failure")
        if celex in self.missing:
            return None
        return {"celex": celex, "date": "2023-07-12", "title": f"Title for {celex}"}

    def close(self):
        self.closed = True


def test_fetch_requirements_all_watchlist():
    reqs = fetch_requirements(client=FakeCellar())
    assert len(reqs) == len(WATCHLIST)
    assert all(isinstance(r, Requirement) for r in reqs)
    by_family = {r.regulation_family: r for r in reqs}
    battery = by_family["battery"]
    assert battery.celex == "32023R1542"
    assert battery.source == "EUR-Lex"
    assert battery.source_url.endswith("CELEX:32023R1542")  # provenance
    assert battery.scope.markets == ["EU"]


def test_fetch_requirements_family_filter():
    reqs = fetch_requirements(client=FakeCellar(), families=["battery", "reach"])
    assert {r.regulation_family for r in reqs} == {"battery", "reach"}


def test_fetch_requirements_skips_missing_and_errors():
    fake = FakeCellar(missing={"32011L0065"}, boom={"32006R1907"})  # rohs missing, reach errors
    reqs = fetch_requirements(client=fake)
    families = {r.regulation_family for r in reqs}
    assert "rohs" not in families
    assert "reach" not in families
    assert "battery" in families
    assert len(reqs) == len(WATCHLIST) - 2


@pytest.fixture
def client(monkeypatch):
    # Replace the live fetch with the fake-backed one so the API runs offline.
    monkeypatch.setattr(
        main,
        "fetch_requirements",
        lambda settings=None, families=None: fetch_requirements(
            client=FakeCellar(), families=families
        ),
    )
    return TestClient(main.app)


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_list_requirements(client):
    resp = client.get("/requirements")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == len(WATCHLIST)
    assert all(r["source_url"].startswith("http") for r in data)


def test_list_requirements_with_family_filter(client):
    resp = client.get("/requirements", params={"family": ["battery"]})
    data = resp.json()
    assert len(data) == 1
    assert data[0]["regulation_family"] == "battery"


def test_get_requirement_by_celex(client):
    resp = client.get("/requirements/32023R1542")
    assert resp.status_code == 200
    assert resp.json()["celex"] == "32023R1542"


def test_get_requirement_unknown_celex_404(client):
    resp = client.get("/requirements/99999999")
    assert resp.status_code == 404
