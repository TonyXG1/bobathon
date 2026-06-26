"""API tests for the alerting service (main.py).

Forced into dry-run (TEST_MODE) so no real messages are sent, and Twilio/HTTP
are never actually called.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
FINDINGS_FIXTURE = REPO_ROOT / "contracts" / "fixtures" / "findings.sample.json"


@pytest.fixture
def findings_payload():
    return json.loads(FINDINGS_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "true")  # never send for real in tests
    import config
    import main

    config.get_settings.cache_clear()
    main.ALERTS_LOG.clear()
    with TestClient(main.app) as c:
        yield c
    config.get_settings.cache_clear()
    main.ALERTS_LOG.clear()


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_send_alerts_simulated(client, findings_payload):
    resp = client.post("/alerts", json=findings_payload)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == len(findings_payload)
    assert all(r["status"] == "simulated" for r in results)
    # one message per gap, each carrying the product id
    assert {r["product_id"] for r in results} == {f["product_id"] for f in findings_payload}


def test_alerts_empty_body_is_400(client):
    assert client.post("/alerts", json=[]).status_code == 400


def test_log_is_populated_and_filterable(client, findings_payload):
    client.post("/alerts", json=findings_payload)
    log = client.get("/alerts/log").json()
    assert len(log) == len(findings_payload)

    pid = findings_payload[0]["product_id"]
    only = client.get(f"/alerts/log/{pid}").json()
    assert only and all(e["product_id"] == pid for e in only)


def test_limit_and_channel_filter(client, findings_payload):
    # only email channel, max 1
    resp = client.post(
        "/alerts", params={"limit": 1, "only_channel": "email"}, json=findings_payload
    )
    results = resp.json()
    assert len(results) == 1
    assert results[0]["channel"] == "email"


def test_recipient_routing(monkeypatch, findings_payload):
    # Email goes to the finding's own address (partner contact); SMS/WhatsApp
    # are clamped to OUR test number.
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("TWILIO_TEST_NUMBER", "+15550009999")
    import config
    import main

    config.get_settings.cache_clear()
    main.ALERTS_LOG.clear()
    with TestClient(main.app) as c:
        results = c.post("/alerts", json=findings_payload).json()
    config.get_settings.cache_clear()

    by_pid = {f["product_id"]: f for f in findings_payload}
    for r in results:
        if r["channel"] == "email":
            assert r["to"] == by_pid[r["product_id"]]["alert"]["to"]
        else:
            assert r["to"] == "+15550009999"


def test_dispatch_fetches_from_assessment(client, findings_payload, monkeypatch):
    import main

    class FakeResp:
        def json(self):
            return findings_payload

        def raise_for_status(self):
            return None

    monkeypatch.setattr(main.httpx, "get", lambda url, timeout=None: FakeResp())
    resp = client.post("/dispatch")
    assert resp.status_code == 200
    assert len(resp.json()) == len(findings_payload)


def test_dispatch_502_when_assessment_unreachable(client, monkeypatch):
    import httpx
    import main

    def boom(url, timeout=None):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(main.httpx, "get", boom)
    assert client.post("/dispatch").status_code == 502
