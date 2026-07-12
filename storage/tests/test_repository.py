"""Repository tests (marked ``db``): round-trip, constraints, upsert semantics,
in-force filtering, and lineage traversal."""

from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.db


def test_round_trip_preserves_contract(db, sample_requirements):
    from storage import repository

    original = sample_requirements[0]

    async def scenario(session):
        await repository.upsert_requirements(session, [original])
        return await repository.get_in_force_requirements(session)

    stored = db(scenario)
    assert len(stored) == 1
    assert stored[0].model_dump(mode="json") == original.model_dump(mode="json")


def test_source_url_constraint(db, sample_requirements):
    from sqlalchemy.exc import IntegrityError

    from storage import repository
    from storage.hashing import content_hash

    bad = sample_requirements[0].model_copy(update={"source_url": ""})

    async def scenario(session):
        await repository.upsert_requirements(session, [bad])

    with pytest.raises(IntegrityError):
        db(scenario)
    assert content_hash(bad)  # hashing itself never enforces provenance


def test_refetch_of_unchanged_rule_is_noop(db, sample_requirements):
    from sqlalchemy import select

    from storage import repository
    from storage.orm import Obligation

    req = sample_requirements[0]
    refetched = req.model_copy(update={"access_timestamp": datetime(2025, 6, 1, tzinfo=UTC)})

    async def scenario(session):
        await repository.upsert_requirements(session, [req])
        await repository.upsert_requirements(session, [refetched])
        rows = list(await session.scalars(select(Obligation)))
        return rows

    rows = db(scenario)
    assert len(rows) == 1
    assert rows[0].access_timestamp == datetime(2025, 6, 1, tzinfo=UTC)
    assert rows[0].valid_to is None


def test_changed_rule_supersedes_not_overwrites(db, sample_requirements):
    from sqlalchemy import select

    from storage import repository
    from storage.orm import Obligation

    v1 = sample_requirements[0]
    v2 = v1.model_copy(update={"title": v1.title + " (amended)"})

    async def scenario(session):
        await repository.upsert_requirements(session, [v1])
        await repository.upsert_requirements(session, [v2])
        rows = list(await session.scalars(select(Obligation).order_by(Obligation.id)))
        in_force = await repository.get_in_force_requirements(session)
        return rows, in_force

    rows, in_force = db(scenario)
    assert len(rows) == 2
    old, new = rows
    assert old.valid_to is not None  # closed, but content untouched
    assert old.title == v1.title
    assert new.supersedes_id == old.id
    assert new.valid_to is None
    assert [r.title for r in in_force] == [v2.title]


def test_lineage_chain_of_three_versions(db, sample_requirements):
    from storage import repository

    v1 = sample_requirements[0]
    v2 = v1.model_copy(update={"title": v1.title + " v2"})
    v3 = v1.model_copy(update={"title": v1.title + " v3"})

    async def scenario(session):
        for version in (v1, v2, v3):
            await repository.upsert_requirements(session, [version])
        return await repository.lineage(session, v1.update_id)

    chain = db(scenario)
    assert [row.title for row in chain] == [v1.title, v2.title, v3.title]
    assert chain[0].supersedes_id is None
    assert chain[1].supersedes_id == chain[0].id
    assert chain[2].supersedes_id == chain[1].id
    assert chain[2].valid_to is None
