# Design: build-orchestrator-pipeline

## Context

Three stateless FastAPI services exist (extraction :8081, assessment :8082, alerting :8083) sharing Pydantic contracts (`Requirement`, `Finding`). Pipeline composition is currently smeared across the services: assessment's `GET /findings` calls extraction, alerting's `/dispatch` and `/refresh` call assessment/extraction. There is no scheduler, no run history, and no alert dedup — a scheduled loop would re-send every alert each run. `orchestrator/` contains only a `pyproject.toml` declaring APScheduler. Decisions on form (scheduled + API), data flow (orchestrator carries data, services become pure), DTO, and alert policy (only-new findings, JSON state) were made with the project owner on 2026-07-10.

## Goals / Non-Goals

**Goals:**
- One component owns pipeline composition, scheduling, run history, and alert dedup
- Services become pure functions over their request bodies (easier to test, no hidden coupling)
- A `PipelineRunResult` contract others (future dashboard/database) can consume
- Zero regression: existing offline tests keep passing (adapted where endpoints are removed)

**Non-Goals:**
- No database — dedup state is a JSON file, explicitly designed to migrate later
- No dashboard/frontend work (CORS stays on for a future one)
- No retry/queueing semantics — a failed stage fails the run and is recorded in `errors`
- No auth on the orchestrator API (matches the other services; local/dev deployment)

## Decisions

1. **Orchestrator layout** — mirror the existing service pattern (flat modules + `config.py` sys.path bootstrap + `tests/`), so the codebase stays uniform:
   - `main.py` — FastAPI app: `POST /pipeline/run`, `GET /pipeline/runs`, `GET /health`; starts/stops the scheduler via lifespan
   - `pipeline.py` — `run_pipeline(settings, client) -> PipelineRunResult`: the three HTTP calls, dedup filtering, timing, error capture
   - `state.py` — load/save the alerted-findings state file; key = `f"{product_id}|{regulation}"`
   - `scheduler.py` — APScheduler `BackgroundScheduler` with one interval job calling `run_pipeline`
   - `config.py` — pydantic-settings: service URLs, `PIPELINE_INTERVAL_HOURS` (default 6, `0` disables), `STATE_PATH`, `HTTP_TIMEOUT`, `ALERT_LIMIT`/`ONLY_CHANNEL` pass-throughs
2. **Sync httpx + BackgroundScheduler** (not async/AsyncIOScheduler) — the existing services use sync httpx and the pipeline is strictly sequential; async buys nothing here. Alternative rejected: async orchestration adds complexity with no concurrency to exploit.
3. **Dedup key = `product_id|regulation`** — matches how the engine emits findings (one per product × rule) and survives re-runs where deadlines/messages vary. Alternative rejected: hashing the whole Finding would re-alert on any wording change.
4. **State file `orchestrator/.state/alerted.json`** (gitignored) storing `{key: first_alerted_iso}`; written atomically (write temp + replace). Run history: in-memory list of `PipelineRunResult` (session-scoped, like alerting's log). Alternative rejected: persisting run history to disk — deferred to the future database.
5. **Purify services by deletion, not deprecation** — remove `GET /findings` (assessment), `/dispatch` + `/refresh` (alerting), and assessment's fetch-fallback in `POST /assess` (body becomes required; empty list allowed). Keeping them as "conveniences" would preserve the hidden coupling this change exists to remove. `/test-email` stays (pure, no chaining).
6. **`PipelineRunResult` lives in `contracts/models.py`** next to the other DTOs, exported to `pipeline_run_result.schema.json` by `export_schemas.py`. It is not frozen (unlike Requirement/Finding) since it aggregates mutable run stats before emission — constructed once at run end, so freeze it anyway for consistency.
7. **`run_all.ps1`** gains a fourth entry (orchestrator :8080, started last, gated on `/health` like the rest).

## Risks / Trade-offs

- [Removing endpoints breaks external callers] → Nothing in-repo calls them after this change; README/CLAUDE.MD document the new entry point (`POST :8080/pipeline/run`).
- [State file corruption/loss re-alerts everything] → Atomic writes; on unreadable state, log a warning and start empty (worst case: duplicate alerts, sends are simulated without credentials anyway).
- [Scheduled run overlapping a slow manual run] → APScheduler `max_instances=1` plus a module-level run lock shared with the API path; overlapping trigger returns 409.
- [CELLAR slowness (~8s) makes scheduled runs slow] → acceptable; timeout via `HTTP_TIMEOUT` (default 180s), failures recorded per-run in `errors`.

## Migration Plan

1. Add contract DTO + schema (additive).
2. Build orchestrator with tests (additive).
3. Remove chaining endpoints from assessment/alerting + adapt their tests (breaking, same change).
4. Update `run_all.ps1` + docs. Rollback = revert the change; services keep working standalone since `POST /assess` / `POST /alerts` signatures only lose fallbacks.

## Open Questions

- None — form, data flow, DTO shape, and alert policy were decided with the owner (see proposal).
