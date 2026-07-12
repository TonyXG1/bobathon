"""Shared PostgreSQL storage layer for Regulatory Radar.

One database, three logical layers with strict roles (see the
add-postgres-pgvector-storage change design):

1. ``orm``/``repository`` — the relational obligation store, the system of
   record and the ONLY input to the assessment decision path.
2. ``similarity`` — pgvector embeddings for retrieval/triage only. The decision
   path must never import it; nothing in this package's other modules does.
3. Lineage (supersedes/corrects) — self-referencing FKs traversed with
   recursive CTEs inside ``repository``.

This module deliberately imports nothing, so ``import storage`` never drags in
SQLAlchemy (or the similarity layer) for services running in stateless mode.
"""
