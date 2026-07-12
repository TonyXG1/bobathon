"""Assessment Service (Part 2) — FastAPI app.

Takes the current requirements, matches them against the fixed portfolio, and
returns gaps as ``Finding[]`` (Part 3/4 input).

Requirements come from the obligation store (Postgres) when ``DATABASE_URL``
is configured — the store is the system of record and the ONLY input to the
matcher — falling back to the extraction HTTP API when it is not. The matcher
itself (``engine.assess``) is unchanged either way, and produced findings are
persisted for audit (best-effort, never failing the response).

Endpoints:
* ``GET  /health``   — liveness probe.
* ``POST /assess``   — assess. Body may carry ``requirements``; if omitted, the
                       service reads the obligation store (or fetches live).
* ``GET  /findings`` — run the full pipeline (obligation store / live → assess).
"""

from __future__ import annotations

import logging

import httpx
from config import Settings, get_settings
from engine import RULES, assess
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from portfolio import load_partners
from pydantic import BaseModel

from contracts.models import Finding, Requirement

# 1:1 today: each gap rule has a distinct human regulation label.
RULE_ID_BY_REGULATION = {rule.regulation: rule.rule_id for rule in RULES}

logging.basicConfig(level=get_settings().log_level.upper())
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Regulatory Radar — Assessment Service",
    description="Match live regulatory requirements against the portfolio to find compliance gaps.",
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


class AssessRequest(BaseModel):
    """Optional body for ``POST /assess``."""

    requirements: list[Requirement] | None = None
    families: list[str] | None = None


def fetch_requirements_from_extraction(settings: Settings) -> list[Requirement]:
    """Fetch the live requirements from the extraction service over HTTP."""
    url = f"{settings.extraction_service_url.rstrip('/')}/requirements"
    resp = httpx.get(url, timeout=settings.http_timeout)
    resp.raise_for_status()
    return [Requirement.model_validate(item) for item in resp.json()]


async def fetch_requirements_from_store(settings: Settings) -> list[Requirement] | None:
    """Read the in-force obligations from the store (layer 1, system of record).

    Returns ``None`` when no database is configured/reachable or the store is
    empty, so the caller falls back to the extraction HTTP path.
    """
    if not settings.database_url:
        return None
    try:
        from storage import repository
        from storage.db import get_sessionmaker
    except ImportError:
        logger.warning("storage package deps not installed — falling back to HTTP")
        return None
    try:
        maker = get_sessionmaker(settings.database_url)
        async with maker() as session:
            requirements = await repository.get_in_force_requirements(session)
    except Exception as exc:  # noqa: BLE001 - degrade to the HTTP path on any DB failure
        logger.warning("Obligation store unavailable (%s) — falling back to HTTP", exc)
        return None
    return requirements or None


async def persist_findings(settings: Settings, findings: list[Finding]) -> None:
    """Audit trail: one row per finding with the rule that fired. Best-effort —

    a persistence failure is logged and never alters or fails the response.
    """
    if not settings.database_url or not findings:
        return
    try:
        from storage import repository
        from storage.db import get_sessionmaker

        maker = get_sessionmaker(settings.database_url)
        async with maker() as session:
            await repository.save_findings(session, findings, RULE_ID_BY_REGULATION)
    except Exception as exc:  # noqa: BLE001 - audit is best-effort by spec
        logger.warning("Could not persist findings for audit: %s", exc)


async def _get_requirements(settings: Settings) -> list[Requirement]:
    requirements = await fetch_requirements_from_store(settings)
    if requirements is not None:
        return requirements
    try:
        return fetch_requirements_from_extraction(settings)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch requirements from extraction service: {exc}",
        ) from exc


def _run(settings: Settings, requirements: list[Requirement]) -> list[Finding]:
    partners = load_partners(settings.partners_path)
    return assess(
        requirements,
        partners,
        test_number=settings.twilio_test_number,
        test_email=settings.twilio_test_email,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "assessment"}


@app.post("/assess", response_model=list[Finding])
async def assess_endpoint(body: AssessRequest | None = None) -> list[Finding]:
    settings = get_settings()
    requirements = body.requirements if body else None
    if requirements is None:
        requirements = await _get_requirements(settings)
    findings = _run(settings, requirements)
    await persist_findings(settings, findings)
    return findings


@app.get("/findings", response_model=list[Finding])
async def findings_endpoint() -> list[Finding]:
    """Full pipeline: obligation store (or live extraction) → assess."""
    settings = get_settings()
    requirements = await _get_requirements(settings)
    findings = _run(settings, requirements)
    await persist_findings(settings, findings)
    return findings
