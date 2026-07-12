"""THE hard constraint (marked ``db``): vector similarity never influences
findings. With embeddings populated, truncated, or the pgvector table dropped
entirely, the assessment output must be byte-identical."""

import asyncio

import pytest

pytestmark = pytest.mark.db


def _serialized_findings(requirements, partners):
    from engine import assess

    return [f.model_dump(mode="json") for f in assess(requirements, partners)]


def _recreate_embeddings_table(db_url: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from storage.orm import ObligationEmbedding

    async def _recreate():
        engine = create_async_engine(db_url)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(ObligationEmbedding.__table__.create, checkfirst=True)
        finally:
            await engine.dispose()

    asyncio.run(_recreate())


def test_findings_identical_with_without_and_dropped_pgvector(
    db, db_url, sample_requirements, partners
):
    from sqlalchemy import func, select, text

    from storage import repository, similarity
    from storage.orm import ObligationEmbedding

    async def seed_and_embed(session):
        new_ids = await repository.upsert_requirements(session, sample_requirements)
        await similarity.embed_obligations(session, new_ids)
        count = await session.scalar(select(func.count(ObligationEmbedding.obligation_id)))
        stored = await repository.get_in_force_requirements(session)
        return count, stored

    async def truncate_embeddings(session):
        await session.execute(text("TRUNCATE obligation_embeddings"))
        await session.commit()
        return await repository.get_in_force_requirements(session)

    async def drop_embeddings_table(session):
        await session.execute(text("DROP TABLE obligation_embeddings"))
        await session.commit()
        return await repository.get_in_force_requirements(session)

    try:
        embedded_count, stored = db(seed_and_embed)
        assert embedded_count == len(sample_requirements)  # vectors really were there
        with_vectors = _serialized_findings(stored, partners)
        assert with_vectors  # guard: parity must not be vacuous

        stored = db(truncate_embeddings)
        without_vectors = _serialized_findings(stored, partners)

        stored = db(drop_embeddings_table)
        dropped_table = _serialized_findings(stored, partners)
    finally:
        _recreate_embeddings_table(db_url)

    assert with_vectors == without_vectors == dropped_table
