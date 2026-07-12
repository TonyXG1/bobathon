# vector-triage

pgvector-backed similarity over obligation text, for retrieval, routing, and human triage only.
It is a convenience index layered inside the same PostgreSQL instance — never a source of truth
and never an input to compliance decisions.

## ADDED Requirements

### Requirement: Embeddings live in a severable side table

Obligation embeddings SHALL be stored in a dedicated table (`obligation_id` FK with ON DELETE
CASCADE, `vector` column via the pgvector extension, embedder identifier, created_at) separate
from the obligations table, inside the same PostgreSQL instance. Embedding writes SHALL happen
after obligation upsert and a failure to embed SHALL never fail or roll back the upsert.

#### Scenario: Embedding failure does not block persistence

- **WHEN** embedding generation raises during an obligation upsert
- **THEN** the obligation row is committed and the error is logged

### Requirement: Similarity search is exposed only outside the decision path

Similarity search SHALL be implemented in a dedicated module (`storage/similarity.py`) with a
clearly named function (e.g. `find_similar_obligations`). The decision path — `engine.py`, the
obligation repository, and the assessment request flow — SHALL NOT import or invoke this module.
Similarity SHALL be reachable only via triage surfaces (e.g. `GET /requirements/{celex}/similar`
on the extraction service).

#### Scenario: Import graph stays clean

- **WHEN** the assessment engine and the obligation repository modules are imported
- **THEN** the similarity module is not loaded as a transitive dependency

#### Scenario: Triage endpoint returns neighbors

- **WHEN** `GET /requirements/{celex}/similar` is called for a stored obligation with embeddings
  present
- **THEN** semantically nearest in-force obligations are returned, ordered by vector distance

### Requirement: Deleting pgvector leaves findings byte-identical

Vector similarity SHALL have no influence on which findings are produced. With the embeddings
table truncated or dropped — or the pgvector extension absent entirely — an assessment run over
the same obligations SHALL produce findings identical to a run with embeddings fully populated.
An automated test SHALL prove this parity.

#### Scenario: Parity with and without vectors

- **WHEN** the same seeded obligation set is assessed with embeddings populated and again after
  the embeddings table is emptied/dropped
- **THEN** the serialized findings of both runs are identical
