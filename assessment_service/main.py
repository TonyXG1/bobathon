"""Assessment Service (Part 2) — FastAPI app (simplified, no database).

Takes the live requirements (Part 1 output), matches them against the fixed
portfolio, and returns gaps as ``Finding[]`` (Part 3/4 input).

Endpoints:
* ``GET  /health``   — liveness probe.
* ``POST /assess``   — assess. Body may carry ``requirements``; if omitted, the
                       service fetches them live from the extraction service.
* ``GET  /findings`` — run the full pipeline (fetch live extraction → assess).
"""

from __future__ import annotations

import logging

import httpx
from config import Settings, get_settings
from engine import assess
from fastapi import FastAPI, HTTPException
from portfolio import load_partners
from pydantic import BaseModel

from contracts.models import Finding, Requirement

logging.basicConfig(level=get_settings().log_level.upper())
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Regulatory Radar — Assessment Service",
    description="Match live regulatory requirements against the portfolio to find compliance gaps.",
    version="0.2.0",
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
def assess_endpoint(body: AssessRequest | None = None) -> list[Finding]:
    settings = get_settings()
    requirements = body.requirements if body else None
    if requirements is None:
        try:
            requirements = fetch_requirements_from_extraction(settings)
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Could not fetch requirements from extraction service: {exc}",
            ) from exc
    return _run(settings, requirements)


@app.get("/findings", response_model=list[Finding])
def findings_endpoint() -> list[Finding]:
    """Full pipeline: fetch live requirements from extraction, then assess."""
    settings = get_settings()
    try:
        requirements = fetch_requirements_from_extraction(settings)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch requirements from extraction service: {exc}",
        ) from exc
    return _run(settings, requirements)
