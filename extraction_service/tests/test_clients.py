"""Tests for the CELLAR client (clients.py).

Network is mocked with ``httpx.MockTransport`` so no test hits the real endpoint.
"""

import httpx
import pytest
from clients import CellarClient, parse_sparql_results
from config import Settings

SAMPLE_PAYLOAD = {
    "head": {"vars": ["celex", "date", "title"]},
    "results": {
        "bindings": [
            {
                "celex": {"value": "32023R1542"},
                "date": {"value": "2023-07-12"},
                "title": {"value": "Regulation (EU) 2023/1542 concerning batteries"},
            }
        ]
    },
}


@pytest.fixture
def settings() -> Settings:
    return Settings()


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parse_sparql_results_flattens_bindings():
    assert parse_sparql_results(SAMPLE_PAYLOAD) == [
        {
            "celex": "32023R1542",
            "date": "2023-07-12",
            "title": "Regulation (EU) 2023/1542 concerning batteries",
        }
    ]


def test_parse_sparql_results_empty():
    assert parse_sparql_results({}) == []


def test_query_sparql_sends_polite_headers(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Accept"] == "application/sparql-results+json"
        assert "RegulatoryRadar" in request.headers["User-Agent"]
        assert request.method == "POST"
        return httpx.Response(200, json=SAMPLE_PAYLOAD)

    with _client(handler) as http:
        cellar = CellarClient(settings=settings, client=http)
        rows = cellar.query_sparql("SELECT * WHERE {?s ?p ?o} LIMIT 1")
    assert rows[0]["celex"] == "32023R1542"


def test_get_metadata_returns_first_row(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert "32023R1542" in body  # CELEX interpolated into the query
        return httpx.Response(200, json=SAMPLE_PAYLOAD)

    with _client(handler) as http:
        cellar = CellarClient(settings=settings, client=http)
        meta = cellar.get_metadata("32023R1542")
    assert meta["title"].startswith("Regulation (EU) 2023/1542")
    assert meta["date"] == "2023-07-12"


def test_get_metadata_none_when_no_results(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": {"bindings": []}})

    with _client(handler) as http:
        cellar = CellarClient(settings=settings, client=http)
        assert cellar.get_metadata("00000000") is None


def test_query_sparql_raises_on_http_error(settings):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with _client(handler) as http, pytest.raises(httpx.HTTPStatusError):
        CellarClient(settings=settings, client=http).query_sparql("SELECT 1")


def test_document_url():
    assert (
        CellarClient.document_url("32023R1542")
        == "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1542"
    )
