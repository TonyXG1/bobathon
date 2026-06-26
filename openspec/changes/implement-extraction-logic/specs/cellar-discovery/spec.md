## ADDED Requirements

### Requirement: SPARQL cursor-based discovery
The system SHALL query CELLAR's SPARQL endpoint to discover new and changed legislation documents using cursor-based pagination.

#### Scenario: Initial discovery
- **WHEN** the system runs discovery for the first time
- **THEN** it SHALL query CELLAR SPARQL for all in-force legislation matching the watchlist
- **THEN** it SHALL store a cursor for incremental fetching

#### Scenario: Incremental discovery
- **WHEN** the system runs discovery with an existing cursor
- **THEN** it SHALL query CELLAR SPARQL for documents modified since the cursor timestamp
- **THEN** it SHALL return only new or changed CELEX numbers
- **THEN** it SHALL update the cursor to the latest modification timestamp

#### Scenario: Rate limit compliance
- **WHEN** querying CELLAR SPARQL
- **THEN** the system SHALL maintain fewer than 5 concurrent connections
- **THEN** it SHALL use LIMIT and OFFSET for pagination
- **THEN** it SHALL respect 60-second query timeout

### Requirement: Watchlist filtering
The system SHALL filter SPARQL results to only include documents from the predefined regulation watchlist.

#### Scenario: Watchlist match
- **WHEN** SPARQL returns a document with CELEX matching the watchlist
- **THEN** the system SHALL include it in the discovery results

#### Scenario: Non-watchlist document
- **WHEN** SPARQL returns a document not in the watchlist
- **THEN** the system SHALL exclude it from discovery results

### Requirement: Consolidated version resolution
The system SHALL resolve to consolidated versions of legislation (CELEX sector 0) to get current in-force text.

#### Scenario: Consolidated version available
- **WHEN** a document has a consolidated version
- **THEN** the system SHALL use the consolidated CELEX (e.g., 02011L0065-YYYYMMDD)
- **THEN** it SHALL record the consolidation date

#### Scenario: No consolidated version
- **WHEN** a document has no consolidated version
- **THEN** the system SHALL use the original CELEX
- **THEN** it SHALL record consolidation_date as null
