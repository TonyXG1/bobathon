"""Gap-assessment engine.

Matches each portfolio product against a small set of **deterministic gap
rules** and emits one :class:`Finding` per (product × matched rule). Each rule
encodes the applicability predicate from AGENTS.md §2.2
(market ∧ category ∧ substance ∧ attribute ∧ ¬exclusion) for one concrete
obligation, and is tied to a regulation *family*.

Provenance: a rule only fires when the live ``Requirement`` for its family is
present in the input — the resulting Finding cites that requirement's
``source_url`` (no source → no finding, AGENTS.md non-negotiable).

The rules are written to re-derive the 5 seeded gaps in ``partners.json`` and
the analogous gaps elsewhere, while avoiding the documented look-alikes
(wrong market, absent substance, out-of-scope attribute).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from portfolio import in_eu_market

from contracts.models import Alert, Finding, RegulationFamily, Requirement

Predicate = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True)
class GapRule:
    """One concrete obligation and the predicate that detects a gap."""

    rule_id: str
    family: RegulationFamily
    regulation: str  # human label incl. article
    requirement: str  # what the rule requires, one sentence
    gap: str  # why the product is non-compliant
    recommended_action: str
    deadline: date
    severity: str  # low | medium | high
    predicate: Predicate


def _has(substance: str) -> Predicate:
    return lambda p: substance in (p.get("substances") or [])


RULES: list[GapRule] = [
    GapRule(
        rule_id="rohs-mercury",
        family="rohs",
        regulation="EU RoHS Directive 2011/65/EU — Annex II (mercury restriction)",
        requirement="Lighting and displays must not contain mercury above 0.1% (CCFL exemption expired).",
        gap="Product still contains mercury, a RoHS Annex II restricted substance.",
        recommended_action="Replace the mercury-containing component (e.g. CCFL backlight) with a compliant LED alternative.",
        deadline=date(2024, 12, 31),
        severity="high",
        predicate=lambda p: (
            _has("mercury")(p)
            and p.get("category") in {"display", "led_lighting"}
            and in_eu_market(p)
        ),
    ),
    GapRule(
        rule_id="reach-pfas",
        family="reach",
        regulation="EU REACH Regulation (EC) 1907/2006 — Annex XVII (PFHxA/PFAS restriction)",
        requirement="PFHxA and related PFAS are restricted in textile coatings and treated articles.",
        gap="Product uses a PFAS/PFHxA coating now restricted under REACH.",
        recommended_action="Reformulate the coating to a PFAS-free alternative and update the technical file.",
        deadline=date(2025, 2, 25),
        severity="high",
        predicate=lambda p: _has("PFAS_PFHxA")(p) and in_eu_market(p),
    ),
    GapRule(
        rule_id="toy-dehp",
        family="toy_safety",
        regulation="EU Toy Safety Directive 2009/48/EC — Annex II (phthalate limits)",
        requirement="Toys must not contain DEHP above the tightened phthalate limit.",
        gap="Toy contains DEHP above the permitted limit for toys.",
        recommended_action="Substitute DEHP-plasticised parts with compliant materials and re-test to EN 71-3.",
        deadline=date(2025, 7, 20),
        severity="high",
        predicate=lambda p: p.get("intended_use") == "toy" and _has("DEHP")(p) and in_eu_market(p),
    ),
    GapRule(
        rule_id="battery-passport",
        family="battery",
        regulation="EU Battery Regulation 2023/1542 — battery passport (Art. 77)",
        requirement="LMT and industrial batteries must carry an EU battery passport with a data carrier (QR).",
        gap="LMT/industrial battery ships without an EU battery passport / data carrier.",
        recommended_action="Generate the battery passport, attach a QR/data-matrix carrier, and register the dataset.",
        deadline=date(2027, 2, 18),
        severity="high",
        predicate=lambda p: p.get("battery_type") in {"lmt", "industrial"} and in_eu_market(p),
    ),
    GapRule(
        rule_id="gpsr-button-cell",
        family="gpsr",
        regulation="EU GPSR Regulation 2023/988 — child-resistant button-cell compartments",
        requirement="Toys with button/coin cells must have child-resistant battery compartments.",
        gap="Toy's button-cell compartment is not secured against child access.",
        recommended_action="Redesign the compartment to require a tool or two independent actions to open.",
        deadline=date(2024, 12, 13),
        severity="high",
        predicate=lambda p: (
            p.get("intended_use") == "toy"
            and p.get("battery_type") == "button_cell"
            and in_eu_market(p)
        ),
    ),
    GapRule(
        rule_id="red-common-charger",
        family="red",
        regulation="EU RED Directive 2014/53/EU — common charger (Art. 3.4)",
        requirement="Rechargeable portable devices must use USB-C; micro-USB is no longer permitted.",
        gap="Rechargeable device still uses a micro-USB charging port instead of USB-C.",
        recommended_action="Switch the charging port to USB-C and update conformity documentation.",
        deadline=date(2024, 12, 28),
        severity="medium",
        predicate=lambda p: (
            p.get("connector") == "micro_usb" and bool(p.get("has_battery")) and in_eu_market(p)
        ),
    ),
]


def _requirements_by_family(
    requirements: Iterable[Requirement],
) -> dict[str, Requirement]:
    """Index live requirements by family, skipping correction/duplicate entries.

    If several requirements share a family, the first non-corrected one wins.
    """
    out: dict[str, Requirement] = {}
    for req in requirements:
        if req.corrects:  # de-dup: corrections add no new obligation
            continue
        out.setdefault(req.regulation_family, req)
    return out


def _alert_recipient(
    channel: str, partner: dict[str, Any], *, test_number: str, test_email: str
) -> str:
    """Recipient for the alert.

    Email alerts go to the partner's own contact email (their preferred inbox);
    SMS/WhatsApp go to OUR test number. In this dataset all partner emails are
    synthetic test addresses, so this stays safe for the demo.
    """
    if channel == "email":
        return partner.get("contact", {}).get("email") or test_email
    return test_number


def _build_finding(
    partner: dict[str, Any],
    product: dict[str, Any],
    rule: GapRule,
    req: Requirement,
    *,
    test_number: str,
    test_email: str,
) -> Finding:
    company = partner["company"]
    channel = partner.get("contact", {}).get("preferred_channel", "email")
    deadline = req.deadline_date or rule.deadline
    source_url = req.source_url

    message = (
        f"[{company}] {product['name']}: {rule.gap} "
        f"Deadline {deadline.isoformat()}. Action: {rule.recommended_action} "
        f"Source: {source_url}"
    )

    return Finding(
        company=company,
        partner_id=partner["partner_id"],
        product_id=product["product_id"],
        product=product["name"],
        regulation=rule.regulation,
        requirement=rule.requirement,
        source_url=source_url,
        gap=rule.gap,
        deadline=deadline,
        severity=rule.severity,
        recommended_action=rule.recommended_action,
        alert=Alert(
            channel=channel,
            to=_alert_recipient(
                channel, partner, test_number=test_number, test_email=test_email
            ),
            message=message,
        ),
    )


def assess(
    requirements: Iterable[Requirement],
    partners: list[dict[str, Any]],
    *,
    test_number: str = "+10000000000",
    test_email: str = "alerts-test@example.com",
) -> list[Finding]:
    """Assess the portfolio against the live requirements; return Finding[].

    One Finding per (product × matched rule), but only for rules whose
    regulation family is present in ``requirements`` (so every Finding cites a
    live ``source_url``).
    """
    req_by_family = _requirements_by_family(requirements)
    findings: list[Finding] = []
    for partner in partners:
        for product in partner.get("products", []):
            for rule in RULES:
                req = req_by_family.get(rule.family)
                if req is None:
                    continue  # no live source for this family → no finding
                if rule.predicate(product):
                    findings.append(
                        _build_finding(
                            partner,
                            product,
                            rule,
                            req,
                            test_number=test_number,
                            test_email=test_email,
                        )
                    )
    return findings
