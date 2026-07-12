# obligation-store

The relational obligation store: a single PostgreSQL database holding regulatory obligations as
normalized, machine-checkable rows. It is the system of record and the ONLY data source the
assessment decision path reads.

## ADDED Requirements

### Requirement: Obligation schema is derived from the Requirement contract

The obligation table SHALL contain exactly the fields of the `Requirement` contract
(`contracts/models.py`) as typed columns — identification (`update_id`, `published_date`),
provenance (`source`, `source_url` NOT NULL, `celex`, `consolidation_date`, `access_timestamp`),
classification (`regulation_family`, `reference`, `change_type`), content (`title`, `summary`,
`severity`, `action_required`), dates (`effective_date`, `deadline_date`), scope (all-categories
flag, categories, substances, markets, conditions), and `corrects` — plus storage-only columns for
content hash, temporal validity, and lineage. Columns extraction cannot yet populate SHALL be
nullable. No scope dimension beyond those the assessment predicate uses SHALL be invented.

#### Scenario: Round-trip preserves the contract

- **WHEN** a valid `Requirement` is persisted and read back through the repository
- **THEN** the rehydrated `Requirement` model equals the original on every contract field

#### Scenario: Provenance is mandatory

- **WHEN** an obligation row is written
- **THEN** it carries a non-null `source_url` and `access_timestamp`, and inserting without a
  `source_url` fails at the database constraint

### Requirement: Extraction persists fetched obligations by content hash

After each live CELLAR fetch, the extraction service SHALL upsert every normalized `Requirement`
into the obligation store keyed by a content hash computed over the requirement's canonical
content excluding `access_timestamp`. An unchanged rule SHALL be a semantic no-op (only the access
timestamp refreshes); a changed rule SHALL create a new row that supersedes the previous version;
existing rows SHALL never be overwritten or deleted.

#### Scenario: Re-fetch of unchanged rule is a no-op

- **WHEN** the same rule content is fetched twice
- **THEN** exactly one obligation row exists for it, with an updated `access_timestamp`

#### Scenario: Changed rule supersedes, not overwrites

- **WHEN** a rule with a known `update_id` is fetched with different content
- **THEN** a new row is inserted whose `supersedes_id` references the old row, the old row's
  `valid_to` is set, and the old row's content is unchanged

### Requirement: GET /requirements serves from the obligation store

`GET /requirements` on the extraction service SHALL fetch live from CELLAR, persist the results,
and respond with the in-force obligations read back from the database as `Requirement` objects.
If the live fetch fails entirely but in-force obligations exist in the store, the service SHALL
serve those (their provenance still cites the original live source and access time). If both the
live fetch and the store are empty, the service SHALL return 502 as today.

#### Scenario: Live fetch populates and serves

- **WHEN** `GET /requirements` succeeds against CELLAR
- **THEN** the response body rows match in-force rows now present in the database

#### Scenario: Store bridges a live outage

- **WHEN** CELLAR is unreachable and the store holds previously fetched in-force obligations
- **THEN** `GET /requirements` returns those obligations instead of an error

### Requirement: Assessment reads obligations only from the store

The assessment service SHALL obtain requirements for matching from the obligation store's
in-force set (`valid_to IS NULL`) via the repository, not via HTTP to the extraction service,
whenever a database is configured and populated. The matcher (`engine.assess`) SHALL be invoked
with rehydrated `Requirement` contract objects and its matching logic and outcomes SHALL remain
unchanged. Every compliance decision SHALL be derivable from relational columns alone.

#### Scenario: DB-backed assessment matches stateless assessment

- **WHEN** the same requirement set is assessed once passed in directly and once read from the
  store
- **THEN** the resulting findings are identical

#### Scenario: Graceful degradation without a database

- **WHEN** no database is configured or reachable
- **THEN** the assessment service falls back to the existing live HTTP path and still produces
  findings

### Requirement: Obligation lineage is queryable inside Postgres

Amendment/supersession relationships SHALL be modeled as self-referencing foreign keys and
traversed with recursive CTEs exposed by the repository (e.g. the version chain of an
`update_id`). No graph database SHALL be introduced, and lineage traversal SHALL remain isolated
in the repository layer, outside the matcher.

#### Scenario: Version chain traversal

- **WHEN** an obligation has been superseded twice
- **THEN** the repository lineage query returns the full chain of three versions in order
