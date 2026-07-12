"""Extraction Service (Part 1) — FastAPI app (live fetch + obligation store).

Every request queries the live EUR-Lex / CELLAR SPARQL endpoint. When a
``DATABASE_URL`` is configured, fetched requirements are upserted into the
obligation store (by content hash — unchanged rules are no-ops, changed rules
supersede) and ``GET /requirements`` serves the in-force set from the store,
which also bridges live outages. Without a database the service keeps the old
stateless behavior.

Endpoints:
* ``GET /health``                       — liveness probe.
* ``GET /requirements``                 — watchlist requirements (live fetch,
                                          persisted + served from the store when
                                          configured). Optional
                                          ``?family=battery&family=reach`` filter.
* ``GET /requirements/{celex}``         — one requirement by CELEX.
* ``GET /requirements/{celex}/similar`` — TRIAGE ONLY: semantically similar
                                          stored obligations via pgvector.
"""

from __future__ import annotations

import logging
from typing import Any

from config import Settings, get_settings
from extractor import WATCHLIST, fetch_requirements
from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from contracts.models import Requirement

logging.basicConfig(level=get_settings().log_level.upper())
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Regulatory Radar — Extraction Service",
    description="Pull & normalize current EU regulatory requirements live from EUR-Lex/CELLAR.",
    version="0.2.0",
)

# CORS — let the browser frontend call this API (origins from CORS_ORIGINS in .env).
_cors_origins = get_settings().cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "extraction"}


async def _store_and_read(
    settings: Settings,
    fetched: list[Requirement],
    families: list[str] | None,
) -> list[Requirement] | None:
    """Persist fetched requirements and read back the in-force set.

    Returns ``None`` when no database is configured/reachable, so the caller
    can fall back to the stateless live-only behavior. Vector embedding is
    opportunistic (triage only) and never fails the upsert.
    """
    if not settings.database_url:
        return None
    try:
        from storage import repository, similarity
        from storage.db import get_sessionmaker
    except ImportError:
        logger.warning("storage package deps not installed — running stateless")
        return None
    try:
        maker = get_sessionmaker(settings.database_url)
        async with maker() as session:
            new_ids = await repository.upsert_requirements(session, fetched)
            await similarity.embed_obligations(session, new_ids)
            stored = await repository.get_in_force_requirements(session)
    except Exception as exc:  # noqa: BLE001 - degrade to stateless on any DB failure
        logger.warning("Obligation store unavailable (%s) — running stateless", exc)
        return None
    if families:
        wanted = {f.lower() for f in families}
        stored = [r for r in stored if r.regulation_family in wanted]
    return stored


@app.get("/requirements", response_model=list[Requirement])
async def list_requirements(
    family: list[str] | None = Query(  # noqa: B008 - FastAPI dependency-injection idiom
        default=None,
        description="Filter by regulation family (repeatable), e.g. battery, reach, rohs.",
    ),
) -> list[Requirement]:
    """Fetch the watchlist requirements live from CELLAR (and persist them)."""
    settings = get_settings()
    reqs = await run_in_threadpool(fetch_requirements, settings, families=family)
    stored = await _store_and_read(settings, reqs, family)
    if stored:
        return stored
    if reqs:
        return reqs
    raise HTTPException(
        status_code=502,
        detail="No requirements could be fetched from the live source or the store.",
    )


@app.get("/requirements/{celex}", response_model=Requirement)
def get_requirement(celex: str) -> Requirement:
    """Fetch a single requirement by CELEX (must be on the watchlist)."""
    family = next((f for f, c in WATCHLIST.items() if c == celex), None)
    if family is None:
        raise HTTPException(
            status_code=404,
            detail=f"CELEX {celex!r} is not on the watchlist: {sorted(WATCHLIST.values())}",
        )
    reqs = fetch_requirements(get_settings(), families=[family])
    if not reqs:
        raise HTTPException(status_code=502, detail=f"Could not fetch {celex} from CELLAR.")
    return reqs[0]


@app.get("/requirements/{celex}/similar")
async def similar_requirements(celex: str, limit: int = 5) -> list[dict[str, Any]]:
    """TRIAGE ONLY — stored obligations semantically near this one (pgvector).

    Never part of the decision path: findings are computed from relational
    columns alone, and deleting the vector index leaves them identical.
    """
    settings = get_settings()
    if not settings.database_url:
        raise HTTPException(
            status_code=503, detail="Similarity triage requires the obligation store."
        )
    from storage.db import get_sessionmaker
    from storage.similarity import find_similar_obligations

    try:
        maker = get_sessionmaker(settings.database_url)
        async with maker() as session:
            neighbors = await find_similar_obligations(session, celex, limit=limit)
    except KeyError:
        raise HTTPException(
            status_code=404, detail=f"No stored in-force obligation for CELEX {celex!r}."
        ) from None
    return [
        {
            "requirement": item["requirement"].model_dump(mode="json"),
            "distance": item["distance"],
        }
        for item in neighbors
    ]
