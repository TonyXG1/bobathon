# Proposal: build-orchestrator-pipeline

## Why

The pipeline (extraction → assessment → alerting) currently has no owner: the chaining is hidden *inside* the services (assessment fetches from extraction, alerting fetches from assessment), there is no scheduling, no run history, and every run would re-send all alerts. The `orchestrator/` directory is an empty stub. We need one component that runs the pipeline on a schedule, carries the data between pure services, records what happened, and only alerts **new** findings.

## What Changes

- **New orchestrator service** (FastAPI, port 8080) in `orchestrator/`:
  - `POST /pipeline/run` — trigger a full pipeline run now, returns a `PipelineRunResult`
  - `GET /pipeline/runs` — history of runs (this session + persisted summaries)
  - `GET /health` — liveness probe
  - APScheduler background job running the pipeline on an interval (env `PIPELINE_INTERVAL_HOURS`, default 6)
- **Orchestrator carries the data**: `GET :8081/requirements` → `POST :8082/assess` (requirements in body) → `POST :8083/alerts` (findings in body)
- **BREAKING — services become pure** (inter-service HTTP chaining removed):
  - assessment: `GET /findings` (which fetched from extraction) removed; `POST /assess` no longer falls back to fetching from extraction — requirements body becomes required
  - alerting: `POST /dispatch` and `POST /refresh` (which fetched from assessment/extraction) removed; `POST /alerts` stays as the pure entry point
- **New `PipelineRunResult` DTO** in `contracts/models.py` (+ regenerated JSON schema): run_id, started_at, duration, requirements_count, findings_count, alerts_sent/simulated/failed/skipped counts, errors list
- **Only-new-findings alert policy**: orchestrator keeps a JSON state file (key: `product_id + regulation`) of already-alerted findings; repeats are skipped and counted in the run result
- `run_all.ps1` starts the orchestrator after the three services; docs (README, CLAUDE.MD, service READMEs) updated
- New offline test suite for the orchestrator (httpx mocked)

## Capabilities

### New Capabilities
- `pipeline-orchestration`: scheduling, executing, and recording end-to-end pipeline runs (extraction → assessment → alerting), including the run-history API and the only-new-findings alert dedup state

### Modified Capabilities
- `gap-assessment-api`: `POST /assess` requires the requirements in the body (no longer fetches from extraction); `GET /findings` removed
- `alert-dispatch-api`: `POST /dispatch` and `POST /refresh` removed; `POST /alerts` is the single entry point

## Impact

- **Code**: new `orchestrator/` modules (main, pipeline, scheduler, state, config, tests); deletions in `assessment_service/main.py` and `alerting_service/main.py` (+ their tests); `contracts/models.py` + `finding/requirement` schema re-export; `run_all.ps1`
- **APIs**: port 8080 added; `GET :8082/findings`, `POST :8083/dispatch`, `POST :8083/refresh` removed (**BREAKING** for anything calling them — nothing in-repo does after this change)
- **Dependencies**: orchestrator gains `fastapi`, `uvicorn`, `apscheduler`, `httpx` (already declared except fastapi/uvicorn)
- **State**: new gitignored JSON state file (e.g. `orchestrator/.state/alerted.json`) — the only persisted state in the system; designed to migrate to the future database
