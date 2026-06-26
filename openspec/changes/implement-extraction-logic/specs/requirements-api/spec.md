## ADDED Requirements

### Requirement: List requirements endpoint
The system SHALL expose a GET /requirements endpoint to list persisted requirements.

#### Scenario: List all requirements
- **WHEN** GET /requirements is called with no filters
- **THEN** the system SHALL return all requirements from the database
- **THEN** it SHALL return them as JSON array of Requirement objects
- **THEN** it SHALL sort by deadline_date ascending (earliest first)

#### Scenario: Filter by regulation family
- **WHEN** GET /requirements?regulation_family=battery is called
- **THEN** the system SHALL return only requirements matching that family
- **THEN** it SHALL return 200 OK with filtered results

#### Scenario: Filter by severity
- **WHEN** GET /requirements?severity=high is called
- **THEN** the system SHALL return only high-severity requirements
- **THEN** it SHALL return 200 OK with filtered results

#### Scenario: Pagination
- **WHEN** GET /requirements?limit=10&offset=20 is called
- **THEN** the system SHALL return 10 requirements starting from offset 20
- **THEN** it SHALL include pagination metadata in response

#### Scenario: Empty result set
- **WHEN** no requirements match the filters
- **THEN** the system SHALL return 200 OK with empty array
- **THEN** it SHALL not return 404

### Requirement: Get single requirement endpoint
The system SHALL expose a GET /requirements/{update_id} endpoint to retrieve a specific requirement.

#### Scenario: Requirement exists
- **WHEN** GET /requirements/{update_id} is called with valid ID
- **THEN** the system SHALL return the requirement as JSON
- **THEN** it SHALL return 200 OK

#### Scenario: Requirement not found
- **WHEN** GET /requirements/{update_id} is called with non-existent ID
- **THEN** the system SHALL return 404 Not Found
- **THEN** it SHALL include error message in response

### Requirement: Trigger extraction endpoint
The system SHALL expose a POST /extract endpoint to manually trigger extraction.

#### Scenario: Trigger extraction
- **WHEN** POST /extract is called
- **THEN** the system SHALL start an extraction job
- **THEN** it SHALL return 202 Accepted immediately
- **THEN** it SHALL include job ID in response

#### Scenario: Extraction already running
- **WHEN** POST /extract is called while extraction is running
- **THEN** the system SHALL return 409 Conflict
- **THEN** it SHALL include message indicating job already in progress

### Requirement: Health check endpoint
The system SHALL expose a GET /health endpoint for health monitoring.

#### Scenario: Service healthy
- **WHEN** GET /health is called and service is operational
- **THEN** the system SHALL return 200 OK
- **THEN** it SHALL include status: "healthy" in response
- **THEN** it SHALL include database connectivity status

#### Scenario: Service unhealthy
- **WHEN** GET /health is called and database is unreachable
- **THEN** the system SHALL return 503 Service Unavailable
- **THEN** it SHALL include status: "unhealthy" in response
- **THEN** it SHALL include error details

### Requirement: OpenAPI documentation
The system SHALL provide OpenAPI documentation at /docs.

#### Scenario: Access API docs
- **WHEN** GET /docs is accessed in a browser
- **THEN** the system SHALL display interactive Swagger UI
- **THEN** it SHALL show all endpoints with request/response schemas

### Requirement: CORS support
The system SHALL support CORS for dashboard access.

#### Scenario: Preflight request
- **WHEN** OPTIONS request is received from allowed origin
- **THEN** the system SHALL return appropriate CORS headers
- **THEN** it SHALL allow GET and POST methods

#### Scenario: Actual request
- **WHEN** GET or POST request is received from allowed origin
- **THEN** the system SHALL include Access-Control-Allow-Origin header
- **THEN** it SHALL process the request normally
