## ADDED Requirements

### Requirement: Category mapping
The system SHALL map extracted text to product categories from taxonomy.json using keyword matching.

#### Scenario: Direct category match
- **WHEN** body text contains a category keyword (e.g., "LED lighting", "battery pack")
- **THEN** the system SHALL map it to the corresponding taxonomy.product_categories key
- **THEN** it SHALL add the category to the requirement scope

#### Scenario: Multiple categories
- **WHEN** body text matches multiple category keywords
- **THEN** the system SHALL include all matching categories in the scope

#### Scenario: All categories scope
- **WHEN** body text indicates broad applicability (e.g., "all electronic equipment")
- **THEN** the system SHALL set scope.categories to "all"

#### Scenario: No category match
- **WHEN** no category keywords are found
- **THEN** the system SHALL log a warning
- **THEN** it SHALL set scope.categories to empty array

### Requirement: Substance mapping
The system SHALL map extracted text to substances from taxonomy.json using keyword matching.

#### Scenario: Substance name match
- **WHEN** body text contains a substance name (e.g., "lead", "cadmium", "DEHP")
- **THEN** the system SHALL map it to the corresponding taxonomy.substances key
- **THEN** it SHALL add the substance to the requirement scope

#### Scenario: CAS number match
- **WHEN** body text contains a CAS number
- **THEN** the system SHALL map it to the corresponding substance
- **THEN** it SHALL add the substance to the requirement scope

#### Scenario: Chemical formula match
- **WHEN** body text contains a chemical formula (e.g., "Pb", "Cd", "Hg")
- **THEN** the system SHALL map it to the corresponding substance
- **THEN** it SHALL add the substance to the requirement scope

#### Scenario: No substances
- **WHEN** the requirement does not restrict specific substances
- **THEN** the system SHALL set scope.substances to empty array

### Requirement: Regulation family mapping
The system SHALL map the document to a regulation family from taxonomy.json.

#### Scenario: CELEX-based mapping
- **WHEN** the CELEX number matches a known regulation
- **THEN** the system SHALL map it to the corresponding taxonomy.regulation_families key
- **THEN** it SHALL set the regulation_family field

#### Scenario: Title-based mapping
- **WHEN** CELEX mapping fails but title contains regulation keywords
- **THEN** the system SHALL map based on title keywords
- **THEN** it SHALL set the regulation_family field

#### Scenario: Unknown regulation
- **WHEN** no mapping can be determined
- **THEN** the system SHALL set regulation_family to "other"
- **THEN** it SHALL log a warning for manual review

### Requirement: Market extraction
The system SHALL extract applicable markets from the document.

#### Scenario: EU-wide applicability
- **WHEN** document indicates EU-wide applicability
- **THEN** the system SHALL set scope.markets to ["EU"]

#### Scenario: Specific member states
- **WHEN** document specifies individual member states
- **THEN** the system SHALL list those states using ISO country codes
- **THEN** it SHALL set scope.markets to the list

#### Scenario: No market specified
- **WHEN** market scope is unclear
- **THEN** the system SHALL default to ["EU"]

### Requirement: Conditions extraction
The system SHALL extract free-text conditions and carve-outs from the document.

#### Scenario: Scope conditions
- **WHEN** document contains scope-limiting conditions
- **THEN** the system SHALL extract the condition text
- **THEN** it SHALL set scope.conditions to the extracted text

#### Scenario: Exclusions
- **WHEN** document contains exclusions (e.g., "except medical devices")
- **THEN** the system SHALL include them in scope.conditions

#### Scenario: No conditions
- **WHEN** no special conditions apply
- **THEN** the system SHALL set scope.conditions to empty string

### Requirement: Taxonomy consistency
The system SHALL only use keys that exist in taxonomy.json.

#### Scenario: Valid taxonomy key
- **WHEN** mapping to a taxonomy key
- **THEN** the system SHALL verify the key exists in taxonomy.json
- **THEN** it SHALL use the exact key (case-sensitive)

#### Scenario: Invalid taxonomy key
- **WHEN** a mapped key does not exist in taxonomy.json
- **THEN** the system SHALL log an error
- **THEN** it SHALL not include the invalid key in the scope
