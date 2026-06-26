# Extraction Service (Part 1)

Pulls current EU regulatory requirements **live** from EUR-Lex / CELLAR and
normalizes them to the `Requirement` schema. **Simplified, no-database build:**
every request queries the live SPARQL endpoint and returns results directly — no
persistence, no extraction job to trigger.

## How it works

For each regulation on the watchlist (the ~11 key acts: RoHS, REACH, WEEE,
Battery, PPWR, GPSR, RED, ESPR, Toy Safety, MDR, POPs) the service queries the
CELLAR SPARQL endpoint for the act's English title and document date, then builds
a `Requirement` whose `source_url` points at the real EUR-Lex document. Requests
to the watchlist run concurrently (≤ 5 connections, to stay a polite client).

## API Endpoints

- `GET /requirements` — live list of watchlist requirements.
  Optional repeatable filter: `?family=battery&family=reach`.
- `GET /requirements/{celex}` — one requirement by CELEX (e.g. `32023R1542`).
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

## Running with Docker

```bash
docker build -t extraction-service .
docker run -p 8081:8081 extraction-service
```

## Testing

```bash
# fast, offline (network mocked):
uv run pytest -m "not integration"
# live smoke test against the real CELLAR endpoint:
uv run pytest -m integration
```

## Environment Variables (all optional)

- `CELLAR_SPARQL_ENDPOINT` — SPARQL endpoint (default: the public CELLAR endpoint)
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
