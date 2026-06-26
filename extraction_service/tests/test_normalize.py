"""Tests for normalization & taxonomy mapping (normalize.py)."""

from datetime import UTC, date, datetime

import pytest
from normalize import (
    NormalizationError,
    map_categories,
    map_family,
    map_substances,
    normalize_update,
)

from contracts.models import Requirement


def test_map_family_known_and_alias_and_unknown():
    assert map_family("battery") == "battery"
    assert map_family("Battery Regulation") == "battery"
    assert map_family("REACH") == "reach"
    assert map_family("something weird") == "other"
    assert map_family(None) == "other"


def test_map_categories_all_and_filtering():
    assert map_categories("all") == "all"
    assert map_categories(["emobility_battery", "not_a_real_category"]) == ["emobility_battery"]
    assert map_categories(None) == []
    assert map_categories("display") == ["display"]


def test_map_substances_canonicalizes_and_dedupes():
    assert map_substances(["PFAS_PFHxA"]) == ["PFAS_PFHxA"]
    assert map_substances(["pfhxa", "PFAS"]) == ["PFAS_PFHxA"]  # alias + dedupe
    assert map_substances(["Mercury", "Hg"]) == ["mercury"]
    assert map_substances(["unobtanium"]) == []
    assert map_substances([]) == []


def test_normalize_update_produces_valid_requirement_with_provenance():
    raw = {
        "update_id": "REG-26-001",
        "published_date": "2024-01-15",
        "regulation_family": "Battery Regulation",
        "reference": "Article 77",
        "title": "Battery passport requirement",
        "summary": "LMT/industrial batteries need a passport",
        "change_type": "new",
        "effective_date": "2024-02-18",
        "deadline_date": "2027-02-18",
        "severity": "high",
        "action_required": "Implement battery passport",
        "scope": {
            "categories": ["emobility_battery"],
            "substances": [],
            "markets": ["EU"],
            "conditions": "LMT and industrial only",
        },
    }
    ts = datetime(2024, 1, 20, 10, 0, tzinfo=UTC)
    req = normalize_update(
        raw,
        source="EUR-Lex",
        source_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1542",
        access_timestamp=ts,
        celex="32023R1542",
        consolidation_date="2024-01-01",
    )
    assert isinstance(req, Requirement)
    assert req.source_url.endswith("32023R1542")
    assert req.celex == "32023R1542"
    assert req.consolidation_date == date(2024, 1, 1)
    assert req.access_timestamp == ts
    assert req.regulation_family == "battery"
    assert req.scope.categories == ["emobility_battery"]
    assert req.deadline_date == date(2027, 2, 18)


def test_normalize_update_requires_source_url():
    raw = {"update_id": "X", "title": "Y", "regulation_family": "battery"}
    with pytest.raises(NormalizationError):
        normalize_update(raw, source="EUR-Lex", source_url="")


def test_normalize_update_defaults_published_date_to_access_date():
    raw = {"update_id": "X", "title": "Y", "regulation_family": "rohs"}
    ts = datetime(2025, 6, 1, tzinfo=UTC)
    req = normalize_update(raw, source="EUR-Lex", source_url="https://x", access_timestamp=ts)
    assert req.published_date == date(2025, 6, 1)
    assert req.change_type == "new"
    assert req.severity == "medium"


def test_normalize_update_drops_unknown_scope_categories():
    raw = {
        "update_id": "X",
        "title": "Y",
        "regulation_family": "rohs",
        "scope": {"categories": ["display", "bogus_cat"], "markets": ["DE"]},
    }
    req = normalize_update(raw, source="EUR-Lex", source_url="https://x")
    assert req.scope.categories == ["display"]
    assert req.scope.markets == ["DE"]
