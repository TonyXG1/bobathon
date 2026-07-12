"""SQLAlchemy 2.0 ORM models for the single-Postgres storage layer.

Columns are derived 1:1 from the ``Requirement`` / ``Finding`` contracts in
``contracts/models.py`` plus the storage-only concerns (content hash, temporal
validity, lineage). No scope dimension beyond what the assessment predicate
uses is invented; product-attribute conditions stay in ``scope_conditions``
free text because that is what the frozen contract carries.

Enum-ish text columns get CHECK constraints built from the contract Literals
(not PG enums) so they evolve with ``taxonomy.json`` via plain migrations.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import get_args

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from contracts.models import ChangeType, Channel, RegulationFamily, Severity

# Dimensionality of the triage embeddings (see storage/similarity.py).
EMBEDDING_DIMS = 256


def _sql_in(literal_type: object) -> str:
    """Render a contracts Literal as a SQL IN-list: ``'a', 'b', 'c'``."""
    return ", ".join(f"'{v}'" for v in get_args(literal_type))


class Base(DeclarativeBase):
    pass


class Obligation(Base):
    """One version of a regulatory obligation — layer 1, the system of record.

    Append-only: a content change inserts a new row that supersedes the old one
    (``supersedes_id`` self-FK, old row's ``valid_to`` set); rows are never
    overwritten. The in-force set is ``valid_to IS NULL``.
    """

    __tablename__ = "obligations"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    update_id: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text, unique=True)

    # Provenance (mandatory — AGENTS.md/CLAUDE.md §6.3)
    source: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    celex: Mapped[str | None] = mapped_column(Text)
    consolidation_date: Mapped[date | None] = mapped_column(Date)
    access_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Classification
    regulation_family: Mapped[str] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(Text)
    change_type: Mapped[str] = mapped_column(Text)

    # Content / payload
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    action_required: Mapped[str | None] = mapped_column(Text)

    # Dates
    published_date: Mapped[date] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    deadline_date: Mapped[date | None] = mapped_column(Date)

    # Scope — exactly the dimensions the applicability predicate matches on
    # (market ∧ category ∧ substance ∧ attribute ∧ ¬exclusion).
    scope_all_categories: Mapped[bool] = mapped_column(Boolean, default=False)
    scope_categories: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    scope_substances: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    scope_markets: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    scope_conditions: Mapped[str] = mapped_column(Text, default="")

    # Temporal validity (NULL valid_to = in force)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Lineage (layer 3 — rows + recursive CTEs, no graph DB)
    supersedes_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("obligations.id"))
    corrects_update_id: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("source_url <> ''", name="ck_obligations_source_url_nonempty"),
        CheckConstraint(
            f"regulation_family IN ({_sql_in(RegulationFamily)})",
            name="ck_obligations_regulation_family",
        ),
        CheckConstraint(
            f"change_type IN ({_sql_in(ChangeType)})", name="ck_obligations_change_type"
        ),
        CheckConstraint(f"severity IN ({_sql_in(Severity)})", name="ck_obligations_severity"),
        Index("ix_obligations_update_id", "update_id"),
        Index("ix_obligations_regulation_family", "regulation_family"),
        Index("ix_obligations_in_force", "valid_to"),
    )


class FindingRecord(Base):
    """Audit row for one produced Finding: what fired, against what, when."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    rule_id: Mapped[str] = mapped_column(Text)
    obligation_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("obligations.id"))

    # Finding contract fields (contracts/models.py)
    company: Mapped[str] = mapped_column(Text)
    partner_id: Mapped[str] = mapped_column(Text)
    product_id: Mapped[str] = mapped_column(Text)
    product: Mapped[str] = mapped_column(Text)
    regulation: Mapped[str] = mapped_column(Text)
    requirement: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text)
    gap: Mapped[str] = mapped_column(Text)
    deadline: Mapped[date] = mapped_column(Date)
    severity: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    alert_channel: Mapped[str] = mapped_column(Text)
    alert_to: Mapped[str] = mapped_column(Text)
    alert_message: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("source_url <> ''", name="ck_findings_source_url_nonempty"),
        CheckConstraint(f"severity IN ({_sql_in(Severity)})", name="ck_findings_severity"),
        CheckConstraint(f"alert_channel IN ({_sql_in(Channel)})", name="ck_findings_alert_channel"),
        Index("ix_findings_partner_product", "partner_id", "product_id"),
    )


class ObligationEmbedding(Base):
    """Layer 2 — triage-only vector index, physically severable.

    Lives in its own table so dropping it (or the pgvector extension) touches
    nothing in the decision path. Written opportunistically after upsert; never
    read by the repository or the matcher.
    """

    __tablename__ = "obligation_embeddings"

    obligation_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("obligations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMS))
    embedder: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
