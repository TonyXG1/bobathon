"""DB-backed wiring tests (marked ``db``): the store feeds the unchanged
matcher identically to direct input, and findings are audited with the rule
that fired and a live source URL."""

import pytest

pytestmark = pytest.mark.db


def _assess(requirements, partners):
    from engine import assess

    return assess(requirements, partners)


def test_db_backed_assessment_identical_to_direct(db, sample_requirements, partners):
    from storage import repository

    async def scenario(session):
        await repository.upsert_requirements(session, sample_requirements)
        return await repository.get_in_force_requirements(session)

    stored = db(scenario)
    findings_direct = _assess(sample_requirements, partners)
    findings_db = _assess(stored, partners)

    assert findings_direct  # guard: the parity assertion is not vacuous
    assert [f.model_dump(mode="json") for f in findings_db] == [
        f.model_dump(mode="json") for f in findings_direct
    ]


def test_finding_audit_rows(db, sample_requirements, partners):
    from engine import RULES
    from sqlalchemy import select

    from storage import repository
    from storage.orm import FindingRecord, Obligation

    rule_ids = {rule.regulation: rule.rule_id for rule in RULES}
    known_rule_ids = {rule.rule_id for rule in RULES}

    async def scenario(session):
        await repository.upsert_requirements(session, sample_requirements)
        stored = await repository.get_in_force_requirements(session)
        findings = _assess(stored, partners)
        written = await repository.save_findings(session, findings, rule_ids)
        rows = list(await session.scalars(select(FindingRecord)))
        url_by_obligation = {
            row.id: row.source_url for row in await session.scalars(select(Obligation))
        }
        return findings, written, rows, url_by_obligation

    findings, written, rows, url_by_obligation = db(scenario)
    assert written == len(findings) == len(rows)
    for row in rows:
        assert row.rule_id in known_rule_ids
        assert row.source_url.startswith("http")
        assert row.assessed_at is not None
        # grounded in the obligation version that carries the same live source
        assert row.obligation_id is not None
        assert url_by_obligation[row.obligation_id] == row.source_url
