# pipeline-orchestration

## ADDED Requirements

### Requirement: Manual pipeline trigger
The orchestrator SHALL expose `POST /pipeline/run` (port 8080) that executes the full pipeline — fetch requirements from the extraction service, assess them via the assessment service, dispatch alerts via the alerting service — carrying the data between services itself, and SHALL return a `PipelineRunResult`.

#### Scenario: Successful run
- **WHEN** `POST /pipeline/run` is called and all three services respond
- **THEN** the response is a `PipelineRunResult` with `requirements_count` > 0, `findings_count` ≥ 0, alert outcome counts, an empty `errors` list, and a unique `run_id`

#### Scenario: Upstream service failure
- **WHEN** a pipeline stage fails (e.g. extraction returns 502 or times out)
- **THEN** the run stops at that stage, the failure is recorded in `PipelineRunResult.errors`, and the result is still returned (HTTP 200 with errors populated) and kept in run history

#### Scenario: Concurrent run rejected
- **WHEN** `POST /pipeline/run` is called while another run (manual or scheduled) is in progress
- **THEN** the orchestrator responds 409 without starting a second run

### Requirement: Scheduled pipeline runs
The orchestrator SHALL run the same pipeline on a background schedule via APScheduler, with the interval configured by `PIPELINE_INTERVAL_HOURS` (default 6). Setting the interval to 0 SHALL disable scheduling.

#### Scenario: Interval fires
- **WHEN** the configured interval elapses
- **THEN** a pipeline run executes exactly as a manual trigger would and its result is appended to run history

#### Scenario: Scheduling disabled
- **WHEN** `PIPELINE_INTERVAL_HOURS=0`
- **THEN** no background job is registered and the pipeline runs only on manual trigger

### Requirement: Run history
The orchestrator SHALL keep the results of all pipeline runs in this session and expose them at `GET /pipeline/runs`, newest first.

#### Scenario: History after runs
- **WHEN** two runs have completed and `GET /pipeline/runs` is called
- **THEN** the response lists both `PipelineRunResult` objects, newest first

### Requirement: Only-new-findings alert policy
The orchestrator SHALL only dispatch alerts for findings not previously alerted, using a persisted state file keyed by `product_id|regulation`. Previously-alerted findings SHALL be skipped and counted in `PipelineRunResult.alerts_skipped`.

#### Scenario: First run alerts everything
- **WHEN** the pipeline runs with an empty state file and produces 15 findings
- **THEN** 15 alerts are dispatched and 15 keys are recorded in the state file

#### Scenario: Repeat run skips known findings
- **WHEN** the pipeline runs again and produces the same 15 findings
- **THEN** 0 alerts are dispatched and `alerts_skipped` = 15

#### Scenario: Unreadable state degrades safely
- **WHEN** the state file is missing or corrupt
- **THEN** the orchestrator logs a warning, starts with empty state, and the run proceeds

### Requirement: PipelineRunResult contract
`contracts/models.py` SHALL define a `PipelineRunResult` model (run_id, started_at, duration_seconds, requirements_count, findings_count, alerts_sent, alerts_simulated, alerts_failed, alerts_skipped, errors) with a generated JSON schema kept in sync by `export_schemas.py`.

#### Scenario: Schema stays in sync
- **WHEN** `export_schemas.py` runs
- **THEN** a `pipeline_run_result.schema.json` matching `PipelineRunResult.model_json_schema()` is written alongside the existing two schemas

### Requirement: Health probe
The orchestrator SHALL expose `GET /health` returning service identity, consistent with the other services.

#### Scenario: Health check
- **WHEN** `GET /health` is called
- **THEN** the response is `{"status": "ok", "service": "orchestrator"}`
