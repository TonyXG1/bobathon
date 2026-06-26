## ADDED Requirements

### Requirement: Content-hash based deduplication
The system SHALL use content hashing to detect truly changed requirements and avoid churning on republished-identical rules.

#### Scenario: Identical content
- **WHEN** a requirement's content hash matches an existing requirement
- **THEN** the system SHALL skip persisting it
- **THEN** it SHALL not update the database
- **THEN** it SHALL not trigger downstream processing

#### Scenario: Changed content
- **WHEN** a requirement's content hash differs from existing
- **THEN** the system SHALL persist the updated requirement
- **THEN** it SHALL update the existing record
- **THEN** it SHALL record the update timestamp

#### Scenario: New requirement
- **WHEN** a requirement has no existing record
- **THEN** the system SHALL persist it as a new record
- **THEN** it SHALL generate a unique update_id

### Requirement: Hash calculation
The system SHALL calculate content hashes from normalized requirement data.

#### Scenario: Hash includes core fields
- **WHEN** calculating content hash
- **THEN** the system SHALL include title, summary, scope, deadline_date, severity
- **THEN** it SHALL exclude access_timestamp and other metadata
- **THEN** it SHALL use SHA-256 algorithm

#### Scenario: Consistent hashing
- **WHEN** calculating hash for the same content multiple times
- **THEN** the system SHALL produce identical hashes
- **THEN** it SHALL normalize whitespace before hashing

### Requirement: SQLite persistence
The system SHALL persist requirements to the SQLite database with full provenance.

#### Scenario: Insert new requirement
- **WHEN** persisting a new requirement
- **THEN** the system SHALL insert into requirements table
- **THEN** it SHALL set created_at to current timestamp
- **THEN** it SHALL set updated_at to current timestamp

#### Scenario: Update existing requirement
- **WHEN** persisting a changed requirement
- **THEN** the system SHALL update the existing record
- **THEN** it SHALL preserve created_at
- **THEN** it SHALL update updated_at to current timestamp

#### Scenario: Provenance fields
- **WHEN** persisting any requirement
- **THEN** the system SHALL include source_url (mandatory)
- **THEN** it SHALL include access_timestamp
- **THEN** it SHALL include celex (if available)
- **THEN** it SHALL include consolidation_date (if available)

### Requirement: Requirement model validation
The system SHALL validate requirements against the Pydantic model before persistence.

#### Scenario: Valid requirement
- **WHEN** a requirement passes Pydantic validation
- **THEN** the system SHALL persist it to the database

#### Scenario: Invalid requirement
- **WHEN** a requirement fails Pydantic validation
- **THEN** the system SHALL log the validation error
- **THEN** it SHALL not persist the requirement
- **THEN** it SHALL continue processing other requirements

#### Scenario: Missing source_url
- **WHEN** a requirement has no source_url
- **THEN** Pydantic validation SHALL fail
- **THEN** the system SHALL not persist it

### Requirement: Cursor advancement
The system SHALL advance the cursor after successful persistence.

#### Scenario: Successful batch
- **WHEN** all requirements in a batch are processed
- **THEN** the system SHALL update the cursor to the latest modification timestamp
- **THEN** it SHALL persist the cursor for next run

#### Scenario: Partial failure
- **WHEN** some requirements fail to persist
- **THEN** the system SHALL still advance the cursor
- **THEN** it SHALL log failed requirements for manual review

### Requirement: Audit trail
The system SHALL record extraction runs in the extraction_runs table.

#### Scenario: Start extraction run
- **WHEN** starting an extraction job
- **THEN** the system SHALL insert a record in extraction_runs
- **THEN** it SHALL set started_at to current timestamp
- **THEN** it SHALL set status to "running"

#### Scenario: Complete extraction run
- **WHEN** extraction completes successfully
- **THEN** the system SHALL update the extraction_runs record
- **THEN** it SHALL set completed_at to current timestamp
- **THEN** it SHALL set status to "completed"
- **THEN** it SHALL record requirements_found, requirements_new, requirements_updated counts

#### Scenario: Failed extraction run
- **WHEN** extraction fails
- **THEN** the system SHALL update the extraction_runs record
- **THEN** it SHALL set status to "failed"
- **THEN** it SHALL record error_message
