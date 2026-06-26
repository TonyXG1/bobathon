## ADDED Requirements

### Requirement: Formex XML retrieval
The system SHALL fetch Formex XML documents from CELLAR REST API for specific CELEX numbers.

#### Scenario: Successful fetch
- **WHEN** given a valid CELEX number
- **THEN** the system SHALL construct the CELLAR REST URL
- **THEN** it SHALL fetch the Formex XML document
- **THEN** it SHALL return the XML content

#### Scenario: Document not found
- **WHEN** given a CELEX that does not exist
- **THEN** the system SHALL return an error indicating document not found

#### Scenario: Network timeout
- **WHEN** the CELLAR REST API does not respond within the timeout
- **THEN** the system SHALL raise a timeout error
- **THEN** it SHALL allow retry with exponential backoff

### Requirement: Conditional GET support
The system SHALL use conditional GET (If-None-Match, If-Modified-Since) to avoid re-fetching unchanged documents.

#### Scenario: Document unchanged
- **WHEN** fetching a document with ETag/Last-Modified headers
- **THEN** the system SHALL send If-None-Match/If-Modified-Since headers
- **THEN** it SHALL receive 304 Not Modified if unchanged
- **THEN** it SHALL skip processing and return cached version

#### Scenario: Document changed
- **WHEN** fetching a document that has been modified
- **THEN** the system SHALL receive 200 OK with new content
- **THEN** it SHALL update the cached ETag/Last-Modified
- **THEN** it SHALL process the new content

### Requirement: Polite client behavior
The system SHALL implement polite client behavior when accessing CELLAR REST API.

#### Scenario: User-Agent header
- **WHEN** making any request to CELLAR
- **THEN** the system SHALL include a User-Agent header with contact information

#### Scenario: Rate limiting
- **WHEN** making multiple requests
- **THEN** the system SHALL respect rate limits
- **THEN** it SHALL back off on 429 or 503 responses

#### Scenario: Request timeout
- **WHEN** making any request
- **THEN** the system SHALL set an explicit timeout (default 30 seconds)
