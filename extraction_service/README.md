# Extraction Service (Part 1)

Pulls current EU regulatory requirements **live** from EUR-Lex / CELLAR and
normalizes them to the `Requirement` schema. Every request queries the live
SPARQL endpoint; when `DATABASE_URL` is configured the results are also
**upserted into the shared obligation store** (`storage/`, one Postgres) — by
content hash, so unchanged rules are no-ops and changed rules supersede rather
than overwrite — and `GET /requirements` serves the in-force set from the
store, which also bridges live outages. Without a database the service runs
in the old stateless mode.

## How it works

For each regulation on the watchlist (the ~11 key acts: RoHS, REACH, WEEE,
Battery, PPWR, GPSR, RED, ESPR, Toy Safety, MDR, POPs) the service queries the
CELLAR SPARQL endpoint for the act's English title and document date, then builds
a `Requirement` whose `source_url` points at the real EUR-Lex document. Requests
to the watchlist run concurrently (≤ 5 connections, to stay a polite client).

## API Endpoints

- `GET /requirements` — live list of watchlist requirements (persisted and
  served from the obligation store when configured).
  Optional repeatable filter: `?family=battery&family=reach`.
- `GET /requirements/{celex}` — one requirement by CELEX (e.g. `32023R1542`).
- `GET /requirements/{celex}/similar` — **triage only**: stored obligations
  semantically near this one (pgvector). Never part of the decision path;
  503 without a database.
- `GET /health` — health check.

## Key Files

- `main.py` — FastAPI app and endpoints (live, stateless).
- `extractor.py` — the watchlist + concurrent live fetch (`fetch_requirements`).
- `clients.py` — `CellarClient`: CELLAR SPARQL query + metadata lookup.
- `normalize.py` — raw source data → `Requirement` (taxonomy mapping, provenance).
- `config.py` — settings (`BaseSettings` from pydantic-settings).

## Technology Stack

- **FastAPI** — web framework
- **Pydantic v2** — data validation (the `Requirement` contract)
- **httpx** — HTTP client (SPARQL over plain HTTP)

## Running Locally

```bash
cd extraction_service
# with uv:
uv sync && uv run uvicorn main:app --reload --port 8081
# or with a plain venv:
python -m venv ../.venv && ../.venv/Scripts/python -m pip install -e .
../.venv/Scripts/python -m uvicorn main:app --reload --port 8081
```

Visit http://localhost:8081/docs for interactive API documentation, then call
`GET /requirements` to get live data. (First call takes ~8 s — it queries CELLAR.)

## Testing

```bash
# fast, offline (network mocked):
uv run pytest -m "not integration"
# live smoke test against the real CELLAR endpoint:
uv run pytest -m integration
```

## Environment Variables (all optional)

- `CELLAR_SPARQL_ENDPOINT` — SPARQL endpoint (default: the public CELLAR endpoint)
- `DATABASE_URL` — the obligation store (default: unset → stateless mode)
- `HTTP_TIMEOUT` — request timeout in seconds (default: 60)
- `CONTACT_EMAIL` — used in the polite `User-Agent` (default: `contact@example.com`)
- `LOG_LEVEL` — logging level (default: INFO)

## Security Notes

- Explicit timeouts on every HTTP request.
- Polite client: clear `User-Agent` with contact, ≤ 5 concurrent connections.
- Never log secrets or credentials.

## Provenance (mandatory)

Every `Requirement` carries:
- `source_url` — the live EUR-Lex document URL
- `celex` — the CELEX id
- `access_timestamp` — when it was fetched (UTC)

## Troubleshooting

**Slow / timing out:** the EU SPARQL endpoint can be slow; raise `HTTP_TIMEOUT`.
The watchlist is fetched concurrently, so a full `/requirements` call is ~8 s.

**`502` from `/requirements`:** the live source returned nothing (network or
endpoint outage). Retry; check connectivity to `publications.europa.eu`.
