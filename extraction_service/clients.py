"""Live client for EUR-Lex / CELLAR.

The CELLAR SPARQL endpoint (Virtuoso) is public, no-auth, and returns the
metadata for any act by CELEX. We query it for the English title and document
date of each watchlist regulation — that is the live data the service serves.

Every request carries a polite ``User-Agent`` and an explicit timeout. The
client accepts an optional ``httpx.Client`` so tests can inject a mock transport
and never touch the network.
"""

from __future__ import annotations

from typing import Any

import httpx
from config import Settings, get_settings

# SPARQL: fetch the English title + document date for one CELEX. The
# FILTER(STR(?celex) = ...) form matches the typed CELEX literal reliably
# (a VALUES clause does not, in the CELLAR Virtuoso store).
_METADATA_QUERY = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX lang: <http://publications.europa.eu/resource/authority/language/>
SELECT ?celex ?date ?title WHERE {{
  ?work cdm:resource_legal_id_celex ?celex .
  ?work cdm:work_date_document ?date .
  ?expr cdm:expression_belongs_to_work ?work .
  ?expr cdm:expression_uses_language lang:ENG .
  ?expr cdm:expression_title ?title .
  FILTER(STR(?celex) = "{celex}")
}}
LIMIT 1
"""


def parse_sparql_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the SPARQL JSON results object into ``[{var: value, ...}]``."""
    bindings = payload.get("results", {}).get("bindings", [])
    return [{k: v.get("value") for k, v in row.items()} for row in bindings]


class CellarClient:
    """Query the CELLAR SPARQL endpoint for live regulation metadata."""

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.settings = settings or get_settings()
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.settings.http_timeout)
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> CellarClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def query_sparql(self, query: str) -> list[dict[str, Any]]:
        """Run a SPARQL query and return a flat list of binding dicts."""
        resp = self.client.post(
            self.settings.cellar_sparql_endpoint,
            data={"query": query},
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept": "application/sparql-results+json",
            },
            timeout=self.settings.http_timeout,
        )
        resp.raise_for_status()
        return parse_sparql_results(resp.json())

    def get_metadata(self, celex: str) -> dict[str, Any] | None:
        """Return ``{celex, date, title}`` for a CELEX, or ``None`` if not found."""
        rows = self.query_sparql(_METADATA_QUERY.format(celex=celex))
        return rows[0] if rows else None

    @staticmethod
    def document_url(celex: str) -> str:
        """Canonical human-facing EUR-Lex URL for a CELEX (used as source_url)."""
        return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
