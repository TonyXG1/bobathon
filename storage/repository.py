"""Decision-path data access for the obligation store (layer 1) and audit (findings).

This module is the ONLY database surface the assessment path touches. It must
never import ``storage.similarity`` (layer 2) — vector similarity has no say
in which findings are produced, and an offline test enforces this import rule.

Lineage (layer 3) is also confined here: supersedes chains are plain rows
traversed with a recursive CTE, so a future property graph could replace
:func:`lineage` without touching the matcher.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from contracts.models import Finding, Requirement, RequirementScope
from storage.hashing import content_hash
from storage.orm import FindingRecord, Obligation


def _to_row(req: Requirement, digest: str) -> Obligation:
    scope = req.scope
    all_categories = scope.categories == "all"
    return Obligation(
        update_id=req.update_id,
        content_hash=digest,
        source=req.source,
        source_url=req.source_url,
        celex=req.celex,
        consolidation_date=req.consolidation_date,
        access_timestamp=req.access_timestamp,
        regulation_family=req.regulation_family,
        reference=req.reference,
        change_type=req.change_type,
        title=req.title,
        summary=req.summary,
        severity=req.severity,
        action_required=req.action_required,
        published_date=req.published_date,
        effective_date=req.effective_date,
        deadline_date=req.deadline_date,
        scope_all_categories=all_categories,
        scope_categories=[] if all_categories else list(scope.categories),
        scope_substances=list(scope.substances),
        scope_markets=list(scope.markets),
        scope_conditions=scope.conditions,
        corrects_update_id=req.corrects,
    )


def to_requirement(row: Obligation) -> Requirement:
    """Rehydrate the frozen ``Requirement`` contract from an obligation row."""
    return Requirement(
        update_id=row.update_id,
        published_date=row.published_date,
        source=row.source,
        source_url=row.source_url,
        celex=row.celex,
        consolidation_date=row.consolidation_date,
        access_timestamp=row.access_timestamp,
        regulation_family=row.regulation_family,  # type: ignore[arg-type]
        reference=row.reference,
        title=row.title,
        summary=row.summary,
        change_type=row.change_type,  # type: ignore[arg-type]
        effective_date=row.effective_date,
        deadline_date=row.deadline_date,
        severity=row.severity,  # type: ignore[arg-type]
        action_required=row.action_required,
        scope=RequirementScope(
            categories="all" if row.scope_all_categories else list(row.scope_categories),  # type: ignore[arg-type]
            substances=list(row.scope_substances),  # type: ignore[arg-type]
            markets=list(row.scope_markets),
            conditions=row.scope_conditions,
        ),
        corrects=row.corrects_update_id,
    )


async def upsert_requirements(
    session: AsyncSession, requirements: Iterable[Requirement]
) -> list[int]:
    """Upsert fetched requirements by content hash; return NEW obligation ids.

    Per requirement:
    - same ``content_hash`` already stored → semantic no-op, only the
      ``access_timestamp`` refreshes;
    - same ``update_id`` in force with different hash → append a new row whose
      ``supersedes_id`` points at the old one and close the old row's
      ``valid_to`` (never overwrite);
    - otherwise → plain insert.

    Commits once at the end.
    """
    new_ids: list[int] = []
    for req in requirements:
        digest = content_hash(req)
        existing = await session.scalar(select(Obligation).where(Obligation.content_hash == digest))
        if existing is not None:
            existing.access_timestamp = req.access_timestamp
            continue

        current = await session.scalar(
            select(Obligation).where(
                Obligation.update_id == req.update_id, Obligation.valid_to.is_(None)
            )
        )
        row = _to_row(req, digest)
        if current is not None:
            current.valid_to = datetime.now(UTC)
            session.add(row)
            await session.flush()
            row.supersedes_id = current.id
        else:
            session.add(row)
            await session.flush()
        new_ids.append(row.id)
    await session.commit()
    return new_ids


async def get_in_force_requirements(session: AsyncSession) -> list[Requirement]:
    """The current in-force obligations (``valid_to IS NULL``) as contract models."""
    rows = await session.scalars(
        select(Obligation).where(Obligation.valid_to.is_(None)).order_by(Obligation.id)
    )
    return [to_requirement(row) for row in rows]


async def lineage(session: AsyncSession, update_id: str) -> list[Obligation]:
    """Full version chain for ``update_id`` via a recursive CTE, oldest first."""
    head = (
        select(Obligation.id, Obligation.supersedes_id)
        .where(Obligation.update_id == update_id, Obligation.valid_to.is_(None))
        .cte("lineage", recursive=True)
    )
    parent = aliased(Obligation)
    chain = head.union_all(
        select(parent.id, parent.supersedes_id).join(head, head.c.supersedes_id == parent.id)
    )
    rows = await session.scalars(
        select(Obligation).join(chain, Obligation.id == chain.c.id).order_by(Obligation.id)
    )
    return list(rows)


async def save_findings(
    session: AsyncSession,
    findings: Iterable[Finding],
    rule_id_by_regulation: Mapping[str, str],
) -> int:
    """Persist one audit row per Finding; returns the number written.

    ``rule_id_by_regulation`` maps the human ``regulation`` label (1:1 with a
    gap rule today) to its ``rule_id``. The grounding obligation is resolved by
    the finding's ``source_url`` against the in-force set (nullable — e.g. when
    requirements were passed in the request body and never persisted).
    """
    in_force = await session.scalars(select(Obligation).where(Obligation.valid_to.is_(None)))
    obligation_by_url = {row.source_url: row.id for row in in_force}

    count = 0
    for finding in findings:
        session.add(
            FindingRecord(
                rule_id=rule_id_by_regulation.get(finding.regulation, "unknown"),
                obligation_id=obligation_by_url.get(finding.source_url),
                company=finding.company,
                partner_id=finding.partner_id,
                product_id=finding.product_id,
                product=finding.product,
                regulation=finding.regulation,
                requirement=finding.requirement,
                source_url=finding.source_url,
                gap=finding.gap,
                deadline=finding.deadline,
                severity=finding.severity,
                recommended_action=finding.recommended_action,
                alert_channel=finding.alert.channel,
                alert_to=finding.alert.to,
                alert_message=finding.alert.message,
            )
        )
        count += 1
    await session.commit()
    return count
