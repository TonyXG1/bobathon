# finding-audit

Persistence of produced findings so every compliance decision is auditable after the fact:
which rule fired, against which obligation version, when.

## ADDED Requirements

### Requirement: Findings are persisted with the rule that fired

After each assessment run, the assessment service SHALL persist every produced `Finding` to the
findings table with all contract fields (company, partner_id, product_id, product, regulation,
requirement, source_url, gap, deadline, severity, recommended_action, alert channel/recipient/
message) plus audit columns: the `rule_id` of the gap rule that fired, a reference to the
obligation row that grounded it, and the assessment timestamp. Persisting findings SHALL NOT
alter the findings returned in the API response, and a persistence failure SHALL be logged
without failing the assessment response.

#### Scenario: Audit row per finding

- **WHEN** an assessment run produces N findings
- **THEN** N rows are written, each carrying the firing `rule_id`, an obligation reference, and
  `assessed_at`

#### Scenario: Response unaffected by persistence

- **WHEN** the findings table is unavailable during an assessment run
- **THEN** the API still returns the computed findings and logs the persistence failure

### Requirement: Every persisted finding cites its live source

Each persisted finding SHALL carry the non-null `source_url` of the requirement it was derived
from, preserving the "no source → no finding" invariant in the audit trail.

#### Scenario: Source URL present in audit

- **WHEN** any finding row is read back
- **THEN** its `source_url` is non-empty and matches the cited obligation's `source_url`
