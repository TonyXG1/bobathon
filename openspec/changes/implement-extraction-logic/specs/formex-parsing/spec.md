## ADDED Requirements

### Requirement: XPath-based metadata extraction
The system SHALL extract metadata from Formex XML using XPath queries.

#### Scenario: Extract CELEX number
- **WHEN** parsing Formex XML
- **THEN** the system SHALL extract the CELEX number from the document metadata
- **THEN** it SHALL validate the CELEX format

#### Scenario: Extract publication date
- **WHEN** parsing Formex XML
- **THEN** the system SHALL extract the publication date
- **THEN** it SHALL convert it to ISO 8601 date format

#### Scenario: Extract title
- **WHEN** parsing Formex XML
- **THEN** the system SHALL extract the document title
- **THEN** it SHALL handle multilingual titles (prefer English)

#### Scenario: Extract legal reference
- **WHEN** parsing Formex XML
- **THEN** the system SHALL extract article/annex references
- **THEN** it SHALL format them consistently (e.g., "Article 77", "Annex II")

### Requirement: Body text extraction
The system SHALL extract the body text from Formex XML for scope analysis.

#### Scenario: Extract full text
- **WHEN** parsing Formex XML
- **THEN** the system SHALL extract all body text content
- **THEN** it SHALL preserve paragraph structure
- **THEN** it SHALL strip XML formatting tags

#### Scenario: Extract specific sections
- **WHEN** parsing Formex XML with section markers
- **THEN** the system SHALL extract text from specific sections (e.g., scope, definitions)
- **THEN** it SHALL associate text with section identifiers

### Requirement: Safe XML parsing
The system SHALL use defusedxml to prevent XXE and other XML attacks.

#### Scenario: Parse with defusedxml
- **WHEN** parsing any Formex XML
- **THEN** the system SHALL use defusedxml.ElementTree (not xml.etree)
- **THEN** it SHALL disable DTD processing
- **THEN** it SHALL disable external entity resolution

#### Scenario: Malformed XML
- **WHEN** receiving malformed XML
- **THEN** the system SHALL raise a parsing error
- **THEN** it SHALL not crash or expose internal details

### Requirement: Consolidation date extraction
The system SHALL extract the consolidation date from consolidated acts.

#### Scenario: Consolidated version
- **WHEN** parsing a consolidated act (CELEX sector 0)
- **THEN** the system SHALL extract the consolidation date from metadata
- **THEN** it SHALL record it in ISO 8601 format

#### Scenario: Original version
- **WHEN** parsing an original act (not consolidated)
- **THEN** the system SHALL set consolidation_date to null
