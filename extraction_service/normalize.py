"""Normalize raw scraped data into the ``Requirement`` contract.

This module owns the output contract for Part 1. It maps free-text fields from
live sources (EUR-Lex titles, ECHA substance names, HTML notices) onto the
controlled vocabulary declared in ``contracts/models.py`` (the single source of
truth), and stamps the mandatory provenance metadata on every record.

Anything that cannot be mapped to a known enum is dropped (categories /
substances) or defaulted to ``"other"`` (regulation family) rather than
inventing a new taxonomy key — see AGENTS.md §13.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, get_args

from contracts.models import (
    ProductCategory,
    RegulationFamily,
    Requirement,
    RequirementScope,
    Substance,
)

# Valid enum values, derived directly from the contract Literals so this module
# can never drift from the models.
KNOWN_CATEGORIES: frozenset[str] = frozenset(get_args(ProductCategory))
KNOWN_SUBSTANCES: frozenset[str] = frozenset(get_args(Substance))
KNOWN_FAMILIES: frozenset[str] = frozenset(get_args(RegulationFamily))

# Aliases for mapping messy source text onto canonical taxonomy keys.
_FAMILY_ALIASES: dict[str, RegulationFamily] = {
    "battery regulation": "battery",
    "batteries": "battery",
    "battery": "battery",
    "reach": "reach",
    "rohs": "rohs",
    "weee": "weee",
    "ppwr": "ppwr",
    "packaging": "ppwr",
    "gpsr": "gpsr",
    "general product safety": "gpsr",
    "red": "red",
    "radio equipment": "red",
    "espr": "espr",
    "ecodesign": "espr",
    "toy safety": "toy_safety",
    "toy_safety": "toy_safety",
    "mdr": "mdr",
    "medical device": "mdr",
    "pops": "pops",
}

_SUBSTANCE_ALIASES: dict[str, Substance] = {
    "pfhxa": "PFAS_PFHxA",
    "pfas": "PFAS_PFHxA",
    "pfas_pfhxa": "PFAS_PFHxA",
    "perfluorohexanoic acid": "PFAS_PFHxA",
    "dehp": "DEHP",
    "di(2-ethylhexyl) phthalate": "DEHP",
    "bpa": "BPA",
    "bisphenol a": "BPA",
    "mercury": "mercury",
    "hg": "mercury",
    "lead": "lead",
    "pb": "lead",
    "cadmium": "cadmium",
    "cd": "cadmium",
    "decabde": "decaBDE",
    "tbbpa": "TBBPA",
    "mccp": "MCCP",
    "1,4-dioxane": "dioxane",
    "dioxane": "dioxane",
    "hexavalent chromium": "chromium_vi",
    "chromium vi": "chromium_vi",
    "chromium_vi": "chromium_vi",
}


class NormalizationError(ValueError):
    """Raised when a raw record cannot be turned into a valid Requirement."""


def _coerce_date(value: Any) -> date | None:
    """Parse a date from an ISO string / ``date`` / ``datetime``; ``None`` if absent."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise NormalizationError(f"Unparseable date: {value!r}")


def map_family(value: str | None) -> RegulationFamily:
    """Map a source family string onto a taxonomy regulation-family key.

    Unknown families fall back to ``"other"`` (a valid enum value).
    """
    if not value:
        return "other"
    key = value.strip().lower()
    if key in KNOWN_FAMILIES:
        return key  # type: ignore[return-value]
    return _FAMILY_ALIASES.get(key, "other")


def map_categories(values: Any) -> list[ProductCategory] | str:
    """Map source category strings onto taxonomy keys.

    Returns the literal ``"all"`` when the scope is universal, otherwise the
    list of recognised categories (unknown ones are dropped).
    """
    if values == "all":
        return "all"
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    mapped: list[ProductCategory] = []
    for raw in values:
        key = str(raw).strip().lower()
        if key in KNOWN_CATEGORIES:
            mapped.append(key)  # type: ignore[arg-type]
    return mapped


def map_substances(values: Any) -> list[Substance]:
    """Map source substance strings onto taxonomy substance keys (unknown dropped)."""
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    mapped: list[Substance] = []
    for raw in values:
        token = str(raw).strip()
        if token in KNOWN_SUBSTANCES:
            mapped.append(token)  # type: ignore[arg-type]
            continue
        alias = _SUBSTANCE_ALIASES.get(token.lower())
        if alias:
            mapped.append(alias)
    # de-dup while preserving order
    seen: set[str] = set()
    out: list[Substance] = []
    for s in mapped:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def normalize_update(
    raw: dict[str, Any],
    *,
    source: str,
    source_url: str,
    access_timestamp: datetime | None = None,
    celex: str | None = None,
    consolidation_date: date | str | None = None,
) -> Requirement:
    """Turn one raw scraped record into a validated :class:`Requirement`.

    ``raw`` is expected to look like a rule-update record (the ``Requirement``
    field names, minus provenance). Provenance (``source_url`` and
    ``access_timestamp``) is mandatory and stamped here.
    """
    if not source_url:
        raise NormalizationError("source_url is mandatory — no source, no requirement")

    raw_scope = raw.get("scope") or {}
    scope = RequirementScope(
        categories=map_categories(raw_scope.get("categories")),
        substances=map_substances(raw_scope.get("substances")),
        markets=list(raw_scope.get("markets") or []),
        conditions=raw_scope.get("conditions") or "",
    )

    ts = access_timestamp or datetime.now(UTC)

    return Requirement(
        update_id=raw["update_id"],
        published_date=_coerce_date(raw.get("published_date")) or ts.date(),
        source=source,
        source_url=source_url,
        celex=celex if celex is not None else raw.get("celex"),
        consolidation_date=_coerce_date(consolidation_date),
        access_timestamp=ts,
        regulation_family=map_family(raw.get("regulation_family")),
        reference=raw.get("reference"),
        title=raw["title"],
        summary=raw.get("summary"),
        change_type=raw.get("change_type", "new"),
        effective_date=_coerce_date(raw.get("effective_date")),
        deadline_date=_coerce_date(raw.get("deadline_date")),
        severity=raw.get("severity", "medium"),
        action_required=raw.get("action_required"),
        scope=scope,
        corrects=raw.get("corrects"),
    )
