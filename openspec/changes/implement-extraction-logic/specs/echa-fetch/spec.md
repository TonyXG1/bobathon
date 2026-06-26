## ADDED Requirements

### Requirement: ECHA SVHC Candidate List fetching
The system SHALL fetch the ECHA SVHC Candidate List to discover substance restrictions.

#### Scenario: Successful fetch
- **WHEN** fetching the ECHA Candidate List
- **THEN** the system SHALL retrieve the HTML table from the ECHA URL
- **THEN** it SHALL parse the table into structured data
- **THEN** it SHALL return a list of substances with their details

#### Scenario: Parse substance details
- **WHEN** parsing the ECHA table
- **THEN** the system SHALL extract substance name
- **THEN** it SHALL extract CAS number
- **THEN** it SHALL extract date of inclusion
- **THEN** it SHALL extract reason for inclusion

### Requirement: Change detection
The system SHALL detect changes in the ECHA Candidate List since the last fetch.

#### Scenario: New substance added
- **WHEN** comparing current list to cached list
- **THEN** the system SHALL identify substances present in current but not in cached
- **THEN** it SHALL mark them as new additions

#### Scenario: Substance details modified
- **WHEN** a substance exists in both lists but details differ
- **THEN** the system SHALL mark it as modified
- **THEN** it SHALL record what changed

#### Scenario: No changes
- **WHEN** current list matches cached list exactly
- **THEN** the system SHALL return empty change set
- **THEN** it SHALL not trigger downstream processing

### Requirement: Caching
The system SHALL cache the ECHA Candidate List to minimize requests.

#### Scenario: Cache hit within TTL
- **WHEN** cached data exists and is within TTL (default 24 hours)
- **THEN** the system SHALL return cached data
- **THEN** it SHALL not make a network request

#### Scenario: Cache expired
- **WHEN** cached data is older than TTL
- **THEN** the system SHALL fetch fresh data from ECHA
- **THEN** it SHALL update the cache

#### Scenario: Cache miss
- **WHEN** no cached data exists
- **THEN** the system SHALL fetch from ECHA
- **THEN** it SHALL populate the cache

### Requirement: Polite client behavior
The system SHALL implement polite client behavior when accessing ECHA.

#### Scenario: User-Agent header
- **WHEN** making any request to ECHA
- **THEN** the system SHALL include a User-Agent header with contact information

#### Scenario: Rate limiting
- **WHEN** ECHA returns rate limit errors
- **THEN** the system SHALL back off and retry with exponential delay

#### Scenario: Request timeout
- **WHEN** making any request
- **THEN** the system SHALL set an explicit timeout (default 30 seconds)
