## Context

The extraction service currently has scaffolding (pyproject.toml, README, Dockerfile) but no implementation. We need to build the core logic that:
1. Discovers new/changed legislation from CELLAR (EUR-Lex) and ECHA
2. Fetches and parses Formex XML documents
3. Normalizes raw data to the Requirement Pydantic model
4. Persists with content-hash deduplication and full provenance

**Current State:**
- Contracts package defines Requirement Pydantic model
- Database schema exists (requirements table, extraction_runs table)
- Taxonomy.json provides controlled vocabulary
- No extraction logic implemented

**Constraints:**
- Must use defusedxml (not xml.etree) for XXE safety
- Must be a polite client (User-Agent, rate limits, conditional GET)
- Must cite source_url on every Requirement (non-negotiable)
- Must normalize to taxonomy.json keys only
- Must work within extraction_service/ directory only

**Stakeholders:**
- Assessment service (Part 2) depends on this data
- Dashboard (Part 4) displays this data
- Orchestrator schedules extraction jobs

## Goals / Non-Goals

**Goals:**
- Implement cursor-based incremental fetching from CELLAR SPARQL
- Implement ECHA SVHC list fetching with change detection
- Implement safe Formex XML parsing with XPath
- Implement taxonomy-based scope normalization
- Implement content-hash deduplication to avoid churn
- Implement full provenance tracking (source_url, CELEX, timestamps)
- Expose REST API for requirements access

**Non-Goals:**
- Assessment logic (Part 2 responsibility)
- Alert dispatch (Part 3 responsibility)
- Dashboard UI (Part 4 responsibility)
- Real-time streaming (batch-based is sufficient)
- Multi-language support (English only for MVP)

## Decisions

### Decision 1: Cursor-based SPARQL discovery vs. RSS polling

**Choice:** Cursor-based SPARQL with modification timestamp tracking

**Rationale:**
- SPARQL gives structured metadata (CELEX, dates, status)
- RSS feeds are less reliable and harder to parse
- Cursor allows precise incremental fetching
- Can query specific watchlist documents

**Alternatives considered:**
- RSS polling: Simpler but less structured, harder to filter
- Full corpus scan: Too slow, violates rate limits

**Implementation:**
- Store cursor (last modification timestamp) in database
- Query SPARQL with `FILTER(?modified > ?cursor)`
- Use LIMIT/OFFSET for pagination
- Update cursor after successful batch

### Decision 2: Formex XML vs. HTML scraping

**Choice:** Formex XML from CELLAR REST API

**Rationale:**
- Formex is structured, machine-readable format
- XPath queries are reliable and maintainable
- HTML is for human consumption, changes frequently
- Formex includes metadata not in HTML

**Alternatives considered:**
- HTML scraping: Fragile, breaks on layout changes
- PDF parsing: Even worse, no structure

**Implementation:**
- Construct URL: `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}&format=formex`
- Parse with defusedxml.ElementTree
- Extract metadata via XPath
- Extract body text for scope analysis

### Decision 3: Content hashing for deduplication

**Choice:** SHA-256 hash of normalized content fields

**Rationale:**
- Republished-identical rules shouldn't churn database
- SPARQL flags documents as "modified" even if content unchanged
- Hash comparison is fast and deterministic
- Avoids false positives in downstream processing

**Alternatives considered:**
- No deduplication: Causes unnecessary churn
- Full text comparison: Slower, whitespace-sensitive
- ETag-based: Not all sources provide ETags

**Implementation:**
- Hash includes: title, summary, scope, deadline_date, severity, action_required
- Excludes: access_timestamp, created_at, updated_at
- Normalize whitespace before hashing
- Compare hash before INSERT/UPDATE

### Decision 4: Taxonomy keyword matching for normalization

**Choice:** Simple keyword matching with fallback to manual review

**Rationale:**
- Taxonomy.json has ~17 categories, ~13 substances, ~20 families
- Keyword matching covers 90%+ of cases
- Complex NLP is overkill for this domain
- Manual review queue handles edge cases

**Alternatives considered:**
- NLP/ML classification: Overkill, adds complexity
- Manual-only: Too slow, doesn't scale
- LLM-based: Expensive, latency, requires API keys

**Implementation:**
- Load taxonomy.json at startup
- Build keyword → taxonomy_key mappings
- Match body text against keywords (case-insensitive)
- Log warnings for unmapped terms
- Default to "other" for regulation_family if no match

### Decision 5: SQLite for persistence

**Choice:** SQLite with optional Postgres upgrade path

**Rationale:**
- SQLite is zero-config, perfect for demo/dev
- Schema is already Postgres-compatible
- Can swap via DATABASE_URL env var
- No need for Postgres complexity in MVP

**Alternatives considered:**
- Postgres-only: Overkill for demo, adds setup burden
- In-memory: Loses data on restart
- JSON files: No query capability, no transactions

**Implementation:**
- Use SQLAlchemy for database abstraction
- Default to SQLite: `sqlite:///./regulatory_radar.db`
- Support Postgres: `postgresql://user:pass@host/db`
- Schema in database/init.sql works for both

### Decision 6: FastAPI for REST API

**Choice:** FastAPI with Pydantic v2 models

**Rationale:**
- Already chosen in AGENTS.md
- Auto-generates OpenAPI docs
- Pydantic integration for validation
- Async support for future optimization

**Implementation:**
- GET /requirements - list with filters
- GET /requirements/{update_id} - single requirement
- POST /extract - trigger extraction job
- GET /health - health check

## Risks / Trade-offs

### Risk: CELLAR SPARQL rate limiting
**Mitigation:**
- Keep < 5 concurrent connections
- Use LIMIT/OFFSET pagination
- Back off on 429/503 responses
- Cache results for 24 hours

### Risk: Formex XML schema changes
**Mitigation:**
- XPath queries are resilient to minor changes
- Log parsing errors for manual review
- Version XPath queries in code comments
- Monitor EUR-Lex announcements

### Risk: Taxonomy drift (new categories/substances)
**Mitigation:**
- Log unmapped terms for review
- Quarterly taxonomy.json updates
- Default to "other" for unknown families
- Manual review queue for edge cases

### Risk: Content hash collisions
**Mitigation:**
- SHA-256 has negligible collision probability
- Include multiple fields in hash
- Log hash values for debugging

### Risk: ECHA table format changes
**Mitigation:**
- BeautifulSoup is resilient to minor changes
- Cache last successful parse
- Fall back to cached data on parse failure
- Monitor ECHA announcements

### Trade-off: Keyword matching vs. NLP
**Chosen:** Keyword matching
**Trade-off:** Less accurate but much simpler and faster
**Acceptable because:** Manual review queue catches edge cases

### Trade-off: Batch vs. real-time
**Chosen:** Batch (scheduled extraction jobs)
**Trade-off:** Latency (hours) vs. complexity
**Acceptable because:** Regulatory changes are infrequent (days/weeks)

## Migration Plan

### Phase 1: Core Implementation (Week 1)
1. Implement clients.py (CellarClient, EchaClient)
2. Implement normalize.py (Formex parsing, taxonomy mapping)
3. Implement change.py (cursor tracking, content hashing)
4. Implement database.py (SQLAlchemy models, persistence)
5. Implement config.py (pydantic-settings)

### Phase 2: API & Integration (Week 1)
1. Implement main.py (FastAPI app, endpoints)
2. Write unit tests for each module
3. Write integration tests against fixtures
4. Test against live CELLAR/ECHA (rate-limited)

### Phase 3: Deployment (Week 2)
1. Test with docker-compose
2. Verify orchestrator integration
3. Verify assessment service can read requirements
4. Load test with full watchlist

### Rollback Strategy
- No rollback needed (net-new implementation)
- If extraction fails, assessment service uses cached data
- Can disable extraction via feature flag: `ENABLE_CELLAR_SPARQL=false`

### Monitoring
- Track extraction_runs table for success/failure
- Alert on consecutive failures
- Monitor CELLAR/ECHA response times
- Track requirements_new/requirements_updated counts

## Open Questions

1. **SPARQL query optimization:** What's the optimal LIMIT for pagination?
   - **Resolution:** Start with 100, tune based on response times

2. **ECHA cache TTL:** 24 hours sufficient or too aggressive?
   - **Resolution:** Start with 24h, monitor ECHA update frequency

3. **Taxonomy updates:** Who maintains taxonomy.json?
   - **Resolution:** Team lead reviews quarterly, logs unmapped terms

4. **Error handling:** Retry logic for transient failures?
   - **Resolution:** Exponential backoff with max 3 retries

5. **Cursor persistence:** Store in database or config file?
   - **Resolution:** Database (extraction_runs table) for auditability
