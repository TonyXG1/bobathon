"""Layer 2 — pgvector similarity over obligation text. TRIAGE ONLY.

This module serves fuzzy questions for humans and routing ("which obligations
look like this one?"). It is NEVER a source of truth and NEVER an input to
compliance decisions: nothing in ``storage.repository`` or the assessment path
imports it, and deleting pgvector entirely must leave findings byte-identical
(both are enforced by tests).

The default embedder is a deterministic stdlib feature-hash — no ML dependency
(house rule: prefer stdlib + existing libs). Swap in a real model later by
implementing :class:`Embedder`; stored rows record which embedder wrote them.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.orm import EMBEDDING_DIMS, Obligation, ObligationEmbedding
from storage.repository import to_requirement

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    """Pluggable embedding provider."""

    name: str

    def embed(self, text: str) -> list[float]: ...


class FeatureHashEmbedder:
    """Deterministic bag-of-words feature hashing into EMBEDDING_DIMS dims.

    Crude but dependency-free and fully reproducible — good enough for
    "which obligations mention similar things" triage until a real model is
    plugged in behind the same interface.
    """

    name = f"feature-hash-v1-{EMBEDDING_DIMS}d"

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * EMBEDDING_DIMS
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMS
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[index] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec


DEFAULT_EMBEDDER = FeatureHashEmbedder()


def _obligation_text(row: Obligation) -> str:
    return " ".join(part for part in (row.title, row.summary, row.scope_conditions) if part)


async def embed_obligations(
    session: AsyncSession,
    obligation_ids: list[int],
    embedder: Embedder = DEFAULT_EMBEDDER,
) -> None:
    """Write embeddings for the given obligations. Best-effort by contract:

    any failure is logged and swallowed — embedding must never fail or roll
    back an obligation upsert (the upsert is committed before this runs).
    """
    if not obligation_ids:
        return
    try:
        rows = await session.scalars(select(Obligation).where(Obligation.id.in_(obligation_ids)))
        for row in rows:
            session.add(
                ObligationEmbedding(
                    obligation_id=row.id,
                    embedding=embedder.embed(_obligation_text(row)),
                    embedder=embedder.name,
                )
            )
        await session.commit()
    except Exception:  # noqa: BLE001 - triage is best-effort, never propagate
        logger.warning("Embedding write failed (triage only, ignored)", exc_info=True)
        await session.rollback()


async def find_similar_obligations(session: AsyncSession, celex: str, limit: int = 5) -> list[dict]:
    """In-force obligations nearest (cosine) to the one identified by CELEX.

    Returns ``[]`` when the obligation has no embedding yet. Raises KeyError
    when no in-force obligation exists for ``celex`` (caller maps to 404).
    """
    target = await session.execute(
        select(Obligation, ObligationEmbedding.embedding)
        .join(
            ObligationEmbedding,
            ObligationEmbedding.obligation_id == Obligation.id,
            isouter=True,
        )
        .where(Obligation.celex == celex, Obligation.valid_to.is_(None))
    )
    row = target.first()
    if row is None:
        raise KeyError(celex)
    target_obligation, target_embedding = row
    if target_embedding is None:
        return []

    distance = ObligationEmbedding.embedding.cosine_distance(target_embedding)
    neighbors = await session.execute(
        select(Obligation, distance.label("distance"))
        .join(ObligationEmbedding, ObligationEmbedding.obligation_id == Obligation.id)
        .where(Obligation.id != target_obligation.id, Obligation.valid_to.is_(None))
        .order_by(distance)
        .limit(limit)
    )
    return [
        {"requirement": to_requirement(obligation), "distance": float(dist)}
        for obligation, dist in neighbors
    ]
