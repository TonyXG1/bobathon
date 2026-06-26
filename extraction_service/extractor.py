"""Live extraction: query CELLAR for the watchlist regulations and normalize.

No database — each call fetches fresh metadata from the live EUR-Lex / CELLAR
SPARQL endpoint and returns a list of :class:`Requirement` objects. The
``source_url`` on every record points at the real EUR-Lex document, satisfying
the provenance non-negotiable (AGENTS.md §1).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from clients import CellarClient
from config import Settings, get_settings
from normalize import normalize_update

from contracts.models import RegulationFamily, Requirement

logger = logging.getLogger(__name__)

# Keep concurrent connections to CELLAR polite (SOURCES.md §7.2: < 5).
MAX_WORKERS = 5

# Watchlist: regulation family → original CELEX (AGENTS.md §6.2 / SOURCES.md §3).
WATCHLIST: dict[RegulationFamily, str] = {
    "rohs": "32011L0065",
    "reach": "32006R1907",
    "weee": "32012L0019",
    "battery": "32023R1542",
    "ppwr": "32025R0040",
    "gpsr": "32023R0988",
    "red": "32014L0053",
    "espr": "32024R1781",
    "toy_safety": "32009L0048",
    "mdr": "32017R0745",
    "pops": "32019R1021",
}


def _build_requirement(family: RegulationFamily, celex: str, meta: dict[str, str]) -> Requirement:
    """Turn one CELLAR metadata row into a validated Requirement."""
    raw = {
        "update_id": f"REQ-{celex}",
        "published_date": meta.get("date"),
        "regulation_family": family,
        "title": meta.get("title") or f"{family.upper()} ({celex})",
        "summary": meta.get("title"),
        "change_type": "new",
        "severity": "medium",
        "scope": {"categories": "all", "substances": [], "markets": ["EU"]},
    }
    return normalize_update(
        raw,
        source="EUR-Lex",
        source_url=CellarClient.document_url(celex),
        access_timestamp=datetime.now(UTC),
        celex=celex,
    )


def fetch_requirements(
    settings: Settings | None = None,
    *,
    families: list[str] | None = None,
    client: CellarClient | None = None,
) -> list[Requirement]:
    """Fetch live requirements for the watchlist (optionally filtered by family).

    A per-regulation failure (timeout, missing CELEX) is logged and skipped so
    one bad source never aborts the whole run.
    """
    settings = settings or get_settings()
    wanted = {f.lower() for f in families} if families else None
    targets = [(f, c) for f, c in WATCHLIST.items() if wanted is None or f in wanted]

    owns = client is None
    cellar = client or CellarClient(settings=settings)

    def _fetch_one(item: tuple[RegulationFamily, str]) -> Requirement | None:
        family, celex = item
        try:
            meta = cellar.get_metadata(celex)
            if not meta:
                logger.warning("No CELLAR metadata for %s (%s)", family, celex)
                return None
            return _build_requirement(family, celex, meta)
        except Exception as exc:  # noqa: BLE001 - per-source resilience
            logger.warning("Live fetch failed for %s (%s): %s", family, celex, exc)
            return None

    try:
        # Fetch concurrently but keep <= MAX_WORKERS connections (be a polite
        # client — SOURCES.md §7.2). httpx.Client is thread-safe.
        workers = max(1, min(MAX_WORKERS, len(targets)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fetched = list(pool.map(_fetch_one, targets))
    finally:
        if owns:
            cellar.close()

    # Preserve watchlist order; drop failures.
    return [r for r in fetched if r is not None]
