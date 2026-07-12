# Design — add-postgres-pgvector-storage

## Context

All three services are stateless FastAPI apps (CLAUDE.md §3): extraction hits the live CELLAR
SPARQL endpoint on every `GET /requirements` ([extraction_service/extractor.py](../../../extraction_service/extractor.py)),
assessment fetches requirements from extraction over HTTP on every call
([assessment_service/main.py](../../../assessment_service/main.py) `fetch_requirements_from_extraction`),
and findings are never stored. The earlier Docker/database scaffolding was removed; there is no
docker-compose, no `DATABASE_URL`, no `database/` directory today. The repo is a `uv` workspace,
services run on the host via `run_all.ps1` (Windows), and the shared `contracts/` package is
imported via a `sys.path` bootstrap in each service's `config.py`.

Fixed constraints from the architecture brief:

- **One database: PostgreSQL.** The vector index and the relationship graph are capabilities
  *inside* that single instance, not separate systems.
- **Three logical layers with strict roles:**
  1. *Relational obligation store* — system of record; the ONLY input to the decision path.
  2. *pgvector index* — retrieval/triage only; never read by the matcher.
  3. *Relationships* (amendments/supersession/corrections) — self-referencing FKs + recursive
     CTEs; lineage and audit, not decisions.
- **Golden rule:** if pgvector were deleted entirely, findings must be byte-identical.
- `contracts/models.py` (`Requirement`/`Finding`) and `engine.py` matching logic are frozen.

## Goals / Non-Goals

**Goals:**

- Durable, auditable obligation storage; assessment reads Postgres instead of live HTTP.
- Extraction persists what it fetches (upsert by content hash; supersede, never overwrite).
- Findings persisted with the rule that fired, for after-the-fact audit.
- pgvector similarity available for triage, provably outside the decision path.
- Keep `run_all.ps1` + offline test suites working, with and without a database running.

**Non-Goals:**

- No change to matching logic or outcomes in `engine.py`; no contract model changes.
- No graph database; no LLM/embedding influence on findings; no dashboard; no dockerization of
  the services themselves; no ECHA/Formex extraction work.

## Decisions

### D1. One Postgres via `pgvector/pgvector:pg16`; compose runs the DB only

New root `docker-compose.yml` with a single `db` service: image `pgvector/pgvector:pg16`, named
volume, healthcheck (`pg_isready`), port 5432, credentials matching the default `DATABASE_URL`.
Services keep running on the host via `run_all.ps1` (which gains an optional step: start/await the
DB, run migrations). *Alternative rejected:* dockerizing all services — there are no Dockerfiles
today, the repo is Windows/uv-oriented, and it would grow the change far beyond storage.

`CREATE EXTENSION IF NOT EXISTS vector` runs inside the first Alembic migration (the pgvector
image permits it without superuser gymnastics).

### D2. Shared `storage/` package, mirroring `contracts/`

New top-level `storage/` package — uv workspace member with its own `pyproject.toml`
(deps: `sqlalchemy>=2.0`, `asyncpg`, `alembic`, `pgvector`), imported by both services through the
existing `sys.path` bootstrap in each `config.py`. Layout:

```
storage/
├── pyproject.toml
├── __init__.py
├── db.py            # async engine/session factory from DATABASE_URL
├── orm.py           # SQLAlchemy 2.0 declarative models (obligations, findings, embeddings)
├── repository.py    # decision-path data access: upsert, in-force query, lineage CTE, findings
├── similarity.py    # TRIAGE ONLY: embeddings + pgvector search; never imported by repository/engine
├── hashing.py       # canonical content-hash of a Requirement
├── alembic.ini
└── migrations/      # Alembic env + versions (schema source of truth; no init.sql)
```

*Alembic over `init.sql`:* the referenced `database/init.sql` no longer exists; for a real product
migrations must evolve, so the first revision *is* the schema (generated from `orm.py`). No
`database/` directory is created.

### D3. Schema derived from the contract + what the engine matches on

`obligations` — one row per obligation version. Columns map 1:1 from `Requirement`
(contracts/models.py:112) — nothing invented, nullable where extraction can't populate yet:

| Group | Columns |
|---|---|
| Key | `id` (identity PK), `update_id` (text, indexed), `content_hash` (text, unique) |
| Provenance | `source`, `source_url` (NOT NULL), `celex`, `consolidation_date`, `access_timestamp` |
| Classification | `regulation_family` (indexed), `reference`, `change_type` |
| Content | `title`, `summary`, `severity`, `action_required` |
| Payload dates | `published_date`, `effective_date`, `deadline_date` |
| Scope | `scope_all_categories` (bool), `scope_categories` (text[]), `scope_substances` (text[]), `scope_markets` (text[]), `scope_conditions` (text) |
| Temporal validity | `valid_from` (timestamptz NOT NULL), `valid_to` (timestamptz NULL — NULL = in force) |
| Lineage | `supersedes_id` (self-FK → obligations.id), `corrects_update_id` (text, from `Requirement.corrects`) |

Scope columns are exactly the dimensions the applicability predicate uses (engine.py predicates +
CLAUDE.md §2.2: market ∧ category ∧ substance ∧ attribute ∧ ¬exclusion). Product-attribute
conditions (battery_type, connector, intended_use…) stay in `scope_conditions` free text because
that is what the `Requirement` contract carries today — no invented columns. Enum-ish text columns
get CHECK constraints against the taxonomy Literals rather than PG enums (cheaper to evolve with
`taxonomy.json`).

`findings` — audit log, written after each assessment run: `id`, `assessed_at`, `rule_id`,
`obligation_id` (FK), plus every `Finding` contract field (partner_id, product_id, company,
product, regulation, requirement, source_url, gap, deadline, severity, recommended_action,
alert_channel, alert_to, alert_message).

`obligation_embeddings` — **separate table**, so layer 2 is physically severable:
`obligation_id` (PK, FK → obligations, ON DELETE CASCADE), `embedding vector(256)`,
`embedder` (text), `created_at`. Dropping this table (or the extension) touches nothing else.

### D4. Upsert-by-content-hash; supersede, never overwrite

`hashing.py` computes sha256 over the canonical JSON of a `Requirement` **excluding**
`access_timestamp` (a re-fetch of unchanged content must hash identically). Repository upsert per
fetched requirement:

1. Same `content_hash` already stored → refresh `access_timestamp` only (semantic no-op).
2. Same `update_id`, different hash → insert new row with `supersedes_id` = old row's id; set old
   row's `valid_to = now()`. History is append-only.
3. New `update_id` → plain insert.

In-force set = `WHERE valid_to IS NULL`. Lineage chain = recursive CTE following `supersedes_id`
(exposed as `repository.lineage(update_id)`); kept entirely inside `repository.py` so a future
property graph could replace it without touching the matcher.

### D5. Service wiring — engine signature and outcomes unchanged

- **extraction_service** `GET /requirements`: fetch live from CELLAR (unchanged politeness), then
  `repository.upsert_requirements(...)`, then serve the in-force rows (rehydrated as `Requirement`
  Pydantic objects) from the DB. If the live fetch fails entirely but the DB has in-force rows,
  serve those (provenance columns still cite the live source + original access time) instead of
  502 — durability is the point of this change. If both fail → 502 as today.
- **assessment_service**: `_run` obtains requirements from `repository.get_in_force_requirements()`
  instead of HTTP; falls back to the existing HTTP fetch when the DB is unavailable/empty (keeps
  `POST /assess` with an explicit `requirements` body working unchanged, e.g. for tests).
  `engine.assess()` is untouched — it still takes `Iterable[Requirement]`. After assessing,
  findings are persisted via `repository.save_findings(findings)`; `rule_id` is resolved by the
  1:1 `regulation` label → `RULES` lookup in `main.py`, so `engine.py` needs no change.
- **Repository returns contract models**, not ORM rows — the DB is invisible to `engine.py`.
- Touched endpoints become `async def` (SQLAlchemy async + asyncpg); `pytest-asyncio` is already a
  dev dependency.
- **Graceful degradation** (`DATABASE_URL` unset or DB down): both services log a warning and run
  in today's stateless mode. `run_all.ps1` therefore still works without Docker.

### D6. pgvector strictly outside the decision path — enforced, not promised

- All similarity code lives in `storage/similarity.py`; `repository.py`, `engine.py`, and
  assessment `main.py` never import it. It is called only from a new triage endpoint on the
  extraction service (`GET /requirements/{celex}/similar`).
- Embedding provider is pluggable with a lightweight deterministic default (stdlib feature-hashing
  of obligation title+summary into 256 dims) — no heavy ML dependency (house rule §12.2); a real
  model can be swapped in later behind the same interface. Embeddings are written opportunistically
  after upsert (failure to embed never fails the upsert).
- **Parity test (the hard constraint):** an integration test runs the assessment path against a
  seeded DB twice — with embeddings populated, and after `TRUNCATE obligation_embeddings` (and a
  variant with the vector table dropped) — and asserts the serialized findings are identical.
  A second, offline test asserts the import graph: importing `engine` and `storage.repository`
  must not load `storage.similarity`.

### D7. Configuration

`.env.example` gains `DATABASE_URL=postgresql+asyncpg://radar:radar@localhost:5432/radar`
(commented note: optional — services degrade to stateless without it). Each service's `Settings`
gains `database_url: str | None = None`. `storage/db.py` builds the engine lazily from the value
passed by the service (no global import-time connection).

## Risks / Trade-offs

- [Graceful degradation adds two code paths] → keep the branch in one place per service (the
  requirements-source function), and cover both paths with tests.
- [Scope `conditions` stays free text, so attribute predicates still live in `RULES`, not SQL] →
  accepted: the contract is frozen and engine outcomes must not change; typed attribute columns
  are a follow-up contract change if extraction ever populates them.
- [Hash excludes `access_timestamp` but includes normalized fields — normalizer changes would
  re-version all rows] → acceptable: a normalization change *is* a content change; note it in
  `hashing.py`.
- [Async SQLAlchemy in currently-sync services] → only touched endpoints go async; FastAPI mixes
  sync/async routes freely.
- [DB tests need a running Postgres] → mark them (`pytest -m db`), auto-skip when `DATABASE_URL`
  is unreachable; offline suites stay green, mirroring the existing `integration` marker pattern.
- [Windows dev without Docker] → any Postgres 16 with pgvector works; compose is convenience,
  `DATABASE_URL` is the contract.

## Migration Plan

1. `docker compose up -d db` (or any Postgres+pgvector), then `uv run alembic upgrade head`
   (from `storage/`; wired into `run_all.ps1` behind a `-WithDb` switch).
2. First `GET /requirements` populates the obligation store; first `GET /findings` writes audit
   rows. No data backfill needed — the system was stateless.
3. Rollback: stop pointing `DATABASE_URL` at the DB (services degrade to stateless mode) or
   `alembic downgrade base`. No contract or API shape changes to roll back.

## Open Questions

- None blocking. Follow-ups deliberately deferred: typed attribute-threshold columns (needs a
  contract change), real embedding model, orchestrator-driven scheduled refresh.
