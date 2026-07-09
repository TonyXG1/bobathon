# gap-assessment-api

> First spec for this capability (no baseline in `openspec/specs/` yet): defines the assessment service's API surface after purification.

## ADDED Requirements

### Requirement: Pure assessment endpoint
The assessment service SHALL expose `POST /assess` that takes `Requirement[]` in the request body (required) and returns `Finding[]`. It SHALL NOT make HTTP calls to other services: composition is the orchestrator's job.

#### Scenario: Assess supplied requirements
- **WHEN** `POST /assess` receives a body with a valid `requirements` list
- **THEN** it returns the findings produced by the deterministic gap engine against `dataset/partners.json`

#### Scenario: Missing requirements rejected
- **WHEN** `POST /assess` is called without a `requirements` list in the body
- **THEN** it responds 422 (validation error) and performs no outbound HTTP call

### Requirement: Chained findings endpoint removed
The assessment service SHALL NOT expose `GET /findings` (which previously fetched requirements from the extraction service itself). The full pipeline is available via the orchestrator's `POST /pipeline/run`.

#### Scenario: Old endpoint gone
- **WHEN** `GET /findings` is called
- **THEN** the service responds 404 or 405
