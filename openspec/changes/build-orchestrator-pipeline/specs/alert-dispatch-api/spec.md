# alert-dispatch-api

> First spec for this capability (no baseline in `openspec/specs/` yet): defines the alerting service's API surface after purification.

## ADDED Requirements

### Requirement: Pure alerts endpoint
The alerting service SHALL expose `POST /alerts` that takes `Finding[]` in the request body and dispatches one alert per finding on its channel (with `?limit=` and `?only_channel=` filters), simulating sends when credentials are incomplete or `TEST_MODE` is on. It SHALL NOT fetch findings from other services.

#### Scenario: Alerts for supplied findings
- **WHEN** `POST /alerts` receives a non-empty `Finding[]` body
- **THEN** each finding is rendered and dispatched (or simulated), logged to the in-memory delivery log, and the delivery results are returned

#### Scenario: Empty body rejected
- **WHEN** `POST /alerts` is called with an empty list
- **THEN** it responds 400

### Requirement: Chaining endpoints removed
The alerting service SHALL NOT expose `POST /dispatch` or `POST /refresh` (which previously fetched from the assessment/extraction services). Pipeline composition, scheduling, and summary reporting are the orchestrator's job. `POST /test-email` (pure, no chaining) SHALL remain.

#### Scenario: Old endpoints gone
- **WHEN** `POST /dispatch` or `POST /refresh` is called
- **THEN** the service responds 404 or 405

#### Scenario: Test email still works
- **WHEN** `POST /test-email` is called
- **THEN** one test email is sent (or simulated) and logged, with no calls to other services
