"""Engine tests — run the matcher against the real portfolio.

Validates the 5 seeded ground-truth gaps are re-derived and the documented
look-alikes are NOT flagged.
"""

from datetime import UTC, date, datetime

import pytest
from config import DEFAULT_PARTNERS_PATH
from engine import RULES, assess
from portfolio import load_partners

from contracts.models import Requirement, RequirementScope

# The families the engine has rules for.
FAMILIES = sorted({rule.family for rule in RULES})


def _req(family: str) -> Requirement:
    return Requirement(
        update_id=f"REQ-{family}",
        published_date=date(2024, 1, 1),
        source="EUR-Lex",
        source_url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{family}",
        access_timestamp=datetime.now(UTC),
        regulation_family=family,
        title=f"{family} requirement",
        change_type="new",
        severity="high",
        scope=RequirementScope(categories="all", markets=["EU"]),
    )


@pytest.fixture
def partners():
    return load_partners(DEFAULT_PARTNERS_PATH)


@pytest.fixture
def all_requirements():
    return [_req(f) for f in FAMILIES]


def _by_product(findings):
    out: dict[str, list] = {}
    for f in findings:
        out.setdefault(f.product_id, []).append(f)
    return out


def test_assess_detects_all_five_seeded_gaps(partners, all_requirements):
    findings = assess(all_requirements, partners)
    by_product = _by_product(findings)

    # P006 FitTrack — PFAS/PFHxA (REACH)
    assert any("REACH" in f.regulation for f in by_product.get("P006-A", []))
    # P008 PlayBright — DEHP toy limit + button-cell (GPSR)
    assert any("Toy Safety" in f.regulation for f in by_product.get("P008-A", []))
    assert any("GPSR" in f.regulation for f in by_product.get("P008-B", []))
    # P010 DisplayOne — mercury (RoHS)
    assert any("RoHS" in f.regulation for f in by_product.get("P010-B", []))
    # P013 RideVolt — missing battery passport
    assert any("Battery Regulation" in f.regulation for f in by_product.get("P013-A", []))
    # P022 KidVision — micro-USB (RED common charger)
    assert any("common charger" in f.regulation for f in by_product.get("P022-A", []))


def test_assess_total_count_is_stable(partners, all_requirements):
    findings = assess(all_requirements, partners)
    # 1 mercury + 2 pfas + 4 toy-dehp + 4 battery + 3 button-cell + 1 micro-usb
    assert len(findings) == 15


def test_lookalikes_are_not_flagged(partners, all_requirements):
    findings = assess(all_requirements, partners)
    flagged = {f.product_id for f in findings}

    # Portable battery is out of scope for the LMT/industrial passport rule.
    assert "P003-A" not in flagged
    assert "P021-A" not in flagged and "P021-C" not in flagged
    # micro-USB but NO battery → not a common-charger gap (P005-B).
    assert "P005-B" not in flagged
    # DEHP present but product is consumer lighting, not a toy (P001-B).
    assert "P001-B" not in flagged
    # Wrong market: UK-only and US-only SKUs never match EU rules.
    assert "P014-C" not in flagged  # UK router
    assert "P016-B" not in flagged  # US 3D printer with lead


def test_inferred_gaps_beyond_the_seeded_five(partners, all_requirements):
    findings = assess(all_requirements, partners)
    flagged = {f.product_id for f in findings}
    # Industrial batteries also need a passport (not just the seeded P013).
    assert "P003-B" in flagged
    assert "P021-B" in flagged
    # PFAS also appears on the SkyScout drone.
    assert "P017-A" in flagged


def test_p008b_has_two_distinct_findings(partners, all_requirements):
    findings = assess(all_requirements, partners)
    p008b = [f for f in findings if f.product_id == "P008-B"]
    regs = {f.regulation for f in p008b}
    # Both the toy-DEHP gap and the button-cell GPSR gap.
    assert len(p008b) == 2
    assert any("Toy Safety" in r for r in regs)
    assert any("GPSR" in r for r in regs)


def test_every_finding_cites_source_and_has_deadline(partners, all_requirements):
    findings = assess(all_requirements, partners)
    assert findings
    for f in findings:
        assert f.source_url.startswith("http")  # provenance non-negotiable
        assert isinstance(f.deadline, date)


def test_alert_recipient_routing(partners, all_requirements):
    findings = assess(
        all_requirements, partners, test_number="+15550000000", test_email="me@test.example"
    )
    for f in findings:
        if f.alert.channel == "email":
            # email goes to the partner's own contact inbox
            assert "@" in f.alert.to
        else:
            # sms/whatsapp go to OUR test number
            assert f.alert.to == "+15550000000"


def test_email_alert_targets_changed_partner(partners, all_requirements):
    findings = assess(all_requirements, partners)
    # P010 DisplayOne's contact email was pointed at our test address.
    p010 = [f for f in findings if f.product_id == "P010-B"]
    assert p010 and p010[0].alert.channel == "email"
    assert p010[0].alert.to == "antonsttum@gmail.com"


def test_no_findings_for_family_without_a_requirement(partners):
    # Only supply the battery requirement → only battery-passport gaps appear.
    findings = assess([_req("battery")], partners)
    assert findings
    assert {f.regulation for f in findings} == {
        "EU Battery Regulation 2023/1542 — battery passport (Art. 77)"
    }
