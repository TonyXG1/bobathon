## Why

The extraction service (Part 1) currently has no implementation. We need to build the core logic that pulls live regulatory requirements from EUR-Lex/CELLAR and ECHA, normalizes them to the Requirement schema, and persists them with full provenance tracking. This is the foundation of the entire compliance monitoring pipeline - without it, the assessment and alerting services have no data to work with.

## What Changes

- Implement SPARQL cursor-based discovery against CELLAR to detect new/changed legislation
- Implement ECHA SVHC Candidate List fetching and diffing for substance restrictions
- Implement Formex XML fetching and parsing from CELLAR REST API
- Implement XPath-based metadata extraction and taxonomy keyword matching for scope normalization
- Implement content-hash based deduplication to avoid churning on republished-identical rules
- Implement SQLite persistence with full provenance (source_url, CELEX, consolidation_date, access_timestamp)
- Implement cursor advancement for incremental fetching
- Expose `GET /requirements` endpoint to list persisted requirements

## Capabilities

### New Capabilities

- `cellar-discovery`: SPARQL-based discovery of new/changed legislation in CELLAR with cursor tracking
- `cellar-fetch`: Formex XML retrieval from CELLAR REST API for specific CELEX documents
- `echa-fetch`: ECHA SVHC Candidate List fetching and change detection
- `formex-parsing`: XPath-based extraction of metadata and body text from Formex XML
- `scope-normalization`: Taxonomy keyword matching to map raw text to controlled vocabulary (categories, substances, regulation families)
- `requirement-persistence`: Content-hash based deduplication and SQLite storage with provenance
- `requirements-api`: REST endpoint to expose persisted requirements

### Modified Capabilities

<!-- No existing capabilities are being modified - this is net-new implementation -->

## Impact

**Code:**
- New files in `extraction_service/`: `main.py`, `clients.py`, `normalize.py`, `change.py`, `database.py`, `config.py`
- New test files in `extraction_service/tests/`

**Dependencies:**
- Requires `contracts` package for Requirement Pydantic model
- Requires `dataset/taxonomy.json` for normalization mappings
- Requires live access to CELLAR SPARQL endpoint and CELLAR REST API
- Requires live access to ECHA Candidate List

**APIs:**
- New endpoint: `GET /requirements` (returns list of Requirement objects)
- New endpoint: `POST /extract` (triggers extraction job)
- New endpoint: `GET /health` (health check)

**Database:**
- Populates `requirements` table in SQLite/Postgres
- Populates `extraction_runs` table for audit trail

**Downstream:**
- Assessment service (Part 2) depends on this data
- Dashboard (Part 4) will display this data
