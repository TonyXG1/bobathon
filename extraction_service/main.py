"""Extraction Service (Part 1) — FastAPI app (simplified, live, no database).

Every request queries the live EUR-Lex / CELLAR SPARQL endpoint and returns the
normalized requirements directly.

Endpoints:
* ``GET /health``                — liveness probe.
* ``GET /requirements``          — live list of watchlist requirements.
                                   Optional ``?family=battery&family=reach`` filter.
* ``GET /requirements/{celex}``  — one requirement by CELEX.
"""

from __future__ import annotations

import logging

from config import get_settings
from extractor import WATCHLIST, fetch_requirements
from fastapi import FastAPI, HTTPException, Query
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


@app.get("/requirements", response_model=list[Requirement])
def list_requirements(
    family: list[str] | None = Query(  # noqa: B008 - FastAPI dependency-injection idiom
        default=None,
        description="Filter by regulation family (repeatable), e.g. battery, reach, rohs.",
    ),
) -> list[Requirement]:
    """Fetch the watchlist requirements live from CELLAR."""
    reqs = fetch_requirements(get_settings(), families=family)
    if not reqs:
        raise HTTPException(
            status_code=502,
            detail="No requirements could be fetched from the live source.",
        )
    return reqs


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
