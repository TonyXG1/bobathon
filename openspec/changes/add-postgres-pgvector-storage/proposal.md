# Add PostgreSQL + pgvector storage layer

## Why

The pipeline is fully stateless today: every `GET /requirements` hits the live CELLAR SPARQL
endpoint, assessment re-fetches over HTTP on every call, and findings vanish after the response.
That makes assessment slow and fragile (one CELLAR hiccup empties the pipeline), and leaves no
audit trail — yet auditability and provenance are explicit judging criteria and product
requirements. Durable storage makes assessment instant and auditable while keeping the
deterministic matcher untouched.

Note on prior scaffolding: the earlier database-backed design's scaffolding (docker-compose
postgres service, `DATABASE_URL`, `database/init.sql`) was **removed** from the repo (CLAUDE.md §3).
This change re-introduces persistence properly rather than completing files that no longer exist.

## What Changes

- **One PostgreSQL database** (pgvector-enabled image `pgvector/pgvector:pg16`) added via a new
  `docker-compose.yml` that runs only the database; services keep running on the host via
  `run_all.ps1`. `DATABASE_URL` added to `.env.example` and service `Settings`.
- **New shared `storage/` package** (mirrors how `contracts/` is shared): SQLAlchemy 2.0 async ORM
  models, asyncpg engine/session, Alembic migrations (instead of an ad-hoc `init.sql`), and a
  repository layer both services import.
- **Relational obligation store — the system of record.** Schema derived strictly from the
  `Requirement` contract (`contracts/models.py`) plus the scope dimensions `engine.py` matches on
  (categories, substances, markets, attributes, conditions). Temporal validity + lineage
  (supersedes/corrects) as self-referencing FKs traversed with recursive CTEs. Provenance columns
  (source_url, CELEX, consolidation date, access timestamp, content hash) on every row.
- **extraction_service writes**: after each live CELLAR fetch it upserts obligations by content
  hash — unchanged rules are no-ops; changed rules supersede via lineage/temporal columns, never
  overwrite. `GET /requirements` serves from the DB (freshly populated by the live fetch).
- **assessment_service reads** current in-force obligations from Postgres via the repository
  instead of calling extraction over HTTP. `engine.py` matching logic is **unchanged** — only its
  input source moves. Findings are persisted with the `rule_id`/predicate that fired, for audit.
- **pgvector for triage only**: an embeddings side-table + similarity search behind a separate,
  clearly named module outside the assessment path. **Hard constraint:** vector similarity never
  influences findings — if pgvector were deleted, findings are byte-identical. A test proves this.
- **No graph database.** Amendment/consolidation relationships are rows + recursive CTEs, isolated
  in the repository so they could later be lifted out without touching the matcher.

## Capabilities

### New Capabilities

- `obligation-store`: the relational system of record for regulatory obligations — schema derived
  from the `Requirement` contract, temporal validity, supersedes/corrects lineage via
  self-referencing FKs + recursive CTEs, mandatory provenance, upsert-by-content-hash from live
  extraction, and DB-backed serving of `GET /requirements`. The ONLY store the assessment matcher
  reads.
- `finding-audit`: persistence of every produced `Finding` with the rule that fired
  (rule_id, obligation reference, timestamps) so compliance decisions are auditable after the fact.
- `vector-triage`: pgvector embeddings of obligation text for similarity search/routing/human
  triage only, exposed behind a dedicated module that the decision path never imports; includes the
  deletion-parity guarantee (drop pgvector ⇒ identical findings).

### Modified Capabilities

None — `openspec/specs/` is empty; no existing capability specs to modify.

## Impact

- **New:** `storage/` package (ORM, session, migrations, repositories, similarity module),
  `docker-compose.yml` (database only), Alembic revision(s).
- **Modified:** `extraction_service/` (persist after fetch; serve from DB), `assessment_service/`
  (read obligations from DB via repository; persist findings), both services' `config.py`
  (`database_url` setting), `.env.example`, root `pyproject.toml` (workspace member), `run_all.ps1`
  (start/require the database), CLAUDE.md §3 (no longer "no database").
- **Unchanged (explicitly out of scope):** `contracts/models.py` (`Requirement`/`Finding` frozen —
  ask before touching), `engine.py` matching logic and outcomes, `dataset/` (read-only),
  alerting_service, no LLM/embedding in the decision path, no graph DB.
- **New dependencies:** `sqlalchemy>=2.0` (async), `asyncpg`, `alembic`, `pgvector` (Python pkg).
- **Operational:** local dev now needs Docker (or any Postgres 16 + pgvector) for DB-backed paths;
  tests that need the DB are marked and skipped when it's absent, offline suites stay green.
