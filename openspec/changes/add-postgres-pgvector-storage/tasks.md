# Tasks — add-postgres-pgvector-storage

## 1. Infrastructure & configuration

- [x] 1.1 Create root `docker-compose.yml` with a single `db` service: `pgvector/pgvector:pg16`, named volume, `pg_isready` healthcheck, port 5432, credentials matching the default `DATABASE_URL`
- [x] 1.2 Add `DATABASE_URL=postgresql+asyncpg://radar:radar@localhost:5432/radar` to `.env.example` with a comment that it is optional (services degrade to stateless without it)
- [x] 1.3 Add `database_url: str | None = None` to `Settings` in `extraction_service/config.py` and `assessment_service/config.py`

## 2. Shared storage package

- [x] 2.1 Scaffold top-level `storage/` package with `pyproject.toml` (deps: `sqlalchemy>=2.0`, `asyncpg`, `alembic`, `pgvector`) and register it as a uv workspace member in the root `pyproject.toml`
- [x] 2.2 Implement `storage/db.py`: lazy async engine + session factory built from a passed `DATABASE_URL` (no import-time connection)
- [x] 2.3 Implement `storage/orm.py`: `obligations` (contract-derived columns per design D3, scope arrays, `content_hash` unique, `valid_from`/`valid_to`, `supersedes_id` self-FK, `corrects_update_id`, CHECK constraints from taxonomy Literals), `findings` (all Finding fields + `rule_id`, `obligation_id` FK, `assessed_at`), `obligation_embeddings` (`obligation_id` PK/FK ON DELETE CASCADE, `embedding vector(256)`, `embedder`, `created_at`)
- [x] 2.4 Implement `storage/hashing.py`: sha256 over canonical Requirement JSON excluding `access_timestamp`, with a docstring noting normalizer changes re-version rows
- [x] 2.5 Set up Alembic in `storage/` (`alembic.ini`, `migrations/env.py` wired to the ORM metadata) and write the initial revision: `CREATE EXTENSION IF NOT EXISTS vector` + the three tables
- [x] 2.6 Implement `storage/repository.py`: `upsert_requirements()` (no-op on same hash refreshing `access_timestamp`; supersede on changed hash setting old `valid_to` and new `supersedes_id`; insert new), `get_in_force_requirements()` returning rehydrated `Requirement` models (`valid_to IS NULL`), `lineage(update_id)` recursive CTE, `save_findings(findings, rule_ids)` — no import of `similarity`
- [x] 2.7 Implement `storage/similarity.py`: pluggable embedder interface with deterministic stdlib feature-hash default (256 dims), `embed_obligations()` (post-upsert, failures logged never raised) and `find_similar_obligations()` via pgvector distance

## 3. Wire extraction_service

- [x] 3.1 After live fetch in `GET /requirements`: upsert via repository, opportunistically embed, and serve in-force rows from the DB; on total live-fetch failure serve stored in-force rows; 502 only when both are empty; keep pure-live behavior when `database_url` is unset/unreachable
- [x] 3.2 Add triage endpoint `GET /requirements/{celex}/similar` calling `storage.similarity.find_similar_obligations` (404 for unknown CELEX, empty list when no embeddings)

## 4. Wire assessment_service

- [x] 4.1 Change the requirements source in `main.py` to `repository.get_in_force_requirements()`, falling back to the existing HTTP fetch when the DB is unavailable/empty; leave `engine.py` and the explicit `requirements` body of `POST /assess` untouched
- [x] 4.2 Persist findings after each run via `repository.save_findings`, resolving `rule_id` by the 1:1 `regulation` label → `RULES` lookup in `main.py`; persistence failure logs a warning without failing the response

## 5. Tests

- [x] 5.1 Add a `db` pytest marker (mirroring the existing `integration` marker) that auto-skips when `DATABASE_URL` is unset/unreachable; keep all existing offline suites green
- [x] 5.2 Repository tests (`db`): contract round-trip equality, mandatory `source_url` constraint, no-op re-fetch, supersede-on-change, in-force filtering, lineage chain of three versions
- [x] 5.3 Wiring tests: DB-backed assessment produces findings identical to directly-passed requirements; graceful degradation paths for both services (mock DB absent); finding audit rows carry `rule_id`, obligation reference, and non-null `source_url`
- [x] 5.4 **Parity test (hard constraint)**: assess a seeded obligation set with embeddings populated, then after truncating and after dropping `obligation_embeddings` — serialized findings byte-identical across all runs
- [x] 5.5 Offline import-graph test: importing `engine` and `storage.repository` does not load `storage.similarity`

## 6. Runbook & docs

- [x] 6.1 Extend `run_all.ps1` with an optional `-WithDb` switch: `docker compose up -d db`, wait for health, `uv run alembic upgrade head`, then start services
- [x] 6.2 Update CLAUDE.md §3/§4 (architecture no longer "stateless, no database"; add `storage/` to the repo tree) and the affected service READMEs
- [x] 6.3 Run `uv run ruff check .` and `uv run ruff format .`; run offline suites and (with the DB up) `uv run pytest -m db`
