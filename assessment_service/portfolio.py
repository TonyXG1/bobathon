"""Load and index the fixed partner portfolio (``dataset/partners.json``).

The portfolio is read-only input. We expose it as plain dicts plus a couple of
small helpers; the matching logic lives in ``engine.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# The EU expands to all 27 member states (taxonomy.json markets_note).
EU_MEMBER_STATES: frozenset[str] = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
    }
)


def load_partners(path: str | Path) -> list[dict[str, Any]]:
    """Load the portfolio. Returns the list of partner dicts."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("partners", [])


def iter_products(partners: list[dict[str, Any]]):
    """Yield ``(partner, product)`` pairs across the portfolio."""
    for partner in partners:
        for product in partner.get("products", []):
            yield partner, product


def in_eu_market(product: dict[str, Any]) -> bool:
    """True if the product is placed on the EU market.

    ``EU`` expands to all 27 states; an explicit member-state code also counts.
    A UK/US-only SKU is therefore *not* in scope for EU rules (look-alike guard).
    """
    markets = set(product.get("markets") or [])
    if "EU" in markets:
        return True
    return bool(markets & EU_MEMBER_STATES)
