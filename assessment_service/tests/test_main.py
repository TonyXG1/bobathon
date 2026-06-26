"""API tests for the assessment service (main.py).

The extraction service is mocked, so these run offline.
"""

from datetime import UTC, date, datetime

import httpx
import main
import pytest
from engine import RULES
from fastapi.testclient import TestClient

from contracts.models import Requirement, RequirementScope

FAMILIES = sorted({rule.family for rule in RULES})


def _req(family: str) -> Requirement:
    return Requirement(
        update_id=f"REQ-{family}",
        published_date=date(2024, 1, 1),
        source="EUR-Lex",
        source_url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{family}",
        access_timestamp=datetime.now(UTC),
        regulation_family=family,
        title=f"{family} requirement",
        change_type="new",
        severity="high",
        scope=RequirementScope(categories="all", markets=["EU"]),
    )


@pytest.fixture
def client():
    return TestClient(main.app)


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_assess_with_requirements_in_body(client):
    body = {"requirements": [r.model_dump(mode="json") for r in (_req(f) for f in FAMILIES)]}
    resp = client.post("/assess", json=body)
    assert resp.status_code == 200
    findings = resp.json()
    assert len(findings) == 15
    assert all(f["source_url"].startswith("http") for f in findings)


def test_assess_empty_body_fetches_from_extraction(client, monkeypatch):
    monkeypatch.setattr(
        main, "fetch_requirements_from_extraction", lambda settings: [_req(f) for f in FAMILIES]
    )
    resp = client.post("/assess", json={})
    assert resp.status_code == 200
    assert len(resp.json()) == 15


def test_findings_runs_full_pipeline(client, monkeypatch):
    monkeypatch.setattr(
        main, "fetch_requirements_from_extraction", lambda settings: [_req(f) for f in FAMILIES]
    )
    resp = client.get("/findings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 15
    assert any("Battery Regulation" in f["regulation"] for f in data)


def test_findings_502_when_extraction_unreachable(client, monkeypatch):
    def boom(settings):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(main, "fetch_requirements_from_extraction", boom)
    resp = client.get("/findings")
    assert resp.status_code == 502
