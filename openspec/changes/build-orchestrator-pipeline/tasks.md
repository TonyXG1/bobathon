# Tasks: build-orchestrator-pipeline

## 1. Contract

- [ ] 1.1 Add `PipelineRunResult` model to `contracts/models.py` (run_id, started_at, duration_seconds, requirements_count, findings_count, alerts_sent, alerts_simulated, alerts_failed, alerts_skipped, errors: list[str]; frozen)
- [ ] 1.2 Extend `contracts/export_schemas.py` to also emit `pipeline_run_result.schema.json`; regenerate all schemas

## 2. Orchestrator service

- [ ] 2.1 `orchestrator/config.py` — pydantic-settings (sys.path bootstrap like the other services): `EXTRACTION_SERVICE_URL`, `ASSESSMENT_SERVICE_URL`, `ALERTING_SERVICE_URL`, `PIPELINE_INTERVAL_HOURS` (default 6, 0 = disabled), `STATE_PATH` (default `orchestrator/.state/alerted.json`), `HTTP_TIMEOUT` (default 300), `ALERT_LIMIT`, `ALERT_ONLY_CHANNEL`, `LOG_LEVEL`, `CORS_ORIGINS`
- [ ] 2.2 `orchestrator/state.py` — load/save alerted-keys state (`{key: first_alerted_iso}`), atomic write (temp file + `os.replace`), warn-and-start-empty on unreadable file; key builder `f"{product_id}|{regulation}"`
- [ ] 2.3 `orchestrator/pipeline.py` — `run_pipeline(settings, client=None) -> PipelineRunResult`: GET requirements → POST /assess (body) → filter findings through state → POST /alerts (body, respecting limit/only_channel) → update state → build result; per-stage error capture into `errors`, stop at first failed stage
- [ ] 2.4 `orchestrator/scheduler.py` — APScheduler `BackgroundScheduler`, one interval job (`max_instances=1`) calling the shared run entry; no job when interval is 0
- [ ] 2.5 `orchestrator/main.py` — FastAPI app (port 8080, CORS like the others, lifespan starts/stops scheduler): `GET /health`, `POST /pipeline/run` (409 when a run is already in progress — module-level lock shared with the scheduled path), `GET /pipeline/runs` (in-memory history, newest first)
- [ ] 2.6 `orchestrator/pyproject.toml` — add fastapi + uvicorn (httpx, pydantic, pydantic-settings, APScheduler already declared); add `.state/` to `.gitignore`

## 3. Purify the services (BREAKING)

- [ ] 3.1 assessment: make `requirements` required in `POST /assess` (422 when missing), delete `GET /findings` and `fetch_requirements_from_extraction`; drop now-unused settings
- [ ] 3.2 alerting: delete `POST /dispatch`, `POST /refresh`, `_summary_message`, and the assessment/extraction URL settings; keep `POST /alerts`, `POST /test-email`, log endpoints
- [ ] 3.3 Adapt existing tests: remove/replace tests covering deleted endpoints; add 404/422 assertions per the delta specs

## 4. Orchestrator tests (offline, httpx mocked)

- [ ] 4.1 `tests/test_state.py` — roundtrip, atomic write, corrupt-file fallback, key format
- [ ] 4.2 `tests/test_pipeline.py` — happy path (counts + state updated), dedup skip on second run (`alerts_skipped`), stage-failure capture (extraction 502 → errors populated, no alert call)
- [ ] 4.3 `tests/test_main.py` — /health, /pipeline/run returns PipelineRunResult, 409 on concurrent run, /pipeline/runs ordering

## 5. Wiring & docs

- [ ] 5.1 `run_all.ps1` — add orchestrator (:8080) after alerting, install its deps, gate on /health; update the header comment
- [ ] 5.2 Update README.md (architecture diagram + table + quick start now pointing at `POST :8080/pipeline/run`; endpoint lists), CLAUDE.MD (§3 table, §4 tree, §8/§11 endpoint references), and the three service READMEs (remove deleted endpoints, mention orchestrator)
- [ ] 5.3 Full verification: all offline suites pass; manual smoke — start all four services via run_all.ps1, `POST :8080/pipeline/run` twice, verify second run has `alerts_skipped` = first run's alert count
