"""
Pydantic models for the two core contracts.

These models are the SINGLE source of truth. JSON schemas are generated from them.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ============================================================================
# ENUMS — kept in sync with dataset/taxonomy.json (the authoritative
# vocabulary). If taxonomy.json changes, update these Literals and re-run
# export_schemas.py in the same change.
# ============================================================================

ProductCategory = Literal[
    "audio",
    "battery_pack",
    "camera",
    "charging_equipment",
    "computing",
    "display",
    "drone",
    "emobility_battery",
    "gaming",
    "industrial_equipment",
    "iot_sensor",
    "led_lighting",
    "medical_wearable",
    "networking",
    "smartphone",
    "toy_electronic",
    "wearable",
]

Substance = Literal[
    "lead",
    "cadmium",
    "mercury",
    "chromium_vi",
    "PBB",
    "PBDE",
    "DEHP",
    "BPA",
    "decaBDE",
    "TBBPA",
    "MCCP",
    "PFAS_PFHxA",
    "dioxane",
]

RegulationFamily = Literal[
    "rohs",
    "reach",
    "weee",
    "battery",
    "ppwr",
    "gpsr",
    "red",
    "espr",
    "toy_safety",
    "mdr",
    "pops",
    "epr",
    "epr_packaging",
    "energy_label",
    "emc",
    "lvd",
    "machinery",
    "atex",
    "chemical_safety",
    "cybersecurity",
    # Extraction-side fallback for live rules that map to no taxonomy family
    # (normalize.map_family defaults unknown families here instead of guessing).
    "other",
]

ChangeType = Literal["new", "amendment", "correction"]

Severity = Literal["low", "medium", "high"]

Channel = Literal["email", "sms", "whatsapp"]


# ============================================================================
# REQUIREMENT (Part 1 output, Part 2 input)
# ============================================================================


class RequirementScope(BaseModel):
    """Scope of a regulatory requirement."""

    categories: list[ProductCategory] | Literal["all"] = Field(
        description="Product categories in scope, or 'all' for all categories"
    )
    substances: list[Substance] = Field(
        default_factory=list,
        description="Substances named in the requirement (empty if none)",
    )
    markets: list[str] = Field(
        description="Markets where requirement applies (ISO country codes, 'EU' = all 27 states)"
    )
    conditions: str = Field(
        default="",
        description="Free-text conditions and carve-outs (e.g., 'LMT and industrial batteries only')",
    )


class Requirement(BaseModel):
    """
    A regulatory requirement from a live source.

    Output of Part 1 (extraction service), input of Part 2 (assessment service).
    """

    # Identification
    update_id: str = Field(description="Unique identifier for this requirement")
    published_date: date = Field(description="When the requirement was published")

    # Source & Provenance (MANDATORY)
    source: str = Field(description="Source name (e.g., 'EUR-Lex', 'ECHA')")
    source_url: str = Field(
        description="Live portal URL where this requirement was read (MANDATORY)"
    )
    celex: str | None = Field(default=None, description="CELEX number (for EUR-Lex documents)")
    consolidation_date: date | None = Field(
        default=None, description="Consolidation date of the act"
    )
    access_timestamp: datetime = Field(description="When we fetched this requirement (UTC)")

    # Classification
    regulation_family: RegulationFamily = Field(
        description="Regulation family (from taxonomy.json)"
    )
    reference: str | None = Field(default=None, description="Legal reference (article/annex)")

    # Content
    title: str = Field(description="Human-readable title")
    summary: str | None = Field(default=None, description="Brief summary")
    change_type: ChangeType = Field(description="Type of change (new/amendment/correction)")

    # Dates
    effective_date: date | None = Field(
        default=None, description="When the requirement becomes effective"
    )
    deadline_date: date | None = Field(default=None, description="Compliance deadline")

    # Impact
    severity: Severity = Field(description="Severity level (low/medium/high)")
    action_required: str | None = Field(
        default=None, description="What action is required to comply"
    )

    # Scope
    scope: RequirementScope = Field(description="Scope of the requirement")

    # De-duplication
    corrects: str | None = Field(
        default=None,
        description="If present, the update_id this entry duplicates/corrects (for de-duplication)",
    )

    class Config:
        frozen = True  # Immutable after creation


# ============================================================================
# FINDING (Part 2 output, Part 3/4 input)
# ============================================================================


class Alert(BaseModel):
    """Alert details for a finding."""

    channel: Channel = Field(description="Channel to send alert on (email/sms/whatsapp)")
    to: str = Field(description="Recipient (YOUR test number/email, NOT portfolio contact)")
    message: str = Field(description="Concise actionable message (< 300 chars for SMS)")


class Finding(BaseModel):
    """
    A compliance gap: a product against a requirement.

    Output of Part 2 (assessment service), input of Parts 3 & 4 (alerting, dashboard).
    """

    # Company & Product
    company: str = Field(description="Partner company name")
    partner_id: str = Field(description="Partner ID (e.g., 'P001')")
    product_id: str = Field(description="Product ID (e.g., 'P001-A')")
    product: str = Field(description="Product name")

    # Regulation
    regulation: str = Field(
        description="Human-readable regulation + article (e.g., 'EU Battery Regulation 2023/1542 — battery passport (Art. 77)')"
    )
    requirement: str = Field(description="What the rule requires, in one sentence")
    source_url: str = Field(
        description="Live source URL (MANDATORY - proves rule came from live source)"
    )

    # Gap
    gap: str = Field(description="Why this product is non-compliant today")

    # Deadline & Severity
    deadline: date = Field(description="Compliance deadline")
    severity: Severity = Field(description="Severity level (low/medium/high)")

    # Action
    recommended_action: str = Field(description="The fix")

    # Alert
    alert: Alert = Field(description="Alert details (channel, recipient, message)")

    class Config:
        frozen = True  # Immutable after creation
